"""Spell management commands: learn, forget, prepare, cast, slots, cantrips, spells."""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.data.spells import (
    get_spell_slots, get_max_spell_level, get_cantrips_known,
    is_spellcaster, is_pact_caster, SPELL_LEVEL_NAMES,
)
from bot.storage import load_campaign, save_campaign


class SpellsCog(commands.Cog, name="Spells"):
    """Commands for managing spells, spell slots, and casting."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx):
        return load_campaign(str(ctx.channel.id))

    def _get_char(self, ctx):
        campaign = self._get_campaign(ctx)
        if not campaign:
            return None, None
        char = campaign.get_character(str(ctx.author.id))
        return campaign, char

    @commands.command(name="slots")
    async def spell_slots(self, ctx: commands.Context):
        """View your current spell slots.

        Usage: !slots
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return
        if not char.spellcasting_ability:
            await ctx.send(f"**{char.name}** is not a spellcaster.")
            return

        if not char.spell_slots_max:
            await ctx.send(f"**{char.name}** has no spell slots at this level.")
            return

        lines = [f"**{char.name}'s Spell Slots**"]
        for lvl in sorted(char.spell_slots_max, key=lambda x: int(x)):
            total = char.spell_slots_max[lvl]
            used = char.spell_slots_used.get(lvl, 0)
            remaining = total - used
            filled = "◆" * remaining + "◇" * used
            lvl_name = SPELL_LEVEL_NAMES.get(int(lvl), f"Lv{lvl}")
            lines.append(f"  **{lvl_name} level:** {filled} ({remaining}/{total})")

        pact_note = " *(Pact Magic — recovers on short rest)*" if is_pact_caster(char.char_class) else ""
        lines.append(f"\n*Use `!cast <spell name> <level>` to cast a spell.*{pact_note}")
        await ctx.send("\n".join(lines))

    @commands.command(name="spells")
    async def spells_list(self, ctx: commands.Context):
        """View your known spells, prepared spells, and cantrips.

        Usage: !spells
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return
        if not char.spellcasting_ability:
            await ctx.send(f"**{char.name}** is not a spellcaster.")
            return

        spell_mod = char.get_modifier(char.spellcasting_ability)
        spell_save = 8 + char.proficiency_bonus + spell_mod
        spell_atk = char.proficiency_bonus + spell_mod
        atk_str = f"+{spell_atk}" if spell_atk >= 0 else str(spell_atk)

        lines = [
            f"**{char.name}'s Spellbook** ({char.spellcasting_ability})",
            f"Spell Save DC: **{spell_save}** | Spell Attack: **{atk_str}**",
        ]

        max_cantrips = get_cantrips_known(char.char_class, char.level)
        if max_cantrips:
            cantrip_list = ", ".join(char.cantrips) if char.cantrips else "*None yet*"
            lines.append(f"\n**Cantrips** ({len(char.cantrips)}/{max_cantrips}): {cantrip_list}")

        if char.known_spells:
            lines.append(f"\n**Known Spells** ({len(char.known_spells)}):")
            for spell in sorted(char.known_spells):
                prep_mark = " ★" if spell in char.prepared_spells else ""
                lines.append(f"  • {spell}{prep_mark}")

        if char.prepared_spells:
            prepped = ", ".join(sorted(char.prepared_spells))
            lines.append(f"\n**Prepared** (★): {prepped}")

        if not char.known_spells and not char.cantrips:
            lines.append("\n*No spells yet. Use `!learn <spell>` to add spells.*")

        await ctx.send("\n".join(lines))

    @commands.command(name="learn")
    async def learn_spell(self, ctx: commands.Context, *, spell_name: str):
        """Add a spell to your known spells list.

        Usage: !learn Fireball
        Usage: !learn Cure Wounds
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return
        if not char.spellcasting_ability:
            await ctx.send(f"**{char.name}** is not a spellcaster.")
            return

        spell_name = spell_name.strip().title()

        if spell_name in char.known_spells:
            await ctx.send(f"**{char.name}** already knows **{spell_name}**.")
            return

        char.known_spells.append(spell_name)
        save_campaign(campaign)
        await ctx.send(f"**{char.name}** learned **{spell_name}**!")

    @commands.command(name="learncantrip")
    async def learn_cantrip(self, ctx: commands.Context, *, cantrip_name: str):
        """Add a cantrip to your cantrip list.

        Usage: !learncantrip Fire Bolt
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return
        if not char.spellcasting_ability:
            await ctx.send(f"**{char.name}** is not a spellcaster.")
            return

        cantrip_name = cantrip_name.strip().title()
        max_cantrips = get_cantrips_known(char.char_class, char.level)

        if cantrip_name in char.cantrips:
            await ctx.send(f"**{char.name}** already knows the cantrip **{cantrip_name}**.")
            return

        if len(char.cantrips) >= max_cantrips:
            await ctx.send(
                f"**{char.name}** already knows {max_cantrips} cantrips (max for "
                f"level {char.level} {char.char_class}). Use `!forget cantrip <name>` first."
            )
            return

        char.cantrips.append(cantrip_name)
        save_campaign(campaign)
        await ctx.send(f"**{char.name}** learned the cantrip **{cantrip_name}**!")

    @commands.command(name="forget")
    async def forget_spell(self, ctx: commands.Context, *, spell_name: str):
        """Remove a spell or cantrip from your known list.

        Usage: !forget Fireball
        Usage: !forget cantrip Fire Bolt
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return

        spell_name = spell_name.strip()

        # Check for "cantrip <name>" syntax
        if spell_name.lower().startswith("cantrip "):
            cantrip_name = spell_name[8:].strip().title()
            if cantrip_name in char.cantrips:
                char.cantrips.remove(cantrip_name)
                save_campaign(campaign)
                await ctx.send(f"**{char.name}** forgot the cantrip **{cantrip_name}**.")
            else:
                await ctx.send(f"**{char.name}** doesn't know the cantrip **{cantrip_name}**.")
            return

        spell_name = spell_name.title()
        if spell_name in char.known_spells:
            char.known_spells.remove(spell_name)
            if spell_name in char.prepared_spells:
                char.prepared_spells.remove(spell_name)
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** forgot **{spell_name}**.")
        else:
            await ctx.send(f"**{char.name}** doesn't know **{spell_name}**.")

    @commands.command(name="prepare")
    async def prepare_spell(self, ctx: commands.Context, *, spell_name: str):
        """Prepare a known spell for casting.

        Usage: !prepare Cure Wounds
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return
        if not char.spellcasting_ability:
            await ctx.send(f"**{char.name}** is not a spellcaster.")
            return

        spell_name = spell_name.strip().title()

        if spell_name not in char.known_spells:
            await ctx.send(f"**{char.name}** doesn't know **{spell_name}**. Use `!learn {spell_name}` first.")
            return

        if spell_name in char.prepared_spells:
            # Unprepare
            char.prepared_spells.remove(spell_name)
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** unprepared **{spell_name}**.")
        else:
            char.prepared_spells.append(spell_name)
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** prepared **{spell_name}**.")

    @commands.command(name="cast")
    async def cast_spell(self, ctx: commands.Context, *, args: str = ""):
        """Cast a spell, consuming a spell slot.

        Usage: !cast Fireball (uses lowest available slot)
        Usage: !cast Cure Wounds 2 (cast at 2nd level)
        """
        campaign, char = self._get_char(ctx)
        if not char:
            await ctx.send("You don't have a character.")
            return
        if not char.spellcasting_ability:
            await ctx.send(f"**{char.name}** is not a spellcaster.")
            return

        if not args.strip():
            await ctx.send("Usage: `!cast <spell name>` or `!cast <spell name> <level>`")
            return

        # Parse spell name and optional level
        parts = args.rsplit(None, 1)
        spell_level = None
        spell_name = args.strip().title()

        # Check if last word is a number (spell level)
        if len(parts) > 1 and parts[-1].isdigit():
            potential_level = int(parts[-1])
            if 1 <= potential_level <= 9:
                spell_level = potential_level
                spell_name = parts[0].strip().title()

        # Check if it's a cantrip
        if spell_name in char.cantrips:
            await ctx.send(f"**{char.name}** casts **{spell_name}**! *(cantrip — no slot used)*")
            return

        # Verify they know the spell
        if spell_name not in char.known_spells and spell_name not in char.prepared_spells:
            await ctx.send(f"**{char.name}** doesn't know **{spell_name}**.")
            return

        if not char.spell_slots_max:
            await ctx.send(f"**{char.name}** has no spell slots.")
            return

        # Find the lowest available slot if no level specified
        if spell_level is None:
            for lvl in sorted(char.spell_slots_max, key=lambda x: int(x)):
                used = char.spell_slots_used.get(lvl, 0)
                if used < char.spell_slots_max[lvl]:
                    spell_level = int(lvl)
                    break

        if spell_level is None:
            await ctx.send(f"**{char.name}** has no spell slots remaining! Take a rest to recover slots.")
            return

        lvl_key = str(spell_level)
        max_slots = char.spell_slots_max.get(lvl_key, 0)
        if max_slots == 0:
            await ctx.send(f"**{char.name}** doesn't have level {spell_level} spell slots.")
            return

        used = char.spell_slots_used.get(lvl_key, 0)
        if used >= max_slots:
            await ctx.send(
                f"**{char.name}** has no {SPELL_LEVEL_NAMES.get(spell_level, f'Lv{spell_level}')} "
                f"level slots remaining!"
            )
            return

        # Consume the slot
        char.spell_slots_used[lvl_key] = used + 1
        remaining = max_slots - used - 1
        save_campaign(campaign)

        lvl_name = SPELL_LEVEL_NAMES.get(spell_level, f"Lv{spell_level}")
        await ctx.send(
            f"**{char.name}** casts **{spell_name}** at {lvl_name} level!\n"
            f"*Spell slot used — {lvl_name} level: {remaining}/{max_slots} remaining*"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SpellsCog(bot))

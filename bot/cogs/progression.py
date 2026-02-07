"""Progression system: rest, level up, XP, inspiration."""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.data.rules import ABILITY_NAMES, SKILLS, xp_for_next_level, proficiency_bonus, modifier
from bot.data.spells import get_spell_slots, is_spellcaster, is_pact_caster

# Valid stat keys for modifiers
_VALID_STATS = set(ABILITY_NAMES) | set(SKILLS.keys()) | {"ac", "hp", "speed"}
# Aliases for convenience
_STAT_ALIASES = {
    "str": "STR", "dex": "DEX", "con": "CON", "int": "INT", "wis": "WIS", "cha": "CHA",
    "strength": "STR", "dexterity": "DEX", "constitution": "CON",
    "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA",
    "armor": "ac", "armor class": "ac",
    "health": "hp", "hitpoints": "hp", "hit points": "hp",
}

def _resolve_stat(name: str) -> str | None:
    """Resolve a stat name to its canonical form, or None if invalid."""
    # Check alias first
    lower = name.lower().strip()
    if lower in _STAT_ALIASES:
        return _STAT_ALIASES[lower]
    # Check exact (case-sensitive for skills like "Perception")
    if name in _VALID_STATS:
        return name
    # Try title case for skills
    titled = name.strip().title()
    if titled in _VALID_STATS:
        return titled
    # Try uppercase for abilities
    upper = name.strip().upper()
    if upper in _VALID_STATS:
        return upper
    # Check lowercase for ac/hp/speed
    if lower in _VALID_STATS:
        return lower
    return None
from bot.dice import roll_die
from bot.storage import load_campaign, save_campaign


class ProgressionCog(commands.Cog, name="Progression"):
    """Commands for character progression and resources."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx):
        return load_campaign(str(ctx.channel.id))

    @commands.command(name="rest")
    async def rest(self, ctx: commands.Context, rest_type: str = ""):
        """Take a short or long rest.

        Usage: !rest short
        Usage: !rest long
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        rest_type = rest_type.lower().strip()
        if rest_type not in ("short", "long"):
            await ctx.send("Usage: `!rest short` or `!rest long`")
            return

        if rest_type == "short":
            # Short rest: can spend hit dice to heal
            if char.hit_dice_remaining <= 0:
                await ctx.send(f"**{char.name}** takes a short rest but has no hit dice to spend.")
                return

            if char.current_hp >= char.max_hp:
                await ctx.send(f"**{char.name}** takes a short rest. Already at full HP ({char.max_hp}/{char.max_hp}).")
                return

            # Spend one hit die
            roll = roll_die(char.hit_die)
            con_mod = char.get_modifier("CON")
            healed = max(roll + con_mod, 1)
            old_hp = char.current_hp
            char.current_hp = min(char.current_hp + healed, char.max_hp)
            actual_healed = char.current_hp - old_hp
            char.hit_dice_remaining -= 1
            save_campaign(campaign)

            msg = (
                f"**{char.name}** takes a short rest.\n"
                f"Spent 1 hit die: d{char.hit_die} [{roll}] + CON ({con_mod:+d}) = **{healed}** HP healed\n"
                f"HP: {old_hp} -> **{char.current_hp}/{char.max_hp}**\n"
                f"Hit Dice remaining: {char.hit_dice_remaining}"
            )

            # Warlock pact magic recovers on short rest
            if is_pact_caster(char.char_class) and char.spell_slots_used:
                char.spell_slots_used = {}
                msg += "\n*Pact Magic spell slots restored!*"
                save_campaign(campaign)

            await ctx.send(msg)

        elif rest_type == "long":
            old_hp = char.current_hp
            char.current_hp = char.max_hp
            # Restore half of max hit dice (minimum 1)
            dice_restored = max(char.level // 2, 1)
            char.hit_dice_remaining = min(char.hit_dice_remaining + dice_restored, char.level)
            # Reset death saves
            char.death_saves = {"successes": 0, "failures": 0}
            # Restore all spell slots
            slots_restored = bool(char.spell_slots_used)
            char.spell_slots_used = {}
            save_campaign(campaign)

            hp_restored = char.max_hp - old_hp
            msg = (
                f"**{char.name}** takes a long rest.\n"
                f"HP fully restored: **{char.max_hp}/{char.max_hp}** (+{hp_restored})\n"
                f"Hit Dice restored: {dice_restored} (total: {char.hit_dice_remaining})\n"
                f"Death saves reset."
            )
            if slots_restored:
                msg += "\n*All spell slots restored!*"
            await ctx.send(msg)

    @commands.command(name="hp")
    async def adjust_hp(self, ctx: commands.Context, amount: str = ""):
        """View or adjust your HP. DM can adjust any player.

        Usage: !hp (view current HP)
        Usage: !hp -5 (take 5 damage)
        Usage: !hp +3 (heal 3)
        Usage: !hp @player -5 (DM adjusts player HP)
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        # Check if DM is targeting another player
        target_id = str(ctx.author.id)
        if ctx.message.mentions and campaign.dm_id == str(ctx.author.id):
            target_id = str(ctx.message.mentions[0].id)
            # Remove the mention from amount
            amount = amount.replace(ctx.message.mentions[0].mention, "").strip()

        char = campaign.get_character(target_id)
        if not char:
            await ctx.send("No character found.")
            return

        if not amount:
            await ctx.send(f"**{char.name}** — HP: **{char.current_hp}/{char.max_hp}** (Temp HP: {char.temp_hp})")
            return

        try:
            change = int(amount)
        except ValueError:
            await ctx.send("Usage: `!hp +5` or `!hp -3`")
            return

        old_hp = char.current_hp
        char.current_hp = max(0, min(char.current_hp + change, char.max_hp))
        save_campaign(campaign)

        if change > 0:
            await ctx.send(f"**{char.name}** healed {change} HP: {old_hp} -> **{char.current_hp}/{char.max_hp}**")
        elif change < 0:
            await ctx.send(f"**{char.name}** took {abs(change)} damage: {old_hp} -> **{char.current_hp}/{char.max_hp}**")
            if char.current_hp == 0:
                await ctx.send(f"**{char.name} has fallen to 0 HP!** Death saving throws begin...")

    @commands.command(name="xp")
    async def award_xp(self, ctx: commands.Context, amount: int = 0, member: discord.Member = None):
        """DM awards XP. Without a target, awards to all players.

        Usage: !xp 100 (award 100 XP to everyone)
        Usage: !xp 50 @player (award 50 XP to one player)
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if campaign.dm_id != str(ctx.author.id):
            await ctx.send("Only the DM can award XP.")
            return
        if amount <= 0:
            await ctx.send("Usage: `!xp <amount>` or `!xp <amount> @player`")
            return

        targets = []
        if member:
            char = campaign.get_character(str(member.id))
            if char:
                targets.append(char)
        else:
            targets = [c for c in campaign.characters.values() if c.creation_complete]

        if not targets:
            await ctx.send("No valid targets for XP.")
            return

        results = []
        for char in targets:
            char.xp += amount
            needed = xp_for_next_level(char.level)
            results.append(f"**{char.name}**: {char.xp} XP (+{amount})"
                           + (f" — Ready to level up! (`!levelup`)" if needed and char.xp >= needed else
                              f" — {needed - char.xp} XP to level {char.level + 1}" if needed else ""))

        save_campaign(campaign)
        await ctx.send("**XP Awarded!**\n" + "\n".join(results))

    @commands.command(name="levelup")
    async def level_up(self, ctx: commands.Context):
        """Level up your character if you have enough XP.

        Usage: !levelup
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        needed = xp_for_next_level(char.level)
        if not needed:
            await ctx.send(f"**{char.name}** is already at max level ({char.level})!")
            return
        if char.xp < needed:
            await ctx.send(f"**{char.name}** needs {needed - char.xp} more XP to reach level {char.level + 1}.")
            return

        old_level = char.level
        char.level += 1
        char.update_proficiency()

        # Roll HP increase
        hp_roll = roll_die(char.hit_die)
        con_mod = char.get_modifier("CON")
        hp_gain = max(hp_roll + con_mod, 1)
        # Hill Dwarf bonus
        if char.subrace and "Hill Dwarf" in char.subrace:
            hp_gain += 1

        char.max_hp += hp_gain
        char.current_hp += hp_gain
        char.hit_dice_remaining = char.level

        # Update spell slots for new level
        spell_msg = ""
        if is_spellcaster(char.char_class):
            old_slots = dict(char.spell_slots_max)
            char.update_spell_slots()
            if char.spell_slots_max != old_slots:
                new_slots = []
                for lvl in sorted(char.spell_slots_max, key=lambda x: int(x)):
                    old_count = old_slots.get(lvl, 0)
                    new_count = char.spell_slots_max[lvl]
                    if new_count > old_count:
                        new_slots.append(f"Lv{lvl}: {old_count}->{new_count}")
                    elif lvl not in old_slots:
                        new_slots.append(f"Lv{lvl}: NEW ({new_count})")
                if new_slots:
                    spell_msg = f"\nSpell Slots: {', '.join(new_slots)}"

        save_campaign(campaign)

        next_needed = xp_for_next_level(char.level)
        next_str = f"{next_needed - char.xp} XP to level {char.level + 1}" if next_needed else "Max level!"

        await ctx.send(
            f"**{char.name} LEVELS UP!** Level {old_level} -> **{char.level}**\n"
            f"HP Roll: d{char.hit_die} [{hp_roll}] + CON ({con_mod:+d}) = +{hp_gain} HP\n"
            f"Max HP: **{char.max_hp}** | Prof Bonus: +{char.proficiency_bonus}{spell_msg}\n"
            f"Next: {next_str}"
        )

    @commands.command(name="inspiration")
    async def inspiration(self, ctx: commands.Context, member: discord.Member = None):
        """DM grants inspiration to a player.

        Usage: !inspiration @player
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if campaign.dm_id != str(ctx.author.id):
            await ctx.send("Only the DM can grant inspiration.")
            return
        if not member:
            await ctx.send("Usage: `!inspiration @player`")
            return

        char = campaign.get_character(str(member.id))
        if not char:
            await ctx.send(f"{member.display_name} doesn't have a character.")
            return

        char.inspiration = True
        save_campaign(campaign)
        await ctx.send(f"**{char.name}** has been granted **Inspiration**!")

    @commands.command(name="deathsave")
    async def death_save(self, ctx: commands.Context):
        """Roll a death saving throw.

        Usage: !deathsave
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        if char.current_hp > 0:
            await ctx.send(f"**{char.name}** isn't at 0 HP. No death save needed!")
            return

        from bot.dice import roll_die
        roll = roll_die(20)

        if roll == 20:
            char.current_hp = 1
            char.death_saves = {"successes": 0, "failures": 0}
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** rolls a death save: **[{roll}] NAT 20!**\n"
                           f"**{char.name} regains consciousness with 1 HP!**")
            return

        if roll == 1:
            char.death_saves["failures"] += 2
        elif roll >= 10:
            char.death_saves["successes"] += 1
        else:
            char.death_saves["failures"] += 1

        save_campaign(campaign)

        succ = char.death_saves["successes"]
        fail = char.death_saves["failures"]
        result = "Success" if roll >= 10 else "Failure" + (" (x2 — nat 1!)" if roll == 1 else "")

        status = f"Successes: {'O' * succ}{'.' * (3 - succ)} | Failures: {'X' * fail}{'.' * (3 - fail)}"

        msg = f"**{char.name}** rolls a death save: **[{roll}]** — {result}\n{status}"

        if fail >= 3:
            msg += f"\n**{char.name} has died.** Rest in peace."
        elif succ >= 3:
            char.current_hp = 1
            char.death_saves = {"successes": 0, "failures": 0}
            save_campaign(campaign)
            msg += f"\n**{char.name} stabilizes** and regains 1 HP!"

        await ctx.send(msg)

    @commands.command(name="feat")
    async def feat(self, ctx: commands.Context, *, action: str = ""):
        """Add, remove, or list your feats.

        Usage: !feat (list your feats)
        Usage: !feat add Great Weapon Master
        Usage: !feat remove Great Weapon Master
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        if not action:
            if not char.feats:
                await ctx.send(f"**{char.name}** has no feats. Use `!feat add <name>` to add one.")
                return
            lines = [f"**{char.name}'s Feats:**"]
            for i, feat_name in enumerate(char.feats, 1):
                lines.append(f"  `{i}.` 🏅 {feat_name}")
            await ctx.send("\n".join(lines))
            return

        parts = action.split(None, 1)
        sub = parts[0].lower()

        if sub == "add" and len(parts) > 1:
            feat_name = parts[1].strip().title()
            if feat_name in char.feats:
                await ctx.send(f"**{char.name}** already has the feat **{feat_name}**.")
                return
            char.feats.append(feat_name)
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** gained the feat **{feat_name}**! 🏅")

        elif sub == "remove" and len(parts) > 1:
            feat_name = parts[1].strip().title()
            if feat_name in char.feats:
                char.feats.remove(feat_name)
                save_campaign(campaign)
                await ctx.send(f"Removed feat **{feat_name}** from **{char.name}**.")
            else:
                await ctx.send(f"**{char.name}** doesn't have the feat **{feat_name}**.")

        else:
            await ctx.send("Usage: `!feat`, `!feat add <name>`, or `!feat remove <name>`")

    @commands.command(name="modifier", aliases=["mod", "buff"])
    async def modifier_cmd(self, ctx: commands.Context, *, action: str = ""):
        """Add, remove, or list stat modifiers on your character.

        Modifiers represent magic items, buffs, equipment bonuses, etc.

        Usage: !modifier (list all modifiers)
        Usage: !modifier add <source> <stat> <+/-number>
        Usage: !modifier remove <source>

        Stats: STR, DEX, CON, INT, WIS, CHA, ac, hp, speed, or any skill name
        Examples:
          !modifier add Shield ac +2
          !modifier add Cloak of Protection ac +1
          !modifier add Gauntlets of Ogre Power STR +5
          !modifier add Boots of Elvenkind Stealth +5
          !modifier remove Shield
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        if not action:
            # List modifiers
            if not char.modifiers:
                await ctx.send(f"**{char.name}** has no active modifiers. Use `!modifier add <source> <stat> <+/-value>` to add one.")
                return
            lines = [f"**{char.name}'s Modifiers:**"]
            for source, bonuses in char.modifiers.items():
                bonus_strs = []
                for stat, val in bonuses.items():
                    sign = "+" if val >= 0 else ""
                    bonus_strs.append(f"{stat} {sign}{val}")
                lines.append(f"  `•` **{source}** — {', '.join(bonus_strs)}")
            lines.append(f"\n*Use `!modifier remove <source>` to remove.*")
            await ctx.send("\n".join(lines))
            return

        parts = action.split(None, 1)
        sub = parts[0].lower()

        if sub == "add" and len(parts) > 1:
            # Parse: <source name> <stat> <+/-number>
            # The last two tokens are stat and value, everything before is the source name
            tokens = parts[1].rsplit(None, 2)
            if len(tokens) < 3:
                await ctx.send(
                    "Usage: `!modifier add <source> <stat> <+/-value>`\n"
                    "Example: `!modifier add Shield ac +2`"
                )
                return

            source_name = tokens[0]
            stat_raw = tokens[1]
            val_raw = tokens[2]

            # Resolve stat
            stat = _resolve_stat(stat_raw)
            if not stat:
                await ctx.send(
                    f"Unknown stat: `{stat_raw}`\n"
                    f"Valid stats: STR, DEX, CON, INT, WIS, CHA, ac, hp, speed, "
                    f"or any skill name (Perception, Stealth, Athletics, etc.)"
                )
                return

            # Parse value
            try:
                value = int(val_raw)
            except ValueError:
                await ctx.send(f"Invalid value: `{val_raw}`. Use a number like `+2` or `-1`.")
                return

            # Add or update the modifier
            if source_name in char.modifiers:
                char.modifiers[source_name][stat] = value
            else:
                char.modifiers[source_name] = {stat: value}

            # Recalculate derived stats
            if stat in ("ac", "DEX", "CON", "WIS"):
                char.calc_ac()
            if stat == "hp":
                char.max_hp += value
                char.current_hp = min(char.current_hp + max(value, 0), char.max_hp)

            save_campaign(campaign)
            sign = "+" if value >= 0 else ""
            await ctx.send(f"**{char.name}** gained modifier: **{source_name}** ({stat} {sign}{value})")

        elif sub == "remove" and len(parts) > 1:
            source_name = parts[1].strip()
            # Try exact match first, then case-insensitive
            match_key = None
            for key in char.modifiers:
                if key == source_name:
                    match_key = key
                    break
            if not match_key:
                for key in char.modifiers:
                    if key.lower() == source_name.lower():
                        match_key = key
                        break

            if not match_key:
                await ctx.send(f"**{char.name}** doesn't have a modifier called **{source_name}**.")
                return

            removed = char.modifiers.pop(match_key)
            # Recalculate derived stats
            has_ac = any(s in ("ac", "DEX", "CON", "WIS") for s in removed)
            if has_ac:
                char.calc_ac()
            if "hp" in removed:
                hp_val = removed["hp"]
                char.max_hp -= hp_val
                char.current_hp = min(char.current_hp, char.max_hp)

            save_campaign(campaign)
            bonus_strs = []
            for stat, val in removed.items():
                sign = "+" if val >= 0 else ""
                bonus_strs.append(f"{stat} {sign}{val}")
            await ctx.send(f"Removed modifier **{match_key}** ({', '.join(bonus_strs)}) from **{char.name}**.")

        else:
            await ctx.send(
                "Usage: `!modifier`, `!modifier add <source> <stat> <value>`, "
                "or `!modifier remove <source>`"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ProgressionCog(bot))

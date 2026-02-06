"""Gameplay commands: action, IC, emote, OOC, look, inspect, talk, roll, check, save, attack."""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.data.rules import ABILITY_NAMES, ABILITY_FULL_NAMES, SKILLS, modifier_str
from bot.dice import parse_and_roll, roll_check
from bot.storage import load_campaign, save_campaign


class GameplayCog(commands.Cog, name="Gameplay"):
    """In-game commands for playing D&D."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx):
        return load_campaign(str(ctx.channel.id))

    def _require_active(self, campaign):
        return campaign and campaign.phase == CampaignPhase.ACTIVE

    async def _dm_respond(self, ctx, campaign, action_text: str, extra_context: str = ""):
        """Send action to Claude DM and post the response."""
        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_summary = char.short_summary() if char else ""

        async with ctx.typing():
            response = await self.bot.dm_engine.get_dm_response(
                campaign, action_text, ctx.author.display_name,
                char_summary, extra_context,
            )

        campaign.add_session_log(f"{ctx.author.display_name}: {action_text[:80]}")
        save_campaign(campaign)

        # Split long responses
        while len(response) > 1990:
            split_at = response.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await ctx.send(response[:split_at])
            response = response[split_at:].lstrip("\n")
        if response:
            await ctx.send(response)

    @commands.command(name="action")
    async def action(self, ctx: commands.Context, *, description: str):
        """Describe what your character does. The DM responds.

        Usage: !action I search the room for hidden doors
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign. The DM needs to `!startcampaign` first.")
            return
        await self._dm_respond(ctx, campaign, f"[ACTION] {description}")

    @commands.command(name="ic")
    async def in_character(self, ctx: commands.Context, *, dialogue: str):
        """Speak in character.

        Usage: !ic "Halt! Who goes there?"
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_name = char.name if char else ctx.author.display_name
        await self._dm_respond(ctx, campaign, f'[IN CHARACTER] {char_name} says: "{dialogue}"')

    @commands.command(name="emote")
    async def emote(self, ctx: commands.Context, *, description: str):
        """Describe your character's actions or expressions.

        Usage: !emote leans against the wall and crosses her arms
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_name = char.name if char else ctx.author.display_name
        await self._dm_respond(ctx, campaign, f"[EMOTE] *{char_name} {description}*")

    @commands.command(name="ooc")
    async def out_of_character(self, ctx: commands.Context, *, message: str):
        """Out-of-character chat. DM does NOT respond to this.

        Usage: !ooc brb getting snacks
        """
        char = None
        campaign = self._get_campaign(ctx)
        if campaign:
            char = campaign.get_character(str(ctx.author.id))
        name = char.name if char else ctx.author.display_name
        await ctx.send(f"**[OOC] {ctx.author.display_name}:** {message}")

    @commands.command(name="look")
    async def look(self, ctx: commands.Context):
        """Ask the DM to describe the current scene.

        Usage: !look
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        await self._dm_respond(ctx, campaign, "[LOOK] Describe the current scene and surroundings in detail.")

    @commands.command(name="inspect")
    async def inspect(self, ctx: commands.Context, *, target: str):
        """Examine something in the scene more closely.

        Usage: !inspect the old chest
        Usage: !inspect the strange rune on the wall
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        await self._dm_respond(ctx, campaign, f"[INSPECT] I examine {target} closely. What do I notice?")

    @commands.command(name="talk")
    async def talk(self, ctx: commands.Context, *, target: str):
        """Initiate conversation with an NPC. The DM roleplays them.

        Usage: !talk the bartender
        Usage: !talk Captain Aldric
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_name = char.name if char else ctx.author.display_name
        await self._dm_respond(ctx, campaign,
                               f"[TALK] {char_name} approaches and speaks to {target}. "
                               "Roleplay this NPC and their response.")

    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context, *, notation: str):
        """Roll dice using standard notation.

        Usage: !roll d20
        Usage: !roll 2d6+3
        Usage: !roll 4d6
        Usage: !roll d20+5
        """
        result = parse_and_roll(notation)
        if "error" in result:
            await ctx.send(result["error"])
            return

        await ctx.send(f"**{ctx.author.display_name}** rolls {notation}: {result['breakdown']}")

    @commands.command(name="check")
    async def ability_check(self, ctx: commands.Context, *, ability: str):
        """Make an ability check using your character's modifier.

        Usage: !check perception
        Usage: !check athletics
        Usage: !check STR
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character. Use `!createchar` first.")
            return

        ability = ability.strip()

        # Check if it's a skill
        skill_match = None
        for skill_name in SKILLS:
            if skill_name.lower() == ability.lower():
                skill_match = skill_name
                break
            if skill_name.lower().startswith(ability.lower()):
                skill_match = skill_name
                break

        # Check if it's an ability
        ab_match = None
        for ab in ABILITY_NAMES:
            if ab.lower() == ability.lower() or ABILITY_FULL_NAMES[ab].lower() == ability.lower():
                ab_match = ab
                break
            if ABILITY_FULL_NAMES[ab].lower().startswith(ability.lower()):
                ab_match = ab
                break

        if skill_match:
            mod = char.get_skill_modifier(skill_match)
            prof = " (proficient)" if skill_match in char.skill_proficiencies else ""
            result = roll_check(mod - char.proficiency_bonus if skill_match in char.skill_proficiencies else mod,
                                char.proficiency_bonus if skill_match in char.skill_proficiencies else 0)
            label = f"{skill_match} check{prof}"
        elif ab_match:
            mod = char.get_modifier(ab_match)
            result = roll_check(mod)
            label = f"{ABILITY_FULL_NAMES[ab_match]} check"
        else:
            await ctx.send(f"Unknown ability or skill: `{ability}`. Try a skill name (Perception, Athletics) or ability (STR, DEX).")
            return

        nat = ""
        if result["natural_20"]:
            nat = " **NAT 20!**"
        elif result["natural_1"]:
            nat = " *Nat 1...*"

        await ctx.send(f"**{char.name}** — {label}: {result['breakdown']}{nat}")

    @commands.command(name="save")
    async def saving_throw(self, ctx: commands.Context, *, ability: str):
        """Make a saving throw.

        Usage: !save DEX
        Usage: !save wisdom
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        ability = ability.strip()
        ab_match = None
        for ab in ABILITY_NAMES:
            if ab.lower() == ability.lower() or ABILITY_FULL_NAMES[ab].lower() == ability.lower():
                ab_match = ab
                break
            if ABILITY_FULL_NAMES[ab].lower().startswith(ability.lower()):
                ab_match = ab
                break

        if not ab_match:
            await ctx.send(f"Unknown ability: `{ability}`. Use STR, DEX, CON, INT, WIS, or CHA.")
            return

        mod = char.get_modifier(ab_match)
        prof = char.proficiency_bonus if ab_match in char.saving_throw_proficiencies else 0
        result = roll_check(mod, prof)
        prof_mark = " (proficient)" if prof else ""

        nat = ""
        if result["natural_20"]:
            nat = " **NAT 20!**"
        elif result["natural_1"]:
            nat = " *Nat 1...*"

        await ctx.send(f"**{char.name}** — {ABILITY_FULL_NAMES[ab_match]} saving throw{prof_mark}: {result['breakdown']}{nat}")

    @commands.command(name="attack")
    async def attack(self, ctx: commands.Context):
        """Make an attack roll (d20 + STR or DEX mod + proficiency).

        Usage: !attack
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        # Use highest of STR/DEX for attack (simple heuristic)
        str_mod = char.get_modifier("STR")
        dex_mod = char.get_modifier("DEX")
        # Finesse / ranged: use DEX if higher for Rogues, Monks, Rangers
        if char.char_class in ("Rogue", "Monk", "Ranger") or dex_mod > str_mod:
            attack_mod = dex_mod
            ab_used = "DEX"
        else:
            attack_mod = str_mod
            ab_used = "STR"

        total_mod = attack_mod + char.proficiency_bonus
        result = roll_check(attack_mod, char.proficiency_bonus)

        nat = ""
        if result["natural_20"]:
            nat = " **CRITICAL HIT!**"
        elif result["natural_1"]:
            nat = " *Critical miss!*"

        await ctx.send(
            f"**{char.name}** — Attack roll ({ab_used}): {result['breakdown']}{nat}\n"
            f"Tell the DM what you're attacking with `!action`"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GameplayCog(bot))

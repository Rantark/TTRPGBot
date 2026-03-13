"""Character creation and management cog with interactive step-by-step flow."""

import asyncio

import discord
from discord.ext import commands

from bot.models.character import Character
from bot.models.campaign import CampaignPhase, GameSystem
from bot.data.races import get_race_names, resolve_race, DRACONIC_ANCESTRIES, RACES
from bot.data.classes import get_class_names, get_class_data, CLASSES
from bot.data.backgrounds import get_background_names, get_background_data
from bot.data.rules import (
    ABILITY_NAMES, ABILITY_FULL_NAMES, STANDARD_ARRAY, SKILLS,
    POINT_BUY_COSTS, POINT_BUY_BUDGET, modifier_str, modifier,
    xp_for_next_level,
)
from bot.data.weapons import WEAPONS, CLASS_STARTING_WEAPONS
from bot.data.spell_lists import (
    CLASS_SPELL_LISTS, CLASS_STARTING_SPELLS, calculate_prepared_count,
)
from bot.data.spells import get_cantrips_known, is_spellcaster
from bot.dice import roll_ability_scores
from bot.storage import load_campaign, save_campaign


# Track creation state per user (user_id -> state dict)
# Each user can only have one creation session at a time.
# Session stores origin_channel_id so we know which campaign to save to.
_creation_sessions: dict[str, dict] = {}


def _get_session(user_id) -> dict | None:
    return _creation_sessions.get(str(user_id))


def _set_session(user_id, session: dict):
    _creation_sessions[str(user_id)] = session


def _clear_session(user_id):
    _creation_sessions.pop(str(user_id), None)


def _format_numbered_list(items: list[str], columns: int = 2) -> str:
    """Format items as a numbered list in columns."""
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"`{i:2d}.` {item}")
    # Simple single-column for clarity
    return "\n".join(lines)


# Emoji sets for character creation reactions
NUMBER_EMOJIS = [
    "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
    "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"
]
CONFIRM_EMOJIS = ["✅", "❌"]

# Edit-mode navigation emojis
NAV_PREV = "\u25c0\ufe0f"   # ◀️
NAV_NEXT = "\u25b6\ufe0f"   # ▶️
EDIT_PLUS = "\u2795"         # ➕
EDIT_MINUS = "\u2796"        # ➖
EDIT_SAVE = "\u2705"         # ✅
EDIT_TOGGLE = "\U0001f504"   # 🔄
EDIT_NAV_EMOJIS = [NAV_PREV, NAV_NEXT, EDIT_PLUS, EDIT_MINUS, EDIT_TOGGLE, EDIT_SAVE]

# Class emojis for flavor
CLASS_EMOJIS = {
    "Barbarian": "⚔️", "Bard": "🎵", "Cleric": "⛪", "Druid": "🌿",
    "Fighter": "🗡️", "Monk": "👊", "Paladin": "🛡️", "Ranger": "🏹",
    "Rogue": "🗡️", "Sorcerer": "✨", "Warlock": "🔮", "Wizard": "📖",
}

# Ability emojis
ABILITY_EMOJIS = {
    "STR": "💪", "DEX": "🏃", "CON": "❤️", "INT": "🧠", "WIS": "👁️", "CHA": "🗣️",
}

# Skill grouping by ability for display
SKILLS_BY_ABILITY = {}
for _sk, _ab in SKILLS.items():
    SKILLS_BY_ABILITY.setdefault(_ab, []).append(_sk)
for _ab in SKILLS_BY_ABILITY:
    SKILLS_BY_ABILITY[_ab].sort()


class CharacterCog(commands.Cog, name="Character"):
    """Commands for character creation and management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx: commands.Context):
        return load_campaign(str(ctx.channel.id))

    async def _send_with_reactions(self, ctx, header: str, options: list[str],
                                    display_options: list[str] = None,
                                    emojis: list[str] = None, expected_step: str = "",
                                    overflow: list[str] = None, allow_custom: bool = False):
        """Send an embed prompt with emoji reactions for selection.

        Adds reactions to the message and starts a background listener.
        When a reaction is clicked, routes the selection through _dispatch_step.
        Falls back to numbered list if more than 10 options.

        Args:
            options: The actual values sent to the step handler when selected.
            display_options: What's shown next to each emoji (defaults to options).
            emojis: Custom emoji set (defaults to NUMBER_EMOJIS).
            overflow: Extra options shown as text (user must type !cc).
            allow_custom: If True, hint that custom text input is accepted.
        """
        if len(options) > 10 or not options:
            # Too many for emojis — fall back to numbered list embed
            display = display_options or options
            opt_list = _format_numbered_list(display)
            embed = discord.Embed(
                description=f"{header}\n\n{opt_list}",
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Reply with: !cc <number or name>")
            await ctx.send(embed=embed)
            return

        if emojis is None:
            emojis = NUMBER_EMOJIS[:len(options)]
        else:
            emojis = emojis[:len(options)]

        display = display_options or options

        lines = []
        for emoji, label in zip(emojis, display):
            lines.append(f"{emoji} {label}")

        if overflow:
            lines.append(f"\nAlso available: {', '.join(overflow)}")
            lines.append("*Type `!cc <name>` to select these*")

        footer_text = "React to choose, or type !cc <name>"
        if allow_custom:
            footer_text = "React to choose, or type !cc <custom value>"

        embed = discord.Embed(
            description=f"{header}\n\n" + "\n".join(lines),
            color=discord.Color.blue(),
        )
        embed.set_footer(text=footer_text)
        msg = await ctx.send(embed=embed)

        # Add reactions
        for emoji in emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                pass

        # Start background reaction listener
        async def _listen():
            def check(reaction, user):
                return (
                    user.id == ctx.author.id
                    and reaction.message.id == msg.id
                    and str(reaction.emoji) in emojis
                )

            try:
                reaction, _ = await self.bot.wait_for(
                    "reaction_add", timeout=120.0, check=check
                )
                # Verify session is still on the expected step
                session = _get_session(ctx.author.id)
                if not session or session.get("step") != expected_step:
                    return
                idx = emojis.index(str(reaction.emoji))
                if idx < len(options):
                    await self._dispatch_step(ctx, options[idx])
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        session = _get_session(ctx.author.id)
        if session:
            old_task = session.get("_reaction_task")
            if old_task and not old_task.done():
                old_task.cancel()
            session["_reaction_task"] = asyncio.create_task(_listen())
            _set_session(ctx.author.id, session)

    async def _dispatch_step(self, ctx, choice: str):
        """Route a creation choice to the appropriate step handler."""
        session = _get_session(ctx.author.id)
        if not session:
            return
        step = session["step"]
        char = session["char"]

        if step == "name":
            await self._step_name(ctx, session, char, choice)
        elif step == "gender":
            await self._step_gender(ctx, session, char, choice)
        elif step == "race":
            await self._step_race(ctx, session, char, choice)
        elif step == "draconic_ancestry":
            await self._step_draconic_ancestry(ctx, session, char, choice)
        elif step == "half_elf_bonus":
            await self._step_half_elf_bonus(ctx, session, char, choice)
        elif step == "class":
            await self._step_class(ctx, session, char, choice)
        elif step == "ability_method":
            await self._step_ability_method(ctx, session, char, choice)
        elif step == "ability_assign":
            await self._step_ability_assign(ctx, session, char, choice)
        elif step == "point_buy":
            await self._step_point_buy(ctx, session, char, choice)
        elif step == "background":
            await self._step_background(ctx, session, char, choice)
        elif step == "skills":
            await self._step_skills(ctx, session, char, choice)
        elif step == "equipment":
            await self._step_equipment(ctx, session, char, choice)
        elif step == "weapons":
            await self._step_weapons(ctx, session, char, choice)
        elif step == "spells_cantrips":
            await self._step_spells_cantrips(ctx, session, char, choice)
        elif step == "spells_level1":
            await self._step_spells_level1(ctx, session, char, choice)
        elif step == "backstory":
            await self._step_backstory(ctx, session, char, choice)
        elif step == "confirm":
            await self._step_confirm(ctx, session, char, choice)

    # ------------------------------------------------------------------
    # Quick stat commands
    # ------------------------------------------------------------------

    @commands.command(name="ac")
    async def quick_ac(self, ctx: commands.Context):
        """Quickly display your AC.

        Usage: !ac
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")
        ac_parts = [f"**{char.name}** — AC: **{char.ac}**"]
        if isinstance(char.equipped, dict):
            armor = char.equipped.get("armor")
            shield = char.equipped.get("shield")
            sources = []
            if armor:
                sources.append(armor)
            elif char.char_class in ("Barbarian", "Monk"):
                sources.append("Unarmored Defense")
            else:
                sources.append("Unarmored")
            if shield:
                sources.append("Shield +2")
            ac_parts.append(f"({', '.join(sources)})")
        await ctx.send(" ".join(ac_parts))

    @commands.command(name="stats")
    async def quick_stats(self, ctx: commands.Context):
        """Quickly display ability scores.

        Usage: !stats
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")

        lines = [f"**{char.name}'s Ability Scores:**"]
        row1 = []
        row2 = []
        for i, ab in enumerate(ABILITY_NAMES):
            score = char.abilities.get(ab, 10)
            mod = modifier_str(score)
            entry = f"{ab} {score} ({mod})"
            if i < 3:
                row1.append(entry)
            else:
                row2.append(entry)
        lines.append(" | ".join(row1))
        lines.append(" | ".join(row2))
        await ctx.send("\n".join(lines))

    @commands.command(name="skills")
    async def quick_skills(self, ctx: commands.Context):
        """Quickly display all skill modifiers.

        Usage: !skills
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")

        # Group skills by ability
        skills_by_ab = {"STR": [], "DEX": [], "INT": [], "WIS": [], "CHA": []}
        for skill_name, ab in sorted(SKILLS.items()):
            if ab not in skills_by_ab:
                skills_by_ab[ab] = []
            mod = char.get_skill_modifier(skill_name)
            prof_mark = " *" if skill_name in char.skill_proficiencies else ""
            mod_s = f"+{mod}" if mod >= 0 else str(mod)
            skills_by_ab[ab].append(f"{skill_name} {mod_s}{prof_mark}")

        lines = [f"**{char.name}'s Skills:**"]
        for ab in ["STR", "DEX", "INT", "WIS", "CHA"]:
            if skills_by_ab.get(ab):
                lines.append(f"**{ab}:** {', '.join(skills_by_ab[ab])}")
        lines.append("*(* = proficient)*")
        await ctx.send("\n".join(lines))

    @commands.command(name="saves")
    async def quick_saves(self, ctx: commands.Context):
        """Quickly display saving throw modifiers.

        Usage: !saves
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")

        parts = []
        for ab in ABILITY_NAMES:
            mod = char.get_save_modifier(ab)
            mod_s = f"+{mod}" if mod >= 0 else str(mod)
            prof_mark = " *" if ab in char.saving_throw_proficiencies else ""
            parts.append(f"{ab} **{mod_s}**{prof_mark}")

        await ctx.send(f"**{char.name}'s Saving Throws:** {' | '.join(parts)}\n*(* = proficient)*")

    @commands.command(name="weapons")
    async def quick_weapons(self, ctx: commands.Context):
        """Quickly display equipped weapons with attack/damage bonuses.

        Usage: !weapons
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")

        if not char.weapons:
            return await ctx.send(f"**{char.name}** has no weapons equipped.")

        lines = [f"**{char.name}'s Weapons:**"]
        for w in char.weapons:
            is_finesse = w.get('finesse', False)
            is_ranged = w.get('category') == 'ranged'
            if is_finesse or is_ranged:
                ab_mod = char.get_modifier("DEX")
            else:
                ab_mod = char.get_modifier("STR")
            atk_bonus = ab_mod + char.proficiency_bonus
            atk_str = f"+{atk_bonus}" if atk_bonus >= 0 else str(atk_bonus)
            dmg_str = f"+{ab_mod}" if ab_mod >= 0 else str(ab_mod)
            props = f" | {', '.join(w['properties'])}" if w.get('properties') else ""
            lines.append(f"  **{w['name']}** — Attack: {atk_str} | Damage: {w['damage']}{dmg_str} {w['damage_type']}{props}")

        await ctx.send("\n".join(lines))

    # ------------------------------------------------------------------
    # Character creation
    # ------------------------------------------------------------------

    @commands.command(name="createchar")
    @commands.guild_only()
    async def create_char(self, ctx: commands.Context):
        """Start interactive character creation (sent to your DMs for privacy).

        Usage: !createchar
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel. Ask the DM to use `!newcampaign` first.")
            return
        # Redirect WoD campaigns to the WoD character creation
        if campaign.game_system == GameSystem.WOD:
            await ctx.send("This is a **World of Darkness** campaign! Use `!createwod` instead.")
            return
        if campaign.phase not in (CampaignPhase.SETUP, CampaignPhase.ACTIVE):
            await ctx.send("Campaign isn't in setup or active phase yet.")
            return

        player_id = str(ctx.author.id)
        existing = campaign.get_character(player_id)
        if existing and existing.creation_complete:
            await ctx.send(f"You already have a character: **{existing.name}**. "
                           "Use `!deletechar` to delete it first.")
            return

        # Start creation session — store origin channel for campaign lookup
        char = Character(player_id, ctx.author.display_name)
        session = {
            "step": "name",
            "char": char,
            "channel_id": str(ctx.channel.id),
            "guild_id": ctx.guild.id,
            "starting_level": campaign.starting_level,
        }
        _set_session(ctx.author.id, session)

        try:
            level_note = ""
            if campaign.starting_level > 1:
                level_note = f"\n⚔️ This campaign starts at **level {campaign.starting_level}**!\n"

            start_embed = discord.Embed(
                title="⚔️ Character Creation",
                description=(
                    "Let's build your character step by step.\n"
                    f"{level_note}\n"
                    "*Tip: Type `!cc restart` at any point to start over.*"
                ),
                color=discord.Color.blue(),
            )
            start_embed.add_field(
                name="📛 Step 1: Name",
                value="What is your character's name?\n`!cc <name>`\nExample: `!cc Thandril`",
                inline=False,
            )
            start_embed.set_footer(text="Step 1/12 — Character Creation")
            await ctx.author.send(embed=start_embed)
            await ctx.send(f"{ctx.author.mention} Check your DMs — character creation has started there!")
        except discord.Forbidden:
            _clear_session(ctx.author.id)
            await ctx.send("I can't DM you! Please enable DMs from server members and try again.")

    @commands.command(name="cc")
    async def creation_choice(self, ctx: commands.Context, *, choice: str = ""):
        """Make a choice during character creation (use in DMs).

        Usage: !cc <your choice>
        """
        session = _get_session(ctx.author.id)
        if not session:
            await ctx.send("No character creation in progress. Use `!createchar` in a server channel to start.")
            return

        # Cancel any pending reaction listener
        reaction_task = session.get("_reaction_task")
        if reaction_task and not reaction_task.done():
            reaction_task.cancel()
            session["_reaction_task"] = None

        # If used in a guild channel, redirect to DMs
        if ctx.guild is not None:
            await ctx.send(f"{ctx.author.mention} Character creation happens in DMs! Check your DMs and use `!cc` there.")
            return

        # Handle restart at any step
        if choice.strip().lower() == "restart":
            await self._restart_creation(ctx, session)
            return

        step = session["step"]
        char: Character = session["char"]

        if step == "name":
            await self._step_name(ctx, session, char, choice)
        elif step == "gender":
            await self._step_gender(ctx, session, char, choice)
        elif step == "race":
            await self._step_race(ctx, session, char, choice)
        elif step == "draconic_ancestry":
            await self._step_draconic_ancestry(ctx, session, char, choice)
        elif step == "half_elf_bonus":
            await self._step_half_elf_bonus(ctx, session, char, choice)
        elif step == "class":
            await self._step_class(ctx, session, char, choice)
        elif step == "ability_method":
            await self._step_ability_method(ctx, session, char, choice)
        elif step == "ability_assign":
            await self._step_ability_assign(ctx, session, char, choice)
        elif step == "point_buy":
            await self._step_point_buy(ctx, session, char, choice)
        elif step == "background":
            await self._step_background(ctx, session, char, choice)
        elif step == "skills":
            await self._step_skills(ctx, session, char, choice)
        elif step == "equipment":
            await self._step_equipment(ctx, session, char, choice)
        elif step == "weapons":
            await self._step_weapons(ctx, session, char, choice)
        elif step == "spells_cantrips":
            await self._step_spells_cantrips(ctx, session, char, choice)
        elif step == "spells_level1":
            await self._step_spells_level1(ctx, session, char, choice)
        elif step == "backstory":
            await self._step_backstory(ctx, session, char, choice)
        elif step == "confirm":
            await self._step_confirm(ctx, session, char, choice)
        else:
            await ctx.send("Unknown creation step. Use `!deletechar` and start over with `!createchar`.")

    async def _restart_creation(self, ctx, session):
        """Restart character creation from step 1, preserving campaign link."""
        channel_id = session.get("channel_id")
        guild_id = session.get("guild_id")
        starting_level = session.get("starting_level", 1)

        # Create fresh character and session
        char = Character(str(ctx.author.id), ctx.author.display_name)
        new_session = {
            "step": "name",
            "char": char,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "starting_level": starting_level,
        }
        _set_session(ctx.author.id, new_session)

        level_note = ""
        if starting_level > 1:
            level_note = f"\n⚔️ This campaign starts at **level {starting_level}**!\n"

        embed = discord.Embed(
            title="🔄 Character Creation Restarted!",
            description=f"Starting over from the beginning.{level_note}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📛 Step 1: Name",
            value="What is your character's name?\n`!cc <name>`\nExample: `!cc Thandril`",
            inline=False,
        )
        embed.set_footer(text="Step 1/12 — Character Creation")
        await ctx.send(embed=embed)

    async def _step_name(self, ctx, session, char: Character, choice: str):
        if not choice.strip():
            await ctx.send("Please provide a name: `!cc <name>`\nExample: `!cc Thandril`")
            return
        char.name = choice.strip()
        session["step"] = "gender"
        _set_session(ctx.author.id, session)

        await self._send_with_reactions(
            ctx,
            f"📛 Name: **{char.name}**\n\n**⚧️ Step 2: Gender**\nChoose your character's gender:",
            ["Male", "Female", "Non-binary"],
            emojis=["♂️", "♀️", "⚧️"],
            expected_step="gender",
            allow_custom=True,
        )

    async def _step_gender(self, ctx, session, char: Character, choice: str):
        if not choice.strip():
            await ctx.send("Please pick a gender: `!cc Male`, `!cc Female`, `!cc Non-binary`, or type your own.")
            return

        presets = {"1": "Male", "2": "Female", "3": "Non-binary"}
        char.gender = presets.get(choice.strip(), choice.strip())

        session["step"] = "race"
        _set_session(ctx.author.id, session)

        races = get_race_names()
        await self._send_with_reactions(
            ctx,
            f"⚧️ Gender: **{char.gender}**\n\n"
            f"**🧝 Step 3: Race**\n"
            f"Choose your character's race:\n"
            f"Each race grants ability score bonuses, traits, and languages.",
            races,
            expected_step="race",
        )

    async def _step_race(self, ctx, session, char: Character, choice: str):
        races = get_race_names()
        selected = self._resolve_choice(choice, races)
        if not selected:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(races)}) or type the race name.")
            return

        race_info = resolve_race(selected)
        if not race_info:
            await ctx.send("Could not resolve that race. Try again.")
            return

        char.race = race_info["race"]
        char.subrace = race_info["subrace"]
        char.racial_bonuses = race_info["ability_bonuses"]
        char.speed = race_info["speed"]
        char.traits = race_info["traits"]
        char.languages = race_info["languages"]

        # Dragonborn needs ancestry choice
        if char.race == "Dragonborn":
            session["step"] = "draconic_ancestry"
            _set_session(ctx.author.id, session)
            ancestries = list(DRACONIC_ANCESTRIES.keys())
            await self._send_with_reactions(
                ctx,
                "**Dragonborn Ancestry**\n"
                "Choose your draconic ancestry:\n"
                "This determines your breath weapon and damage resistance.",
                ancestries,
                expected_step="draconic_ancestry",
            )
            return

        # Half-Elf needs two +1 ability choices
        if char.race == "Half-Elf":
            session["step"] = "half_elf_bonus"
            session["half_elf_picks"] = []
            _set_session(ctx.author.id, session)
            abilities = [a for a in ABILITY_NAMES if a != "CHA"]
            ab_list = _format_numbered_list(abilities)
            await ctx.send(
                f"**Half-Elf Bonus Abilities**\n"
                f"Choose **2** ability scores to increase by +1 (other than CHA):\n{ab_list}\n\n"
                "Reply with two numbers or names: `!cc 1 3` or `!cc STR CON`"
            )
            return

        await self._show_race_summary_and_advance(ctx, session, char)

    async def _step_draconic_ancestry(self, ctx, session, char: Character, choice: str):
        ancestries = list(DRACONIC_ANCESTRIES.keys())
        selected = self._resolve_choice(choice, ancestries)
        if not selected:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(ancestries)}) or type the color.")
            return

        ancestry_data = DRACONIC_ANCESTRIES[selected]
        char.draconic_ancestry = selected
        char.traits.append(f"Breath Weapon: {ancestry_data['breath']} ({ancestry_data['damage_type']})")
        char.traits.append(f"Damage Resistance: {ancestry_data['damage_type']}")

        await self._show_race_summary_and_advance(ctx, session, char)

    async def _step_half_elf_bonus(self, ctx, session, char: Character, choice: str):
        abilities = [a for a in ABILITY_NAMES if a != "CHA"]
        parts = choice.upper().replace(",", " ").split()

        picks = []
        for part in parts:
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(abilities):
                    picks.append(abilities[idx])
            elif part in abilities:
                picks.append(part)

        if len(picks) != 2 or len(set(picks)) != 2:
            await ctx.send("Please choose exactly **2 different** abilities. Example: `!cc 1 3` or `!cc STR CON`")
            return

        for ab in picks:
            char.racial_bonuses[ab] = char.racial_bonuses.get(ab, 0) + 1
        char.half_elf_bonus_abilities = picks

        await self._show_race_summary_and_advance(ctx, session, char)

    async def _show_race_summary_and_advance(self, ctx, session, char: Character):
        """Show race summary and move to class selection."""
        race_display = char.subrace or char.race
        bonuses = ", ".join(f"{a} +{v}" for a, v in char.racial_bonuses.items())

        race_embed = discord.Embed(
            title=f"🧝 Race: {race_display}",
            color=discord.Color.blue(),
        )
        race_embed.add_field(name="📊 Ability Bonuses", value=bonuses, inline=True)
        race_embed.add_field(name="⚡ Speed", value=f"{char.speed} ft", inline=True)
        trait_display = "\n".join(f"• {t}" for t in char.traits[:6])
        if len(char.traits) > 6:
            trait_display += f"\n*...and {len(char.traits) - 6} more*"
        race_embed.add_field(name="🧬 Traits", value=trait_display, inline=False)
        await ctx.send(embed=race_embed)

        session["step"] = "class"
        _set_session(ctx.author.id, session)

        classes = get_class_names()
        emoji_classes = classes[:10]
        overflow_classes = classes[10:]

        display_list = []
        for cls_name in emoji_classes:
            data = CLASSES[cls_name]
            cls_emoji = CLASS_EMOJIS.get(cls_name, "⚔️")
            primary = data.get("primary_ability", "")
            display_list.append(f"{cls_emoji} **{cls_name}** ({primary}) — d{data['hit_die']} HP")

        overflow_display = []
        for cls_name in overflow_classes:
            data = CLASSES[cls_name]
            cls_emoji = CLASS_EMOJIS.get(cls_name, "⚔️")
            primary = data.get("primary_ability", "")
            overflow_display.append(f"{cls_emoji} {cls_name} ({primary}) — d{data['hit_die']} HP")

        await self._send_with_reactions(
            ctx,
            f"**{CLASS_EMOJIS.get(char.char_class, '⚔️')} Step 4: Class**\nChoose your class:",
            emoji_classes,
            display_options=display_list,
            expected_step="class",
            overflow=overflow_display if overflow_classes else None,
        )

    async def _step_class(self, ctx, session, char: Character, choice: str):
        classes = get_class_names()
        selected = self._resolve_choice(choice, classes)
        if not selected:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(classes)}) or type the class name.")
            return

        cls_name, cls_data = get_class_data(selected)
        char.char_class = cls_name
        char.hit_die = cls_data["hit_die"]
        char.saving_throw_proficiencies = list(cls_data["saving_throws"])
        char.armor_proficiencies = list(cls_data["armor_proficiencies"])
        char.weapon_proficiencies = list(cls_data["weapon_proficiencies"])
        # Set spellcasting ability if applicable
        if cls_data.get("spellcaster"):
            char.spellcasting_ability = cls_data.get("spellcasting_ability", "")

        session["class_data"] = cls_data
        session["step"] = "ability_method"
        _set_session(ctx.author.id, session)

        cls_emoji = CLASS_EMOJIS.get(cls_name, "⚔️")
        await self._send_with_reactions(
            ctx,
            f"{cls_emoji} **Class: {cls_name}** (d{cls_data['hit_die']})\n"
            f"*{cls_data['description']}*\n\n"
            f"**📊 Step 5: Ability Scores**\n"
            f"Choose how to generate your ability scores:",
            ["roll", "standard", "point buy"],
            display_options=[
                f"**Roll** — Roll 4d6, drop lowest, 6 times",
                f"**Standard Array** — Use preset scores {STANDARD_ARRAY}",
                f"**Point Buy** — Spend 27 points to customize (scores 8-15)",
            ],
            emojis=["🎲", "📊", "🧮"],
            expected_step="ability_method",
        )

    async def _step_ability_method(self, ctx, session, char: Character, choice: str):
        choice = choice.strip()

        if choice in ("1", "roll"):
            # Roll 4d6 drop lowest — reroll if no score is 15+ or any score is under 8
            MAX_REROLLS = 10
            reroll_count = 0
            while True:
                results = roll_ability_scores()
                scores = [r[0] for r in results]
                if max(scores) >= 15 and min(scores) >= 8:
                    break
                if reroll_count >= MAX_REROLLS:
                    break
                reroll_count += 1

            details = []
            for total, rolls in results:
                dropped = min(rolls)
                detail_rolls = []
                dropped_shown = False
                for r in rolls:
                    if r == dropped and not dropped_shown:
                        detail_rolls.append(f"~~{r}~~")
                        dropped_shown = True
                    else:
                        detail_rolls.append(str(r))
                details.append(f"[{', '.join(detail_rolls)}] = **{total}**")

            session["rolled_scores"] = scores
            session["step"] = "ability_assign"
            _set_session(ctx.author.id, session)

            detail_str = "\n".join(f"  Roll {i+1}: {d}" for i, d in enumerate(details))
            reroll_note = f"\n*Rerolled {reroll_count} time(s) — requires at least one 15+ and no scores under 8*\n" if reroll_count > 0 else ""
            await ctx.send(
                f"**Rolled Ability Scores:**\n{detail_str}\n"
                f"{reroll_note}\n"
                f"Your scores: **{scores}**\n\n"
                f"Assign them to abilities in order (STR DEX CON INT WIS CHA):\n"
                f"Reply with: `!cc {' '.join(str(s) for s in scores)}`\n"
                f"(Rearrange the numbers however you want)"
            )

        elif choice in ("2", "standard", "array", "standard array"):
            session["rolled_scores"] = list(STANDARD_ARRAY)
            session["step"] = "ability_assign"
            _set_session(ctx.author.id, session)

            await ctx.send(
                f"**Standard Array:** {STANDARD_ARRAY}\n\n"
                f"Assign them to abilities in order (STR DEX CON INT WIS CHA):\n"
                f"Reply with: `!cc 15 14 13 12 10 8`\n"
                f"(Rearrange the numbers however you want)"
            )

        elif choice in ("3", "point", "buy", "point buy"):
            session["point_buy_scores"] = {a: 8 for a in ABILITY_NAMES}
            session["point_buy_remaining"] = POINT_BUY_BUDGET
            session["step"] = "point_buy"
            _set_session(ctx.author.id, session)

            await self._show_point_buy(ctx, session)

        else:
            await ctx.send(
                "Choose `1` (Roll), `2` (Standard Array), or `3` (Point Buy).\n"
                "Example: `!cc roll` or `!cc 2`"
            )

    async def _step_ability_assign(self, ctx, session, char: Character, choice: str):
        available = sorted(session["rolled_scores"], reverse=True)
        parts = choice.replace(",", " ").split()

        try:
            values = [int(p) for p in parts]
        except ValueError:
            await ctx.send(f"Enter 6 numbers from your available scores: {available}")
            return

        if len(values) != 6:
            await ctx.send(f"Need exactly 6 scores. Your available scores: {available}")
            return

        if sorted(values) != sorted(available):
            await ctx.send(f"Those don't match your available scores: {available}")
            return

        for i, ab in enumerate(ABILITY_NAMES):
            char.abilities[ab] = values[i]

        # Apply racial bonuses
        for ab, bonus in char.racial_bonuses.items():
            char.abilities[ab] += bonus

        await self._show_abilities_and_advance_to_background(ctx, session, char)

    async def _show_point_buy(self, ctx, session):
        scores = session["point_buy_scores"]
        remaining = session["point_buy_remaining"]

        lines = ["**Point Buy** — Budget remaining: **{0}**".format(remaining)]
        for i, ab in enumerate(ABILITY_NAMES, 1):
            score = scores[ab]
            mod = modifier_str(score)
            lines.append(f"  `{i}.` {ABILITY_FULL_NAMES[ab]:14s} {score:2d} ({mod})")

        lines.append("\nTo adjust: `!cc <ability#> <new_score>` (e.g., `!cc 1 15` to set STR to 15)")
        lines.append("Scores must be 8-15. When happy: `!cc done`")
        lines.append(f"\nCost table: " + " | ".join(f"{s}={c}" for s, c in POINT_BUY_COSTS.items()))

        await ctx.send("\n".join(lines))

    async def _step_point_buy(self, ctx, session, char: Character, choice: str):
        if choice.strip().lower() == "done":
            remaining = session["point_buy_remaining"]
            if remaining < 0:
                await ctx.send(f"You're over budget by {abs(remaining)} points! Reduce some scores.")
                return

            for ab in ABILITY_NAMES:
                char.abilities[ab] = session["point_buy_scores"][ab]
            # Apply racial bonuses
            for ab, bonus in char.racial_bonuses.items():
                char.abilities[ab] += bonus
            await self._show_abilities_and_advance_to_background(ctx, session, char)
            return

        parts = choice.replace(",", " ").split()
        if len(parts) != 2:
            await ctx.send("Format: `!cc <ability#> <score>` or `!cc done` when finished.")
            return

        try:
            ab_idx = int(parts[0]) - 1
            new_score = int(parts[1])
        except ValueError:
            await ctx.send("Format: `!cc <ability#> <score>` (e.g., `!cc 1 15`)")
            return

        if ab_idx < 0 or ab_idx >= 6:
            await ctx.send("Ability number must be 1-6.")
            return
        if new_score not in POINT_BUY_COSTS:
            await ctx.send(f"Score must be 8-15. Cost table: " +
                           " | ".join(f"{s}={c}" for s, c in POINT_BUY_COSTS.items()))
            return

        ab = ABILITY_NAMES[ab_idx]
        old_score = session["point_buy_scores"][ab]
        old_cost = POINT_BUY_COSTS[old_score]
        new_cost = POINT_BUY_COSTS[new_score]

        session["point_buy_remaining"] += old_cost - new_cost
        session["point_buy_scores"][ab] = new_score
        _set_session(ctx.author.id, session)

        await self._show_point_buy(ctx, session)

    async def _show_abilities_and_advance_to_background(self, ctx, session, char: Character):
        ab_embed = discord.Embed(
            title="📊 Final Ability Scores",
            description="*(racial bonuses applied)*",
            color=discord.Color.green(),
        )
        for ab in ABILITY_NAMES:
            score = char.abilities[ab]
            bonus = char.racial_bonuses.get(ab, 0)
            bonus_str = f" (+{bonus} racial)" if bonus else ""
            emoji = ABILITY_EMOJIS.get(ab, "")
            ab_embed.add_field(
                name=f"{emoji} {ABILITY_FULL_NAMES[ab]}",
                value=f"**{score}** ({modifier_str(score)}){bonus_str}",
                inline=True,
            )
        await ctx.send(embed=ab_embed)

        session["step"] = "background"
        _set_session(ctx.author.id, session)

        backgrounds = get_background_names()
        emoji_bgs = backgrounds[:10]
        overflow_bgs = backgrounds[10:]

        await self._send_with_reactions(
            ctx,
            "**📜 Step 6: Background**\n"
            "Choose your background (grants 2 skill proficiencies):",
            emoji_bgs,
            expected_step="background",
            overflow=overflow_bgs if overflow_bgs else None,
        )

    async def _step_background(self, ctx, session, char: Character, choice: str):
        backgrounds = get_background_names()
        selected = self._resolve_choice(choice, backgrounds)
        if not selected:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(backgrounds)}) or type the background name.")
            return

        bg_name, bg_data = get_background_data(selected)
        char.background = bg_name

        # Add background skill proficiencies
        for skill in bg_data["skill_proficiencies"]:
            if skill not in char.skill_proficiencies:
                char.skill_proficiencies.append(skill)

        # Add tool proficiencies
        for tool in bg_data.get("tool_proficiencies", []):
            char.tool_proficiencies.append(tool)

        char.features.append(bg_data["feature"])

        # Now choose class skills
        cls_data = session["class_data"]
        # Filter out skills already granted by background
        available_skills = [s for s in cls_data["skill_choices"] if s not in char.skill_proficiencies]
        num_skills = cls_data["num_skills"]

        session["available_skills"] = available_skills
        session["num_skills"] = num_skills
        session["step"] = "skills"
        _set_session(ctx.author.id, session)

        skill_list = _format_numbered_list(available_skills)
        already = ", ".join(char.skill_proficiencies) if char.skill_proficiencies else "None"

        bg_embed = discord.Embed(
            title=f"📜 Background: {bg_name}",
            description=f"*{bg_data['description']}*",
            color=discord.Color.blue(),
        )
        bg_embed.add_field(name="⭐ Feature", value=bg_data['feature'], inline=False)
        bg_embed.add_field(name="📚 Skills Gained", value=", ".join(bg_data['skill_proficiencies']), inline=True)
        await ctx.send(embed=bg_embed)

        skills_embed = discord.Embed(
            title=f"📚 Step 7: Class Skills",
            description=(
                f"Already proficient: {already}\n"
                f"Choose **{num_skills}** from:\n\n{skill_list}"
            ),
            color=discord.Color.blue(),
        )
        skills_embed.set_footer(text="Reply with numbers: !cc 1 3 or names: !cc Athletics Perception")
        await ctx.send(embed=skills_embed)

    async def _step_skills(self, ctx, session, char: Character, choice: str):
        available = session["available_skills"]
        num_needed = session["num_skills"]
        parts = choice.replace(",", " ").split()

        picks = []
        for part in parts:
            part = part.strip()
            resolved = self._resolve_choice(part, available)
            if resolved:
                picks.append(resolved)

        # Deduplicate
        picks = list(dict.fromkeys(picks))

        if len(picks) != num_needed:
            await ctx.send(f"Choose exactly **{num_needed}** skills. Try again.")
            return

        for skill in picks:
            if skill not in char.skill_proficiencies:
                char.skill_proficiencies.append(skill)

        # Advance to equipment selection
        cls_data = session["class_data"]
        equip_options = cls_data.get("starting_equipment", [])

        # Separate choices (lists) from fixed items (strings)
        choices = []
        fixed_items = []
        for item in equip_options:
            if isinstance(item, list):
                choices.append(item)
            else:
                fixed_items.append(item)

        session["equip_choices"] = choices
        session["equip_fixed"] = fixed_items
        session["equip_picks"] = []
        session["equip_index"] = 0
        session["step"] = "equipment"
        _set_session(ctx.author.id, session)

        await self._show_equipment_choice(ctx, session, char)

    async def _show_equipment_choice(self, ctx, session, char: Character):
        """Show the current equipment choice or advance past equipment."""
        choices = session["equip_choices"]
        idx = session["equip_index"]

        if idx >= len(choices):
            # All choices made — assemble final equipment list
            all_items = list(session["equip_picks"]) + list(session["equip_fixed"])
            char.inventory = all_items

            equip_display = "\n".join(f"  {item}" for item in all_items)

            # Move to weapon selection
            session["step"] = "weapons"
            session["weapon_choices"] = CLASS_STARTING_WEAPONS.get(char.char_class, [])
            session["weapon_index"] = 0
            session["weapon_picks"] = []
            _set_session(ctx.author.id, session)

            await ctx.send(f"**Starting Equipment:**\n{equip_display}")
            await self._show_weapon_choice(ctx, session, char)
            return

        current_choice = choices[idx]
        choice_num = idx + 1
        total = len(choices)

        await self._send_with_reactions(
            ctx,
            f"**Step 8: Starting Equipment** (choice {choice_num}/{total})\nPick one:",
            current_choice,
            expected_step="equipment",
        )

    async def _step_equipment(self, ctx, session, char: Character, choice: str):
        choices = session["equip_choices"]
        idx = session["equip_index"]

        if idx >= len(choices):
            # Shouldn't happen, but advance
            await self._show_equipment_choice(ctx, session, char)
            return

        current_choice = choices[idx]
        selected = self._resolve_choice(choice.strip(), current_choice)
        if not selected:
            await ctx.send(f"Pick a number (1-{len(current_choice)}) or type the item name.")
            return

        session["equip_picks"].append(selected)
        session["equip_index"] = idx + 1
        _set_session(ctx.author.id, session)

        await self._show_equipment_choice(ctx, session, char)

    # ------------------------------------------------------------------
    # Weapon selection step
    # ------------------------------------------------------------------

    async def _show_weapon_choice(self, ctx, session, char: Character):
        """Show weapon choice or advance to spells."""
        weapon_choices = session.get("weapon_choices", [])
        idx = session.get("weapon_index", 0)

        if idx >= len(weapon_choices):
            # Done with weapons — move to spells
            await self._advance_to_spells(ctx, session, char)
            return

        choice_group = weapon_choices[idx]
        label = choice_group["label"]
        options = choice_group["options"]

        # Build display labels and weapon names for reactions
        weapon_names = []
        display_labels = []
        for weapon_key in options:
            w = WEAPONS.get(weapon_key)
            if w:
                props = f" ({', '.join(w['properties'])})" if w.get('properties') else ""
                weapon_names.append(w['name'])
                display_labels.append(f"**{w['name']}** — {w['damage']} {w['damage_type']}{props}")
            else:
                weapon_names.append(weapon_key)
                display_labels.append(weapon_key)

        header = f"**Step 9: Weapon Selection** ({label})\nChoose your weapon:"
        if idx > 0:
            picked_names = [w.get('name', '?') for w in session.get("weapon_picks", [])]
            if picked_names:
                header += f"\nAlready chosen: {', '.join(picked_names)}"

        await self._send_with_reactions(
            ctx,
            header,
            weapon_names,
            display_options=display_labels,
            expected_step="weapons",
        )

    async def _step_weapons(self, ctx, session, char: Character, choice: str):
        weapon_choices = session.get("weapon_choices", [])
        idx = session.get("weapon_index", 0)

        if idx >= len(weapon_choices):
            await self._advance_to_spells(ctx, session, char)
            return

        options = weapon_choices[idx]["options"]

        # Try as number
        selected_key = None
        choice = choice.strip()
        if choice.isdigit():
            num = int(choice) - 1
            if 0 <= num < len(options):
                selected_key = options[num]
        else:
            # Try matching by name
            for key in options:
                w = WEAPONS.get(key)
                if w and w['name'].lower() == choice.lower():
                    selected_key = key
                    break
                if key.lower() == choice.lower():
                    selected_key = key
                    break

        if not selected_key:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(options)}).")
            return

        weapon_data = WEAPONS.get(selected_key)
        if not weapon_data:
            await ctx.send(f"Weapon not found: {selected_key}. Try again.")
            return

        session["weapon_picks"].append(dict(weapon_data))
        session["weapon_index"] = idx + 1
        _set_session(ctx.author.id, session)

        await ctx.send(f"Selected: **{weapon_data['name']}**")
        await self._show_weapon_choice(ctx, session, char)

    # ------------------------------------------------------------------
    # Spell selection step
    # ------------------------------------------------------------------

    async def _advance_to_spells(self, ctx, session, char: Character):
        """Check if class gets spells and set up spell selection.

        At level 1, Paladins/Rangers don't get spells.
        At level 2+, they do — so we check the campaign's starting level.
        """
        # Assign weapons to character
        char.weapons = session.get("weapon_picks", [])

        starting_level = session.get("starting_level", 1)
        spell_info = CLASS_STARTING_SPELLS.get(char.char_class)
        spell_list = CLASS_SPELL_LISTS.get(char.char_class)

        # Determine if this class gets spells at the starting level
        is_half_caster = char.char_class in ('Paladin', 'Ranger')
        has_spells = False

        if spell_info and spell_list:
            if spell_info['spell_type'] != 'none':
                has_spells = True
            elif is_half_caster and starting_level >= 2:
                # Half-casters gain spells at level 2
                has_spells = True

        if not has_spells:
            await self._advance_to_backstory(ctx, session, char)
            return

        # Determine cantrips needed
        cantrips_count = spell_info['cantrips']
        if cantrips_count > 0 and spell_list.get('cantrips'):
            session["cantrips_needed"] = cantrips_count
            session["cantrips_available"] = list(spell_list['cantrips'])
            session["cantrips_picked"] = []
        else:
            session["cantrips_needed"] = 0
            session["cantrips_available"] = []
            session["cantrips_picked"] = []

        # Calculate spells needed
        effective_level = starting_level
        if is_half_caster and starting_level >= 2:
            # Half-casters: Paladin uses WIS, Ranger uses known spells
            if char.char_class == 'Paladin':
                wis_mod = modifier(char.abilities.get("WIS", 10))
                session["spells_needed"] = max(1, wis_mod + (effective_level // 2))
                session["spell_type"] = "prepared"
            else:
                # Ranger: known spells — 2 at level 2, +1 per level after
                session["spells_needed"] = 2 + max(0, effective_level - 2)
                session["spell_type"] = "known"
        elif spell_info['spell_type'] == 'known':
            session["spells_needed"] = spell_info['spells']
        elif spell_info['spell_type'] == 'prepared':
            wis_mod = modifier(char.abilities.get("WIS", 10))
            int_mod = modifier(char.abilities.get("INT", 10))
            session["spells_needed"] = calculate_prepared_count(char.char_class, effective_level, wis_mod, int_mod)
        elif spell_info['spell_type'] == 'spellbook':
            session["spells_needed"] = spell_info['spells']  # 6 for wizard
        else:
            session["spells_needed"] = 0

        if not is_half_caster:
            session["spell_type"] = spell_info['spell_type']

        session["spells_available"] = list(spell_list['level_1'])
        session["spells_picked"] = []

        # If there are cantrips to pick, start there; otherwise go to level 1 spells
        if session["cantrips_needed"] > 0:
            session["step"] = "spells_cantrips"
            _set_session(ctx.author.id, session)
            await self._show_cantrip_choice(ctx, session, char)
        elif session["spells_needed"] > 0 and session["spells_available"]:
            session["step"] = "spells_level1"
            _set_session(ctx.author.id, session)
            await self._show_spell_choice(ctx, session, char)
        else:
            await self._advance_to_backstory(ctx, session, char)

    async def _show_cantrip_choice(self, ctx, session, char: Character):
        needed = session["cantrips_needed"]
        picked = session["cantrips_picked"]
        available = [c for c in session["cantrips_available"] if c not in picked]

        if len(picked) >= needed:
            # Move to level 1 spells
            if session.get("spells_needed", 0) > 0 and session.get("spells_available"):
                session["step"] = "spells_level1"
                _set_session(ctx.author.id, session)
                await self._show_spell_choice(ctx, session, char)
            else:
                await self._finalize_spells(ctx, session, char)
            return

        header = (
            f"**Step 10: Spell Selection — Cantrips**\n"
            f"Choose {needed} cantrips for your {char.char_class}.\n"
            f"Progress: {len(picked)}/{needed} chosen"
        )
        if picked:
            header += f"\nChosen so far: {', '.join(picked)}"

        if len(available) <= 10:
            await self._send_with_reactions(
                ctx, header, available, expected_step="spells_cantrips",
            )
        else:
            # Too many for emojis — fall back to numbered list
            opt_list = _format_numbered_list(available)
            await ctx.send(f"{header}\n\n{opt_list}\n\nReply with: `!cc <number>`")

    async def _step_spells_cantrips(self, ctx, session, char: Character, choice: str):
        picked = session["cantrips_picked"]
        available = [c for c in session["cantrips_available"] if c not in picked]

        choice = choice.strip()
        selected = None
        if choice.isdigit():
            num = int(choice) - 1
            if 0 <= num < len(available):
                selected = available[num]
        else:
            # Try matching by name
            for c in available:
                if c.lower() == choice.lower() or c.lower().startswith(choice.lower()):
                    selected = c
                    break

        if not selected:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(available)}).")
            return

        session["cantrips_picked"].append(selected)
        _set_session(ctx.author.id, session)

        await ctx.send(f"Added cantrip: **{selected}**")
        await self._show_cantrip_choice(ctx, session, char)

    async def _show_spell_choice(self, ctx, session, char: Character):
        needed = session["spells_needed"]
        picked = session["spells_picked"]
        available = [s for s in session["spells_available"] if s not in picked]

        if len(picked) >= needed:
            await self._finalize_spells(ctx, session, char)
            return

        spell_type = session.get("spell_type", "known")
        if spell_type == "prepared":
            type_desc = f"You know all {char.char_class} spells. Choose {needed} to prepare."
        elif spell_type == "spellbook":
            type_desc = f"Choose {needed} spells to add to your spellbook."
        else:
            type_desc = f"Choose {needed} 1st-level spells."

        header = (
            f"**Step 10: Spell Selection — 1st Level Spells**\n"
            f"{type_desc}\n"
            f"Progress: {len(picked)}/{needed} chosen"
        )
        if picked:
            header += f"\nChosen so far: {', '.join(picked)}"

        if len(available) <= 10:
            await self._send_with_reactions(
                ctx, header, available, expected_step="spells_level1",
            )
        else:
            # Too many for emojis — fall back to numbered list
            opt_list = _format_numbered_list(available)
            await ctx.send(f"{header}\n\n{opt_list}\n\nReply with: `!cc <number>`")

    async def _step_spells_level1(self, ctx, session, char: Character, choice: str):
        picked = session["spells_picked"]
        available = [s for s in session["spells_available"] if s not in picked]

        choice = choice.strip()
        selected = None
        if choice.isdigit():
            num = int(choice) - 1
            if 0 <= num < len(available):
                selected = available[num]
        else:
            for s in available:
                if s.lower() == choice.lower() or s.lower().startswith(choice.lower()):
                    selected = s
                    break

        if not selected:
            await ctx.send(f"Invalid choice. Pick a number (1-{len(available)}).")
            return

        session["spells_picked"].append(selected)
        _set_session(ctx.author.id, session)

        await ctx.send(f"Added spell: **{selected}**")
        await self._show_spell_choice(ctx, session, char)

    async def _finalize_spells(self, ctx, session, char: Character):
        """Save spell selections to character and advance."""
        cantrips = session.get("cantrips_picked", [])
        spells = session.get("spells_picked", [])
        spell_type = session.get("spell_type", "known")
        starting_level = session.get("starting_level", 1)

        char.cantrips = cantrips

        if spell_type == "known":
            char.known_spells = spells
            # Known casters have all their spells "prepared" automatically
            char.prepared_spells = list(spells)
        elif spell_type == "prepared":
            # Cleric/Druid/Paladin: know all class spells, prepare a subset
            char.known_spells = list(session.get("spells_available", []))
            char.prepared_spells = spells
        elif spell_type == "spellbook":
            # Wizard: spellbook holds known spells, prepare a subset
            wis_mod = modifier(char.abilities.get("WIS", 10))
            int_mod = modifier(char.abilities.get("INT", 10))
            num_prepared = calculate_prepared_count(char.char_class, starting_level, wis_mod, int_mod)
            char.known_spells = spells
            char.prepared_spells = spells[:num_prepared]

        await self._advance_to_backstory(ctx, session, char)

    async def _advance_to_backstory(self, ctx, session, char: Character):
        """Move to backstory step."""
        session["step"] = "backstory"
        _set_session(ctx.author.id, session)

        await ctx.send(
            f"**Step 11: Backstory** *(optional)*\n"
            f"Write a short backstory for **{char.name}** (1-3 sentences).\n"
            f"This helps the DM weave your character into the story.\n\n"
            f"Reply with: `!cc <your backstory>` or `!cc skip` to skip"
        )

    async def _step_backstory(self, ctx, session, char: Character, choice: str):
        if not choice.strip():
            await ctx.send("Write a short backstory or `!cc skip` to skip.")
            return

        if choice.strip().lower() != "skip":
            char.backstory = choice.strip()

        # Set starting armor based on class
        from bot.data.armor import CLASS_STARTING_ARMOR, CLASS_STARTING_SHIELD
        armor = CLASS_STARTING_ARMOR.get(char.char_class)
        if armor:
            char.equipped["armor"] = armor
        if CLASS_STARTING_SHIELD.get(char.char_class):
            char.equipped["shield"] = True

        # Finalize character at the campaign's starting level
        starting_level = session.get("starting_level", 1)
        char.finalize(starting_level=starting_level)

        session["step"] = "confirm"
        _set_session(ctx.author.id, session)

        # Send preview embeds
        preview_embeds = self._build_sheet_embeds(char)
        for embed in preview_embeds:
            await ctx.send(embed=embed)

        await self._send_with_reactions(
            ctx,
            "**✅ Confirm this character?**",
            ["yes", "no"],
            display_options=["Confirm — Save this character", "Start Over — Delete and redo"],
            emojis=CONFIRM_EMOJIS,
            expected_step="confirm",
        )

    async def _step_confirm(self, ctx, session, char: Character, choice: str):
        choice = choice.strip().lower()
        if choice in ("yes", "y", "confirm"):
            # Load campaign from the original guild channel
            channel_id = session.get("channel_id", str(ctx.channel.id))
            campaign = load_campaign(channel_id)
            if not campaign:
                await ctx.send("Campaign not found. Something went wrong.")
                _clear_session(ctx.author.id)
                return

            campaign.add_character(str(ctx.author.id), char)
            save_campaign(campaign)
            _clear_session(ctx.author.id)

            cls_emoji = CLASS_EMOJIS.get(char.char_class, "⚔️")
            saved_embed = discord.Embed(
                title=f"✅ {char.name} Created!",
                description=(
                    f"{cls_emoji} Level {char.level} {char.subrace or char.race} {char.char_class}\n\n"
                    f"📋 Use `!sheet` in the server channel to view your sheet.\n"
                    f"✏️ Use `!dndedit` to adjust stats with emojis.\n"
                    f"🎒 Use `!equipment` to manage inventory.\n"
                    f"🎲 Use `!roll` to make dice rolls."
                ),
                color=discord.Color.green(),
            )
            await ctx.send(embed=saved_embed)

            # Announce in the original guild channel
            try:
                guild_channel = self.bot.get_channel(int(channel_id))
                if guild_channel:
                    announce_embed = discord.Embed(
                        title=f"{cls_emoji} New Adventurer Joins!",
                        description=(
                            f"**{char.name}** ({char.subrace or char.race} {char.char_class}) "
                            f"has joined the party!\nCreated by {ctx.author.mention}."
                        ),
                        color=discord.Color.blue(),
                    )
                    await guild_channel.send(embed=announce_embed)
            except Exception:
                pass  # Don't fail if announcement doesn't work

        elif choice in ("no", "n", "restart"):
            _clear_session(ctx.author.id)
            await ctx.send("Character creation cancelled. Use `!createchar` in a server channel to start over.")
        else:
            await ctx.send("Reply `!cc yes` to confirm or `!cc no` to start over.")

    @commands.command(name="equipment", aliases=["inv", "inventory"])
    async def equipment(self, ctx: commands.Context, *, action: str = ""):
        """View or manage your equipment/inventory.

        Usage: !equipment (view your gear)
        Usage: !equipment add Rope (50 ft)
        Usage: !equipment remove Rope (50 ft)
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
            lines = [f"**{char.name}'s Inventory:**"]
            if char.gold:
                lines.append(f"  💰 **Gold:** {char.gold} gp")
            # Show equipped items
            if isinstance(char.equipped, dict):
                equipped_items = []
                if char.equipped.get("armor"):
                    equipped_items.append(f"Armor: {char.equipped['armor']}")
                if char.equipped.get("shield"):
                    equipped_items.append("Shield")
                if equipped_items:
                    lines.append(f"  🛡 **Equipped:** {', '.join(equipped_items)}")
            if not char.inventory and not char.gold:
                lines.append("  *Empty inventory*")
                lines.append("Use `!equipment add <item>` to add items.")
            else:
                for i, item in enumerate(char.inventory, 1):
                    lines.append(f"  `{i}.` {char._format_inv_item(item)}")
            await ctx.send("\n".join(lines))
            return

        parts = action.split(None, 1)
        sub = parts[0].lower()

        if sub == "add" and len(parts) > 1:
            item_name = parts[1].strip()
            char.inventory.append(item_name)
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** added **{item_name}** to inventory.")

        elif sub == "remove" and len(parts) > 1:
            target = parts[1].strip()
            # Try as number first
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(char.inventory):
                    removed = char.inventory.pop(idx)
                    save_campaign(campaign)
                    await ctx.send(f"**{char.name}** removed **{removed}** from inventory.")
                else:
                    await ctx.send(f"Invalid item number. Use 1-{len(char.inventory)}.")
            else:
                # Try by name (case-insensitive)
                target_lower = target.lower()
                for i, item in enumerate(char.inventory):
                    if item.lower() == target_lower:
                        char.inventory.pop(i)
                        save_campaign(campaign)
                        await ctx.send(f"**{char.name}** removed **{item}** from inventory.")
                        return
                await ctx.send(f"Item **{target}** not found in inventory.")
        else:
            await ctx.send("Usage: `!equipment`, `!equipment add <item>`, `!equipment remove <item or #>`")

    @commands.command(name="gold")
    async def gold_cmd(self, ctx: commands.Context, *, action: str = ""):
        """View or adjust your gold. DM can adjust any player.

        Usage: !gold (view your gold)
        Usage: !gold +50 (gain 50 gold)
        Usage: !gold -10 (spend 10 gold)
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")

        # DM targeting another player
        target_id = str(ctx.author.id)
        if ctx.message.mentions and campaign.dm_id == str(ctx.author.id):
            target_id = str(ctx.message.mentions[0].id)
            action = action.replace(ctx.message.mentions[0].mention, "").strip()

        char = campaign.get_character(target_id)
        if not char:
            return await ctx.send("No character found.")

        if not action:
            return await ctx.send(f"**{char.name}** — 💰 **{char.gold} gp**")

        try:
            change = int(action)
        except ValueError:
            return await ctx.send("Usage: `!gold`, `!gold +50`, `!gold -10`")

        if char.gold + change < 0:
            return await ctx.send(f"**{char.name}** only has {char.gold} gp. Not enough to spend {abs(change)} gp.")

        char.gold += change
        save_campaign(campaign)
        if change > 0:
            await ctx.send(f"**{char.name}** gained {change} gp. Total: **{char.gold} gp**")
        else:
            await ctx.send(f"**{char.name}** spent {abs(change)} gp. Total: **{char.gold} gp**")

    @commands.command(name="give")
    async def give_item(self, ctx: commands.Context, target: discord.Member, *, item_description: str):
        """Give an item or gold to another player.

        Usage: !give @Player Potion of Healing
        Usage: !give @Player 50 gold
        Usage: !give @Player 2 arrows
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")

        giver = campaign.get_character(str(ctx.author.id))
        receiver = campaign.get_character(str(target.id))
        if not giver:
            return await ctx.send("You don't have a character.")
        if not receiver:
            return await ctx.send(f"{target.display_name} doesn't have a character.")

        # Parse "50 gold" or "2 arrows" or "Potion of Healing"
        parts = item_description.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            quantity = int(parts[0])
            item_name = parts[1]
        else:
            quantity = 1
            item_name = item_description.strip()

        # Gold transfer
        if item_name.lower() in ("gold", "gp", "gold pieces"):
            if giver.gold < quantity:
                return await ctx.send(f"You only have {giver.gold} gp.")
            giver.gold -= quantity
            receiver.gold += quantity
            save_campaign(campaign)
            return await ctx.send(f"**{giver.name}** gave **{quantity} gp** to **{receiver.name}**.")

        # Item transfer
        if not giver.has_item(item_name, quantity):
            return await ctx.send(f"You don't have {quantity}x **{item_name}**.")

        giver.remove_item(item_name, quantity)
        receiver.add_item(item_name, quantity)
        save_campaign(campaign)
        qty_str = f"{quantity}x " if quantity > 1 else ""
        await ctx.send(f"**{giver.name}** gave {qty_str}**{item_name}** to **{receiver.name}**.")

    @commands.command(name="use")
    async def use_item(self, ctx: commands.Context, *, item_name: str):
        """Use a consumable from your inventory.

        Known consumables (healing potions, etc.) apply effects automatically.
        Unknown items are removed and the DM narrates the effect.

        Usage: !use Potion of Healing
        """
        from bot.data.consumables import get_consumable
        from bot.dice import parse_and_roll

        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character.")
        if not char.has_item(item_name):
            return await ctx.send(f"You don't have **{item_name}**. Use `!equipment` to see your inventory.")

        effect = get_consumable(item_name)

        if effect and effect["effect_type"] == "heal":
            char.remove_item(item_name, 1)
            result = parse_and_roll(effect["dice"])
            healing = result["total"] + effect["bonus"]
            old_hp = char.current_hp
            char.current_hp = min(char.max_hp, char.current_hp + healing)
            actual = char.current_hp - old_hp
            save_campaign(campaign)
            await ctx.send(
                f"**{char.name}** uses **{effect['name']}**\n"
                f"Healing: {result['breakdown']}+{effect['bonus']} = **{healing} HP**\n"
                f"HP: {old_hp} -> **{char.current_hp}/{char.max_hp}** (+{actual})"
            )
        elif effect and effect["effect_type"] == "remove_condition":
            char.remove_item(item_name, 1)
            condition = effect["condition"]
            if condition in char.conditions:
                char.conditions.remove(condition)
                save_campaign(campaign)
                await ctx.send(f"**{char.name}** uses **{effect['name']}** — removed *{condition}* condition.")
            else:
                save_campaign(campaign)
                await ctx.send(f"**{char.name}** uses **{effect['name']}**. (No *{condition}* condition to remove.)")
        else:
            # Unknown consumable — remove and let DM narrate
            char.remove_item(item_name, 1)
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** uses **{item_name}**. *(DM will narrate the effect.)*")

    @commands.command(name="equip")
    async def equip_item(self, ctx: commands.Context, slot: str = "", *, item_name: str = ""):
        """Equip or unequip armor and shields.

        Usage: !equip armor Chain Mail
        Usage: !equip shield (toggle shield on/off)
        Usage: !equip (show what's equipped)
        """
        from bot.data.armor import get_armor

        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character.")

        # Ensure equipped is a dict
        if not isinstance(char.equipped, dict):
            char.equipped = {"armor": None, "shield": False}

        if not slot:
            # Show currently equipped
            lines = [f"**{char.name}'s Equipment:**"]
            lines.append(f"  Armor: **{char.equipped.get('armor') or 'None'}**")
            lines.append(f"  Shield: **{'Yes' if char.equipped.get('shield') else 'No'}**")
            lines.append(f"  AC: **{char.ac}**")
            return await ctx.send("\n".join(lines))

        slot = slot.lower()

        if slot == "shield":
            char.equipped["shield"] = not char.equipped.get("shield", False)
            old_ac = char.ac
            char.calc_ac()
            save_campaign(campaign)
            state = "equipped" if char.equipped["shield"] else "unequipped"
            await ctx.send(f"**{char.name}** {state} **Shield** (AC: {old_ac} -> **{char.ac}**)")
            return

        if slot == "armor":
            if not item_name:
                # Unequip armor
                old_armor = char.equipped.get("armor")
                if not old_armor:
                    return await ctx.send(f"**{char.name}** isn't wearing armor.")
                char.equipped["armor"] = None
                old_ac = char.ac
                char.calc_ac()
                save_campaign(campaign)
                return await ctx.send(f"**{char.name}** removed **{old_armor}** (AC: {old_ac} -> **{char.ac}**)")

            armor_data = get_armor(item_name)
            if not armor_data:
                return await ctx.send(f"Unknown armor: **{item_name}**. Valid armor: Leather, Studded Leather, Hide, "
                                      "Chain Shirt, Scale Mail, Breastplate, Half Plate, Ring Mail, Chain Mail, Splint, Plate")

            old_armor = char.equipped.get("armor")
            char.equipped["armor"] = armor_data["name"]
            old_ac = char.ac
            char.calc_ac()
            save_campaign(campaign)
            msg = f"**{char.name}** equipped **{armor_data['name']}** (AC: {old_ac} -> **{char.ac}**)"
            if old_armor:
                msg += f"\n*(Replaced {old_armor})*"
            await ctx.send(msg)
            return

        await ctx.send("Usage: `!equip`, `!equip armor <name>`, `!equip shield`")

    @commands.command(name="backstory")
    async def backstory(self, ctx: commands.Context, *, text: str = ""):
        """View or set your character's backstory.

        Usage: !backstory (view your backstory)
        Usage: !backstory <text> (set/update your backstory)
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        # Allow viewing other players' backstories
        target_id = str(ctx.author.id)
        if ctx.message.mentions:
            target_id = str(ctx.message.mentions[0].id)
            text = ""  # Viewing, not setting

        char = campaign.get_character(target_id)
        if not char:
            await ctx.send("No character found.")
            return

        if not text:
            if not char.backstory:
                if target_id == str(ctx.author.id):
                    await ctx.send(f"**{char.name}** has no backstory yet. Use `!backstory <text>` to write one.")
                else:
                    await ctx.send(f"**{char.name}** has no backstory yet.")
                return
            await ctx.send(f"**{char.name}'s Backstory:**\n> {char.backstory}")
            return

        # Setting backstory (only for your own character)
        if target_id != str(ctx.author.id):
            await ctx.send("You can only set your own backstory.")
            return

        char.backstory = text.strip()
        save_campaign(campaign)
        await ctx.send(f"**{char.name}'s** backstory updated!\n> {char.backstory}")

    @commands.command(name="deletechar")
    async def delete_char(self, ctx: commands.Context):
        """Delete your character and start over."""
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        _clear_session(ctx.author.id)

        if not char:
            await ctx.send("You don't have a character to delete.")
            return

        name = char.name or "Unnamed"
        campaign.remove_character(player_id)
        save_campaign(campaign)
        await ctx.send(f"**{name}** has been deleted. Use `!createchar` to make a new character.")

    def _build_sheet_embeds(self, char) -> list[discord.Embed]:
        """Build rich Discord embeds for a D&D character sheet."""
        embeds = []
        cls_emoji = CLASS_EMOJIS.get(char.char_class, "⚔️")
        race_display = char.subrace if char.subrace else char.race
        gender_str = f" | {char.gender}" if char.gender else ""
        insp_str = " ✦ Inspired" if char.inspiration else ""

        # ── Header Embed ──
        desc_lines = [f"{cls_emoji} **Level {char.level} {race_display} {char.char_class}**{gender_str}"]
        if char.background:
            desc_lines.append(f"📜 *{char.background}*")
        if char.draconic_ancestry:
            desc_lines.append(f"🐉 Draconic Ancestry: {char.draconic_ancestry}")

        header = discord.Embed(
            title=f"⚔ {char.name}{insp_str}",
            description="\n".join(desc_lines),
            color=discord.Color.blue(),
        )

        # HP bar
        hp_ratio = max(0, min(char.current_hp / char.max_hp, 1.0)) if char.max_hp > 0 else 0
        hp_filled = round(hp_ratio * 16)
        hp_bar = "█" * hp_filled + "░" * (16 - hp_filled)
        hp_color = "🟢" if hp_ratio > 0.5 else ("🟡" if hp_ratio > 0.25 else "🔴")
        header.add_field(
            name=f"❤️ Hit Points {hp_color}",
            value=f"`{hp_bar}`\n**{char.current_hp}/{char.max_hp}**" +
                  (f" (+{char.temp_hp} temp)" if char.temp_hp else ""),
            inline=False,
        )

        # Core stats row
        ac_source = ""
        if isinstance(char.equipped, dict):
            parts = []
            if char.equipped.get("armor"):
                parts.append(char.equipped["armor"])
            if char.equipped.get("shield"):
                parts.append("Shield")
            if parts:
                ac_source = f" ({', '.join(parts)})"

        core_stats = (
            f"🛡️ **AC:** {char.ac}{ac_source}\n"
            f"⚡ **Speed:** {char.speed} ft\n"
            f"🎲 **Prof:** +{char.proficiency_bonus}\n"
            f"🎯 **Hit Dice:** {char.hit_dice_remaining}d{char.hit_die}"
        )
        header.add_field(name="\u200b", value=core_stats, inline=True)

        xp_info = (
            f"✨ **XP:** {char.xp}/{xp_for_next_level(char.level)}\n"
            f"💰 **Gold:** {char.gold} gp"
        )
        header.add_field(name="\u200b", value=xp_info, inline=True)

        # Death saves (if applicable)
        if char.current_hp == 0:
            ds = char.death_saves
            ds_str = f"✅ {ds['successes']}/3  ❌ {ds['failures']}/3"
            header.add_field(name="💀 Death Saves", value=ds_str, inline=False)

        # Conditions
        if char.conditions:
            header.add_field(
                name="⚠️ Conditions",
                value=", ".join(char.conditions),
                inline=False,
            )

        embeds.append(header)

        # ── Ability Scores Embed ──
        ability_embed = discord.Embed(
            title="📊 Ability Scores",
            description="*★ = saving throw proficiency*",
            color=discord.Color.blue(),
        )
        # Two columns: STR/DEX/CON and INT/WIS/CHA
        for col_abilities in [["STR", "DEX", "CON"], ["INT", "WIS", "CHA"]]:
            lines = []
            for ab in col_abilities:
                emoji = ABILITY_EMOJIS.get(ab, "")
                score = char.abilities[ab]
                mod = modifier_str(score)
                save_mod = char.get_save_modifier(ab)
                save_str = f"+{save_mod}" if save_mod >= 0 else str(save_mod)
                prof_mark = " ★" if ab in char.saving_throw_proficiencies else ""
                lines.append(
                    f"{emoji} **{ABILITY_FULL_NAMES[ab]}:** {score} ({mod})\n"
                    f"   Save: {save_str}{prof_mark}"
                )
            ability_embed.add_field(
                name="\u200b",
                value="\n".join(lines),
                inline=True,
            )
        embeds.append(ability_embed)

        # ── Skills Embed ──
        skills_embed = discord.Embed(
            title="📚 Skills",
            description="*★ = proficient*",
            color=discord.Color.blue(),
        )
        # Group by ability
        for ab_key, ab_label in [("STR", "💪 Strength"), ("DEX", "🏃 Dexterity"),
                                   ("CON", "❤️ Constitution"), ("INT", "🧠 Intelligence"),
                                   ("WIS", "👁️ Wisdom"), ("CHA", "🗣️ Charisma")]:
            skill_list = SKILLS_BY_ABILITY.get(ab_key, [])
            if not skill_list:
                continue
            lines = []
            for sk in skill_list:
                sk_mod = char.get_skill_modifier(sk)
                mod_s = f"+{sk_mod}" if sk_mod >= 0 else str(sk_mod)
                mark = "★" if sk in char.skill_proficiencies else "○"
                if sk in char.skill_proficiencies:
                    lines.append(f"**{mark} {sk}** {mod_s}")
                else:
                    lines.append(f"{mark} {sk} {mod_s}")
            skills_embed.add_field(name=ab_label, value="\n".join(lines), inline=True)

        # Passive scores
        passive_perc = 10 + char.get_skill_modifier("Perception")
        passive_inv = 10 + char.get_skill_modifier("Investigation")
        skills_embed.add_field(
            name="👀 Passive Scores",
            value=f"Perception: **{passive_perc}** | Investigation: **{passive_inv}**",
            inline=False,
        )
        embeds.append(skills_embed)

        # ── Features & Traits Embed ──
        if char.traits or char.features or char.feats or char.languages or char.modifiers:
            feat_embed = discord.Embed(
                title="📜 Traits & Features",
                color=discord.Color.blue(),
            )
            if char.traits:
                trait_text = "\n".join(f"• {t}" for t in char.traits[:10])
                feat_embed.add_field(name="🧬 Racial Traits", value=trait_text, inline=False)
            if char.features:
                feat_text = "\n".join(f"• {f}" for f in char.features)
                feat_embed.add_field(name="⭐ Features", value=feat_text, inline=True)
            if char.feats:
                feat_embed.add_field(name="🏅 Feats", value=", ".join(char.feats), inline=True)
            if char.languages:
                feat_embed.add_field(name="💬 Languages", value=", ".join(char.languages), inline=True)
            if char.modifiers:
                mod_strs = []
                for source, bonuses in char.modifiers.items():
                    parts = [f"{stat} {'+' if val >= 0 else ''}{val}" for stat, val in bonuses.items()]
                    mod_strs.append(f"**{source}** ({', '.join(parts)})")
                feat_embed.add_field(name="🔧 Modifiers", value="\n".join(mod_strs), inline=False)
            embeds.append(feat_embed)

        # ── Weapons Embed ──
        if char.weapons:
            weapons_embed = discord.Embed(
                title="⚔️ Weapons",
                color=discord.Color.blue(),
            )
            for w in char.weapons:
                is_finesse = w.get('finesse', False)
                is_ranged = w.get('category') == 'ranged'
                ab_mod = char.get_modifier("DEX") if (is_finesse or is_ranged) else char.get_modifier("STR")
                atk_bonus = ab_mod + char.proficiency_bonus
                atk_str = f"+{atk_bonus}" if atk_bonus >= 0 else str(atk_bonus)
                dmg_str = f"+{ab_mod}" if ab_mod >= 0 else str(ab_mod)
                props = f"\n*{', '.join(w['properties'])}*" if w.get('properties') else ""
                weapons_embed.add_field(
                    name=f"⚔️ {w['name']}",
                    value=f"Attack: **{atk_str}**\nDamage: **{w['damage']}{dmg_str}** {w['damage_type']}{props}",
                    inline=True,
                )
            embeds.append(weapons_embed)

        # ── Spellcasting Embed ──
        if char.spellcasting_ability:
            spell_mod = char.get_modifier(char.spellcasting_ability)
            spell_save = 8 + char.proficiency_bonus + spell_mod
            spell_atk = char.proficiency_bonus + spell_mod
            atk_str = f"+{spell_atk}" if spell_atk >= 0 else str(spell_atk)

            spell_embed = discord.Embed(
                title="🔮 Spellcasting",
                description=(
                    f"**Ability:** {char.spellcasting_ability} | "
                    f"**Save DC:** {spell_save} | "
                    f"**Attack:** {atk_str}"
                ),
                color=discord.Color.purple(),
            )
            if char.cantrips:
                spell_embed.add_field(
                    name="✨ Cantrips",
                    value=", ".join(char.cantrips),
                    inline=False,
                )
            if char.spell_slots_max:
                slot_lines = []
                for lvl in sorted(char.spell_slots_max, key=lambda x: int(x)):
                    used = char.spell_slots_used.get(lvl, 0)
                    total = char.spell_slots_max[lvl]
                    remaining = total - used
                    pips = "◆" * remaining + "◇" * used
                    slot_lines.append(f"**Lv{lvl}:** {pips}")
                spell_embed.add_field(
                    name="📊 Spell Slots",
                    value="\n".join(slot_lines),
                    inline=True,
                )
            if char.prepared_spells:
                spell_embed.add_field(
                    name="📖 Prepared",
                    value=", ".join(char.prepared_spells),
                    inline=False,
                )
            if char.known_spells and char.known_spells != char.prepared_spells:
                spell_embed.add_field(
                    name="📚 Known",
                    value=", ".join(char.known_spells),
                    inline=False,
                )
            embeds.append(spell_embed)

        # ── Inventory Embed ──
        if char.inventory or char.gold:
            inv_embed = discord.Embed(
                title="🎒 Inventory",
                color=discord.Color.blue(),
            )
            if isinstance(char.equipped, dict):
                equipped_parts = []
                if char.equipped.get("armor"):
                    equipped_parts.append(f"🛡️ {char.equipped['armor']}")
                if char.equipped.get("shield"):
                    equipped_parts.append("🛡️ Shield")
                if equipped_parts:
                    inv_embed.add_field(
                        name="Equipped",
                        value="\n".join(equipped_parts),
                        inline=True,
                    )
            if char.inventory:
                items = [char._format_inv_item(e) for e in char.inventory[:15]]
                item_text = "\n".join(f"• {item}" for item in items)
                if len(char.inventory) > 15:
                    item_text += f"\n*...and {len(char.inventory) - 15} more*"
                inv_embed.add_field(name="Items", value=item_text, inline=False)
            embeds.append(inv_embed)

        return embeds

    @commands.command(name="sheet")
    async def sheet(self, ctx: commands.Context, member: discord.Member = None):
        """View your character sheet (or another player's).

        Usage: !sheet
        Usage: !sheet @player
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        target_id = str(member.id) if member else str(ctx.author.id)
        char = campaign.get_character(target_id)
        if not char:
            await ctx.send("No character found." if member else
                           "You don't have a character. Use `!createchar` to make one.")
            return

        embeds = self._build_sheet_embeds(char)
        for embed in embeds:
            await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # Interactive sheet editor (!dndedit)
    # ------------------------------------------------------------------

    def _build_edit_pages(self, char):
        """Build the list of editor pages for a D&D character."""
        pages = [
            {
                "title": "📊 Ability Scores",
                "items": list(ABILITY_NAMES),
                "kind": "abilities",
                "display_fn": lambda c, name: (
                    f"{c.abilities[name]} ({modifier_str(c.abilities[name])})"
                ),
            },
            {
                "title": "💪 STR / 🏃 DEX Skills",
                "items": SKILLS_BY_ABILITY.get("STR", []) + SKILLS_BY_ABILITY.get("DEX", []),
                "kind": "skills",
                "display_fn": lambda c, name: (
                    f"{'★' if name in c.skill_proficiencies else '○'} "
                    f"{'+' if c.get_skill_modifier(name) >= 0 else ''}{c.get_skill_modifier(name)}"
                ),
            },
            {
                "title": "🧠 INT / 👁️ WIS Skills",
                "items": SKILLS_BY_ABILITY.get("INT", []) + SKILLS_BY_ABILITY.get("WIS", []),
                "kind": "skills",
                "display_fn": lambda c, name: (
                    f"{'★' if name in c.skill_proficiencies else '○'} "
                    f"{'+' if c.get_skill_modifier(name) >= 0 else ''}{c.get_skill_modifier(name)}"
                ),
            },
            {
                "title": "🗣️ CHA Skills",
                "items": SKILLS_BY_ABILITY.get("CHA", []),
                "kind": "skills",
                "display_fn": lambda c, name: (
                    f"{'★' if name in c.skill_proficiencies else '○'} "
                    f"{'+' if c.get_skill_modifier(name) >= 0 else ''}{c.get_skill_modifier(name)}"
                ),
            },
        ]
        return pages

    def _build_edit_embed(self, char, pages, page_idx: int, cursor: int) -> discord.Embed:
        """Build the embed for the current editor page."""
        page = pages[page_idx]
        items = page["items"]
        kind = page["kind"]
        display_fn = page["display_fn"]

        embed = discord.Embed(
            title=f"✏️ Editing: {char.name}",
            description=f"**{page['title']}**\nPage {page_idx + 1}/{len(pages)}",
            color=discord.Color.gold(),
        )

        lines = []
        for i, name in enumerate(items):
            display_label = ABILITY_FULL_NAMES.get(name, name)
            emoji = ABILITY_EMOJIS.get(name, "")
            val_str = display_fn(char, name)
            pointer = "▸ " if i == cursor else "  "
            num = NUMBER_EMOJIS[i] if i < len(NUMBER_EMOJIS) else f"{i + 1}."
            lines.append(f"{pointer}{num} {emoji} **{display_label}:** {val_str}")

        embed.add_field(name="\u200b", value="\n".join(lines), inline=False)

        # Controls legend — different for abilities vs skills
        if kind == "abilities":
            embed.set_footer(
                text="◀️▶️ Page │ 1️⃣-🔟 Select │ ➕➖ Score ±1 │ ✅ Save"
            )
        else:
            embed.set_footer(
                text="◀️▶️ Page │ 1️⃣-🔟 Select │ 🔄 Toggle Proficiency │ ✅ Save"
            )
        return embed

    @commands.command(name="dndedit", aliases=["dedit", "editchar"])
    async def dnd_edit(self, ctx: commands.Context):
        """Interactively edit your D&D character with emoji reactions.

        Navigate pages with ◀️▶️, select items with number emojis.
        For abilities: ➕➖ to adjust scores.
        For skills: 🔄 to toggle proficiency.
        Press ✅ to save and exit.

        Usage: !dndedit
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            return await ctx.send("No campaign in this channel.")
        if campaign.game_system == GameSystem.WOD:
            return await ctx.send("This is a WoD campaign — use `!wodedit` instead.")
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")
        if not char.creation_complete:
            return await ctx.send("Finish character creation first with `!cc`.")

        pages = self._build_edit_pages(char)
        page_idx = 0
        cursor = 0

        embed = self._build_edit_embed(char, pages, page_idx, cursor)
        msg = await ctx.send(embed=embed)

        # Add control reactions
        all_emojis = NUMBER_EMOJIS[:len(pages[page_idx]["items"])] + EDIT_NAV_EMOJIS
        for emoji in all_emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                pass

        changed = False
        timeout_seconds = 180.0

        while True:
            def check(reaction, user):
                return (
                    user.id == ctx.author.id
                    and reaction.message.id == msg.id
                    and str(reaction.emoji) in (
                        NUMBER_EMOJIS[:len(pages[page_idx]["items"])] + EDIT_NAV_EMOJIS
                    )
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=timeout_seconds, check=check
                )
            except asyncio.TimeoutError:
                if changed:
                    char.calc_ac()
                    char.update_proficiency()
                    save_campaign(campaign)
                embed = self._build_edit_embed(char, pages, page_idx, cursor)
                embed.set_footer(text="⏰ Editor timed out. Changes saved." if changed else "⏰ Editor timed out.")
                try:
                    await msg.edit(embed=embed)
                except discord.HTTPException:
                    pass
                return

            emoji_str = str(reaction.emoji)

            try:
                await msg.remove_reaction(reaction.emoji, user)
            except discord.HTTPException:
                pass

            page = pages[page_idx]
            items = page["items"]
            kind = page["kind"]

            if emoji_str == EDIT_SAVE:
                if changed:
                    char.calc_ac()
                    char.update_proficiency()
                    save_campaign(campaign)
                embed = self._build_edit_embed(char, pages, page_idx, cursor)
                embed.color = discord.Color.green()
                embed.set_footer(text="✅ Changes saved!" if changed else "✅ No changes made.")
                try:
                    await msg.edit(embed=embed)
                    await msg.clear_reactions()
                except discord.HTTPException:
                    pass
                return

            elif emoji_str == NAV_PREV:
                page_idx = (page_idx - 1) % len(pages)
                cursor = 0

            elif emoji_str == NAV_NEXT:
                page_idx = (page_idx + 1) % len(pages)
                cursor = 0

            elif emoji_str == EDIT_PLUS and kind == "abilities":
                ab = items[cursor]
                if char.abilities[ab] < 30:
                    char.abilities[ab] += 1
                    changed = True

            elif emoji_str == EDIT_MINUS and kind == "abilities":
                ab = items[cursor]
                if char.abilities[ab] > 1:
                    char.abilities[ab] -= 1
                    changed = True

            elif emoji_str == EDIT_TOGGLE and kind == "skills":
                skill = items[cursor]
                if skill in char.skill_proficiencies:
                    char.skill_proficiencies.remove(skill)
                else:
                    char.skill_proficiencies.append(skill)
                changed = True

            elif emoji_str in NUMBER_EMOJIS:
                idx = NUMBER_EMOJIS.index(emoji_str)
                if idx < len(items):
                    cursor = idx

            embed = self._build_edit_embed(char, pages, page_idx, cursor)
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass

    def _resolve_choice(self, choice: str, options: list[str]) -> str | None:
        """Resolve a user choice by number or partial name match."""
        choice = choice.strip()

        # Try as number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
            return None

        # Try exact match (case-insensitive)
        choice_lower = choice.lower()
        for opt in options:
            # Handle formatted options like "Fighter — A master..."
            opt_name = opt.split("—")[0].strip() if "—" in opt else opt
            if opt_name.lower() == choice_lower:
                return opt_name if "—" in opt else opt

        # Try prefix match
        for opt in options:
            opt_name = opt.split("—")[0].strip() if "—" in opt else opt
            if opt_name.lower().startswith(choice_lower):
                return opt_name if "—" in opt else opt

        return None


async def setup(bot: commands.Bot):
    await bot.add_cog(CharacterCog(bot))

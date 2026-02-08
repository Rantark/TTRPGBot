"""Character creation and management cog with interactive step-by-step flow."""

import discord
from discord.ext import commands

from bot.models.character import Character
from bot.models.campaign import CampaignPhase
from bot.data.races import get_race_names, resolve_race, DRACONIC_ANCESTRIES, RACES
from bot.data.classes import get_class_names, get_class_data, CLASSES
from bot.data.backgrounds import get_background_names, get_background_data
from bot.data.rules import (
    ABILITY_NAMES, ABILITY_FULL_NAMES, STANDARD_ARRAY, SKILLS,
    POINT_BUY_COSTS, POINT_BUY_BUDGET, modifier_str, modifier,
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


class CharacterCog(commands.Cog, name="Character"):
    """Commands for character creation and management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx: commands.Context):
        return load_campaign(str(ctx.channel.id))

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
        await ctx.send(f"**{char.name}** — AC: **{char.ac}**")

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
                level_note = f"\nThis campaign starts at **level {campaign.starting_level}**! Your character will be created at that level.\n"
            await ctx.author.send(
                "**Character Creation**\n"
                "Let's build your character step by step.\n"
                f"{level_note}\n"
                "**Step 1: Name**\n"
                "What is your character's name?\n"
                "Reply with: `!cc <name>`\n"
                "Example: `!cc Thandril`"
            )
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

        # If used in a guild channel, redirect to DMs
        if ctx.guild is not None:
            await ctx.send(f"{ctx.author.mention} Character creation happens in DMs! Check your DMs and use `!cc` there.")
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

    async def _step_name(self, ctx, session, char: Character, choice: str):
        if not choice.strip():
            await ctx.send("Please provide a name: `!cc <name>`\nExample: `!cc Thandril`")
            return
        char.name = choice.strip()
        session["step"] = "gender"
        _set_session(ctx.author.id, session)

        await ctx.send(
            f"Great, **{char.name}**!\n\n"
            f"**Step 2: Gender**\n"
            f"Choose your character's gender:\n"
            f"`1.` Male\n"
            f"`2.` Female\n"
            f"`3.` Non-binary\n"
            f"Or type anything else (e.g., `!cc Agender`)\n\n"
            f"Example: `!cc Male`"
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
        race_list = _format_numbered_list(races)
        await ctx.send(
            f"Gender: **{char.gender}**\n\n"
            f"**Step 3: Race**\n"
            f"Choose your character's race:\n{race_list}\n\n"
            f"Each race grants ability score bonuses, traits, and languages.\n"
            f"Reply with: `!cc <number or name>`\n"
            f"Example: `!cc Elf`"
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
            ancestry_list = _format_numbered_list(list(DRACONIC_ANCESTRIES.keys()))
            await ctx.send(
                f"**Dragonborn Ancestry**\n"
                f"Choose your draconic ancestry:\n{ancestry_list}\n\n"
                "This determines your breath weapon and damage resistance.\n"
                "Reply with: `!cc <number or color>`"
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

        msg = (
            f"**Race: {race_display}**\n"
            f"Ability Bonuses: {bonuses}\n"
            f"Speed: {char.speed} ft\n"
            f"Traits: {', '.join(char.traits[:5])}"
        )
        if len(char.traits) > 5:
            msg += f" (+{len(char.traits) - 5} more)"

        session["step"] = "class"
        _set_session(ctx.author.id, session)

        classes = get_class_names()
        class_list = []
        for cls_name in classes:
            data = CLASSES[cls_name]
            primary = data.get("primary_ability", "")
            class_list.append(f"{cls_name} ({primary}) — d{data['hit_die']} HP")
        class_display = _format_numbered_list(class_list)

        await ctx.send(
            f"{msg}\n\n"
            f"**Step 4: Class**\n"
            f"Choose your class:\n{class_display}\n\n"
            f"Reply with: `!cc <number or name>`\n"
            f"Example: `!cc Fighter`"
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

        await ctx.send(
            f"**Class: {cls_name}** (d{cls_data['hit_die']})\n"
            f"*{cls_data['description']}*\n\n"
            f"**Step 5: Ability Scores**\n"
            f"Choose how to generate your ability scores:\n\n"
            f"`1.` **Roll** — Roll 4d6, drop lowest, 6 times (random)\n"
            f"`2.` **Standard Array** — Use preset scores {STANDARD_ARRAY}\n"
            f"`3.` **Point Buy** — Spend 27 points to customize (scores 8-15)\n\n"
            f"Reply with: `!cc 1`, `!cc 2`, or `!cc 3`\n"
            f"Example: `!cc roll` or `!cc standard array` or `!cc point buy`"
        )

    async def _step_ability_method(self, ctx, session, char: Character, choice: str):
        choice = choice.strip()

        if choice in ("1", "roll"):
            # Roll 4d6 drop lowest
            results = roll_ability_scores()
            scores = [r[0] for r in results]
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
            await ctx.send(
                f"**Rolled Ability Scores:**\n{detail_str}\n\n"
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
        lines = ["**Final Ability Scores** (racial bonuses applied):"]
        for ab in ABILITY_NAMES:
            score = char.abilities[ab]
            bonus = char.racial_bonuses.get(ab, 0)
            bonus_str = f" (+{bonus} racial)" if bonus else ""
            lines.append(f"  {ABILITY_FULL_NAMES[ab]:14s} **{score}** ({modifier_str(score)}){bonus_str}")

        session["step"] = "background"
        _set_session(ctx.author.id, session)

        backgrounds = get_background_names()
        bg_list = _format_numbered_list(backgrounds)

        await ctx.send(
            "\n".join(lines) + "\n\n"
            f"**Step 6: Background**\n"
            f"Choose your background (grants 2 skill proficiencies):\n{bg_list}\n\n"
            f"Reply with: `!cc <number or name>`\n"
            f"Example: `!cc Soldier`"
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

        await ctx.send(
            f"**Background: {bg_name}**\n"
            f"*{bg_data['description']}*\n"
            f"Feature: {bg_data['feature']}\n"
            f"Skills gained: {', '.join(bg_data['skill_proficiencies'])}\n\n"
            f"**Step 7: Class Skills**\n"
            f"Already proficient: {already}\n"
            f"Choose **{num_skills}** from:\n{skill_list}\n\n"
            f"Reply with numbers: `!cc 1 3` or names: `!cc Athletics Perception`"
        )

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
        choice_list = _format_numbered_list(current_choice)
        choice_num = idx + 1
        total = len(choices)

        await ctx.send(
            f"**Step 8: Starting Equipment** (choice {choice_num}/{total})\n"
            f"Pick one:\n{choice_list}\n\n"
            f"Reply with: `!cc <number>`"
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

        lines = [f"**Step 9: Weapon Selection** ({label})"]
        lines.append("Choose your weapon:\n")
        for i, weapon_key in enumerate(options, 1):
            w = WEAPONS.get(weapon_key)
            if w:
                props = f" ({', '.join(w['properties'])})" if w.get('properties') else ""
                lines.append(f"`{i:2d}.` **{w['name']}** — {w['damage']} {w['damage_type']}{props}")
            else:
                lines.append(f"`{i:2d}.` {weapon_key}")

        lines.append(f"\nReply with: `!cc <number>`\nExample: `!cc 1`")

        if idx > 0:
            picked_names = [w.get('name', '?') for w in session.get("weapon_picks", [])]
            if picked_names:
                lines.append(f"\nAlready chosen: {', '.join(picked_names)}")

        await ctx.send("\n".join(lines))

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

        lines = [f"**Step 10: Spell Selection — Cantrips**"]
        lines.append(f"Choose {needed} cantrips for your {char.char_class}.")
        lines.append(f"Progress: {len(picked)}/{needed} chosen\n")

        for i, spell in enumerate(available, 1):
            lines.append(f"`{i:2d}.` {spell}")

        lines.append(f"\nReply with: `!cc <number>`\nExample: `!cc 1`")

        if picked:
            lines.append(f"\nChosen so far: {', '.join(picked)}")

        await ctx.send("\n".join(lines))

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

        lines = [f"**Step 10: Spell Selection — 1st Level Spells**"]
        lines.append(f"{type_desc}")
        lines.append(f"Progress: {len(picked)}/{needed} chosen\n")

        for i, spell in enumerate(available, 1):
            lines.append(f"`{i:2d}.` {spell}")

        lines.append(f"\nReply with: `!cc <number>`\nExample: `!cc 1`")

        if picked:
            lines.append(f"\nChosen so far: {', '.join(picked)}")

        await ctx.send("\n".join(lines))

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

        # Finalize character at the campaign's starting level
        starting_level = session.get("starting_level", 1)
        char.finalize(starting_level=starting_level)

        session["step"] = "confirm"
        _set_session(ctx.author.id, session)

        sheet = char.format_sheet()
        if len(sheet) > 1800:
            sheet = sheet[:1800] + "\n..."

        await ctx.send(
            f"**Character Preview:**\n{sheet}\n\n"
            f"Confirm this character? Reply `!cc yes` to save or `!cc no` to start over."
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

            await ctx.send(
                f"**{char.name}** has been created and saved!\n"
                f"Use `!sheet` in the server channel to view your character sheet."
            )

            # Announce in the original guild channel
            try:
                guild_channel = self.bot.get_channel(int(channel_id))
                if guild_channel:
                    await guild_channel.send(
                        f"**{char.name}** ({char.race} {char.char_class}) has joined the party! "
                        f"Created by {ctx.author.mention}."
                    )
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
            if not char.inventory:
                await ctx.send(f"**{char.name}** has no equipment. Use `!equipment add <item>` to add items.")
                return
            lines = [f"**{char.name}'s Equipment:**"]
            for i, item in enumerate(char.inventory, 1):
                lines.append(f"  `{i}.` {item}")
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

        sheet = char.format_sheet()
        # Split if too long
        while len(sheet) > 1990:
            split_at = sheet.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await ctx.send(sheet[:split_at])
            sheet = sheet[split_at:].lstrip("\n")
        if sheet:
            await ctx.send(sheet)

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

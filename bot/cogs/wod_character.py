"""World of Darkness character creation cog with interactive step-by-step flow."""

import asyncio

import discord
from discord.ext import commands

from bot.models.wod_character import (
    WoDCharacter,
    WOD_MENTAL_ATTRIBUTES, WOD_PHYSICAL_ATTRIBUTES, WOD_SOCIAL_ATTRIBUTES,
    WOD_MENTAL_SKILLS, WOD_PHYSICAL_SKILLS, WOD_SOCIAL_SKILLS,
    WOD_ALL_ATTRIBUTES, WOD_ALL_SKILLS,
)
from bot.models.campaign import CampaignPhase, GameSystem
from bot.data.wod_clans import (
    CLANS, COVENANTS, VIRTUES, VICES,
    get_clan_names, get_clan_data, get_covenant_names,
)
from bot.data.wod_disciplines import get_clan_disciplines, get_discipline_data
from bot.data.wod_merits import MERITS, MERIT_DOTS_AT_CREATION, get_merit_names
from bot.storage import load_campaign, save_campaign


# Track WoD creation state per user (user_id -> state dict)
_wod_creation_sessions: dict[str, dict] = {}


def _get_session(user_id) -> dict | None:
    return _wod_creation_sessions.get(str(user_id))


def _set_session(user_id, session: dict):
    _wod_creation_sessions[str(user_id)] = session


def _clear_session(user_id):
    _wod_creation_sessions.pop(str(user_id), None)


def _format_numbered_list(items: list[str]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"`{i:2d}.` {item}")
    return "\n".join(lines)


NUMBER_EMOJIS = [
    "1\u20e3", "2\u20e3", "3\u20e3", "4\u20e3", "5\u20e3",
    "6\u20e3", "7\u20e3", "8\u20e3", "9\u20e3", "\U0001f51f"
]
CONFIRM_EMOJIS = ["\u2705", "\u274c"]


class WoDCharacterCog(commands.Cog, name="WoD Character"):
    """Commands for World of Darkness character creation and management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx: commands.Context):
        return load_campaign(str(ctx.channel.id))

    def _is_wod_campaign(self, campaign) -> bool:
        return campaign and campaign.game_system == GameSystem.WOD

    async def _send_with_reactions(self, ctx, header: str, options: list[str],
                                    display_options: list[str] = None,
                                    emojis: list[str] = None, expected_step: str = ""):
        """Send a prompt with emoji reactions for selection."""
        if len(options) > 10 or not options:
            display = display_options or options
            opt_list = _format_numbered_list(display)
            await ctx.send(f"{header}\n{opt_list}\n\nReply with: `!wcc <number or name>`")
            return

        if emojis is None:
            emojis = NUMBER_EMOJIS[:len(options)]
        else:
            emojis = emojis[:len(options)]

        display = display_options or options

        lines = [header, ""]
        for emoji, label in zip(emojis, display):
            lines.append(f"{emoji} {label}")
        lines.append("\n*React to choose, or type `!wcc <name>` to select*")

        msg = await ctx.send("\n".join(lines))

        for emoji in emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                pass

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

        handler = {
            "name": self._step_name,
            "gender": self._step_gender,
            "concept": self._step_concept,
            "clan": self._step_clan,
            "covenant": self._step_covenant,
            "virtue": self._step_virtue,
            "vice": self._step_vice,
            "attr_priority": self._step_attr_priority,
            "attr_assign_primary": self._step_attr_assign,
            "attr_assign_secondary": self._step_attr_assign,
            "attr_assign_tertiary": self._step_attr_assign,
            "skill_priority": self._step_skill_priority,
            "skill_assign_primary": self._step_skill_assign,
            "skill_assign_secondary": self._step_skill_assign,
            "skill_assign_tertiary": self._step_skill_assign,
            "specialties": self._step_specialties,
            "disciplines": self._step_disciplines,
            "merits": self._step_merits,
            "backstory": self._step_backstory,
            "confirm": self._step_confirm,
        }.get(step)

        if handler:
            await handler(ctx, session, char, choice)

    # ------------------------------------------------------------------
    # Quick stat commands (WoD versions)
    # ------------------------------------------------------------------

    @commands.command(name="wodsheet", aliases=["wsheet"])
    async def wod_sheet(self, ctx: commands.Context):
        """Display your WoD character sheet."""
        campaign = self._get_campaign(ctx)
        if not self._is_wod_campaign(campaign):
            return
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createchar` to create one.")
        await self._send_long(ctx, char.format_sheet())

    @commands.command(name="vitae", aliases=["blood"])
    async def quick_vitae(self, ctx: commands.Context, *, amount: str = ""):
        """View or spend Vitae.

        Usage: !vitae (view)
        Usage: !vitae -2 (spend 2)
        Usage: !vitae +3 (gain 3)
        """
        campaign = self._get_campaign(ctx)
        if not self._is_wod_campaign(campaign):
            return
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character.")

        if amount:
            try:
                delta = int(amount)
                old = char.vitae
                char.vitae = max(0, min(char.vitae_max, char.vitae + delta))
                save_campaign(campaign)
                await ctx.send(
                    f"**{char.name}** Vitae: {old} -> {char.vitae}/{char.vitae_max}"
                )
            except ValueError:
                await ctx.send("Usage: `!vitae +3` or `!vitae -2`")
        else:
            pips = "O" * char.vitae + "." * (char.vitae_max - char.vitae)
            await ctx.send(
                f"**{char.name}** — Vitae: {char.vitae}/{char.vitae_max} [{pips}] "
                f"({char.vitae_per_turn}/turn)"
            )

    @commands.command(name="humanity")
    async def quick_humanity(self, ctx: commands.Context):
        """Display your Humanity rating."""
        campaign = self._get_campaign(ctx)
        if not self._is_wod_campaign(campaign):
            return
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character.")
        dots = "O" * char.humanity + "." * (10 - char.humanity)
        await ctx.send(f"**{char.name}** — Humanity: {char.humanity}/10 [{dots}]")

    @commands.command(name="willpower", aliases=["wp"])
    async def quick_willpower(self, ctx: commands.Context, *, amount: str = ""):
        """View or spend Willpower.

        Usage: !willpower (view)
        Usage: !willpower -1 (spend 1)
        """
        campaign = self._get_campaign(ctx)
        if not self._is_wod_campaign(campaign):
            return
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character.")

        if amount:
            try:
                delta = int(amount)
                old = char.willpower_current
                char.willpower_current = max(0, min(char.willpower_max, char.willpower_current + delta))
                save_campaign(campaign)
                await ctx.send(
                    f"**{char.name}** Willpower: {old} -> {char.willpower_current}/{char.willpower_max}"
                )
            except ValueError:
                await ctx.send("Usage: `!willpower -1` or `!willpower +1`")
        else:
            pips = "O" * char.willpower_current + "." * (char.willpower_max - char.willpower_current)
            await ctx.send(
                f"**{char.name}** — Willpower: {char.willpower_current}/{char.willpower_max} [{pips}]"
            )

    # ------------------------------------------------------------------
    # Character creation entry point
    # ------------------------------------------------------------------

    @commands.command(name="createwod", aliases=["wodcreate"])
    @commands.guild_only()
    async def create_wod_char(self, ctx: commands.Context):
        """Start World of Darkness character creation (Vampire: The Requiem).

        Usage: !createwod
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if not self._is_wod_campaign(campaign):
            await ctx.send("This isn't a World of Darkness campaign. Use `!createchar` for D&D.")
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

        char = WoDCharacter(player_id, ctx.author.display_name)
        session = {
            "step": "name",
            "char": char,
            "channel_id": str(ctx.channel.id),
            "guild_id": ctx.guild.id,
        }
        _set_session(ctx.author.id, session)

        try:
            await ctx.author.send(
                "**World of Darkness — Character Creation**\n"
                "*Vampire: The Requiem*\n\n"
                "Let's build your Kindred step by step.\n"
                "*Tip: Type `!wcc restart` at any point to start over.*\n\n"
                "**Step 1: Name**\n"
                "What is your character's name?\n"
                "Reply with: `!wcc <name>`\n"
                "Example: `!wcc Marcus Ashton`"
            )
            await ctx.send(f"{ctx.author.mention} Check your DMs — WoD character creation has started!")
        except discord.Forbidden:
            _clear_session(ctx.author.id)
            await ctx.send("I can't DM you! Please enable DMs from server members.")

    @commands.command(name="wcc")
    async def wod_creation_choice(self, ctx: commands.Context, *, choice: str = ""):
        """Make a choice during WoD character creation (use in DMs).

        Usage: !wcc <your choice>
        """
        session = _get_session(ctx.author.id)
        if not session:
            await ctx.send("No WoD character creation in progress. Use `!createwod` in a server channel.")
            return

        reaction_task = session.get("_reaction_task")
        if reaction_task and not reaction_task.done():
            reaction_task.cancel()
            session["_reaction_task"] = None

        if ctx.guild is not None:
            await ctx.send(f"{ctx.author.mention} Character creation happens in DMs! Use `!wcc` there.")
            return

        if choice.strip().lower() == "restart":
            session["step"] = "name"
            char = WoDCharacter(session["char"].owner_id, session["char"].owner_name)
            session["char"] = char
            _set_session(ctx.author.id, session)
            await ctx.send(
                "**Restarting character creation.**\n\n"
                "**Step 1: Name**\n"
                "What is your character's name?\n"
                "Reply with: `!wcc <name>`"
            )
            return

        await self._dispatch_step(ctx, choice)

    # ------------------------------------------------------------------
    # Creation steps
    # ------------------------------------------------------------------

    async def _step_name(self, ctx, session, char: WoDCharacter, choice: str):
        char.name = choice.strip()[:50]
        session["step"] = "gender"
        _set_session(ctx.author.id, session)
        await self._send_with_reactions(
            ctx,
            f"**{char.name}** — great name.\n\n**Step 2: Gender**\nChoose your character's gender:",
            ["Male", "Female", "Non-Binary"],
            emojis=["\u2642\ufe0f", "\u2640\ufe0f", "\u26a7\ufe0f"],
            expected_step="gender",
        )

    async def _step_gender(self, ctx, session, char: WoDCharacter, choice: str):
        char.gender = choice.strip()[:30]
        session["step"] = "concept"
        _set_session(ctx.author.id, session)
        await ctx.send(
            "**Step 3: Concept**\n"
            "A one-line concept that defines your character.\n"
            "Examples: *Jaded detective*, *Ambitious socialite*, *Underground fight club owner*\n\n"
            "Reply with: `!wcc <concept>`"
        )

    async def _step_concept(self, ctx, session, char: WoDCharacter, choice: str):
        char.concept = choice.strip()[:100]
        session["step"] = "clan"
        _set_session(ctx.author.id, session)

        clan_names = get_clan_names()
        display = []
        for name in clan_names:
            data = get_clan_data(name)
            disc = ", ".join(data["clan_disciplines"])
            display.append(f"**{name}** ({data['nickname']}) — {disc}")

        await self._send_with_reactions(
            ctx,
            "**Step 4: Clan**\nChoose your vampire clan:",
            clan_names,
            display_options=display,
            expected_step="clan",
        )

    async def _step_clan(self, ctx, session, char: WoDCharacter, choice: str):
        # Accept number or name
        clan_names = get_clan_names()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(clan_names):
                choice = clan_names[idx]
        except ValueError:
            pass

        # Fuzzy match
        match = None
        for name in clan_names:
            if name.lower() == choice.strip().lower():
                match = name
                break
        if not match:
            for name in clan_names:
                if name.lower().startswith(choice.strip().lower()):
                    match = name
                    break
        if not match:
            await ctx.send(f"Unknown clan. Choose from: {', '.join(clan_names)}")
            return

        char.clan = match
        clan_data = get_clan_data(match)

        session["step"] = "covenant"
        _set_session(ctx.author.id, session)

        await ctx.send(f"You are now a **{match}** — *{clan_data['nickname']}*\n{clan_data['description']}")

        cov_names = get_covenant_names()
        display = [f"**{name}**" for name in cov_names]
        display.append("**Unaligned** (no covenant)")

        await self._send_with_reactions(
            ctx,
            "\n**Step 5: Covenant**\nChoose your covenant (or go unaligned):",
            cov_names + ["Unaligned"],
            display_options=display,
            expected_step="covenant",
        )

    async def _step_covenant(self, ctx, session, char: WoDCharacter, choice: str):
        cov_names = get_covenant_names() + ["Unaligned"]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(cov_names):
                choice = cov_names[idx]
        except ValueError:
            pass

        match = None
        for name in cov_names:
            if name.lower() == choice.strip().lower():
                match = name
                break
        if not match:
            for name in cov_names:
                if name.lower().startswith(choice.strip().lower()):
                    match = name
                    break
        if not match:
            await ctx.send(f"Unknown covenant. Choose from: {', '.join(cov_names)}")
            return

        char.covenant = match if match != "Unaligned" else ""

        session["step"] = "virtue"
        _set_session(ctx.author.id, session)

        await self._send_with_reactions(
            ctx,
            "**Step 6: Virtue**\nChoose your character's guiding Virtue:",
            VIRTUES,
            expected_step="virtue",
        )

    async def _step_virtue(self, ctx, session, char: WoDCharacter, choice: str):
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(VIRTUES):
                choice = VIRTUES[idx]
        except ValueError:
            pass
        choice = choice.strip().title()
        if choice not in VIRTUES:
            await ctx.send(f"Choose from: {', '.join(VIRTUES)}")
            return

        char.virtue = choice
        session["step"] = "vice"
        _set_session(ctx.author.id, session)

        await self._send_with_reactions(
            ctx,
            "**Step 7: Vice**\nChoose your character's Vice:",
            VICES,
            expected_step="vice",
        )

    async def _step_vice(self, ctx, session, char: WoDCharacter, choice: str):
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(VICES):
                choice = VICES[idx]
        except ValueError:
            pass
        choice = choice.strip().title()
        if choice not in VICES:
            await ctx.send(f"Choose from: {', '.join(VICES)}")
            return

        char.vice = choice
        session["step"] = "attr_priority"
        _set_session(ctx.author.id, session)

        await ctx.send(
            "**Step 8: Attributes**\n"
            "In WoD, you prioritize three categories: **Mental**, **Physical**, **Social**.\n"
            "- **Primary:** 5 dots to distribute (one attribute starts at 1, you add 5)\n"
            "- **Secondary:** 4 dots to distribute\n"
            "- **Tertiary:** 3 dots to distribute\n"
            "(All attributes start at 1)\n\n"
            "Choose your **PRIMARY** category first:"
        )
        await self._send_with_reactions(
            ctx, "",
            ["Mental", "Physical", "Social"],
            display_options=[
                f"**Mental** (Intelligence, Wits, Resolve)",
                f"**Physical** (Strength, Dexterity, Stamina)",
                f"**Social** (Presence, Manipulation, Composure)",
            ],
            expected_step="attr_priority",
        )

    async def _step_attr_priority(self, ctx, session, char: WoDCharacter, choice: str):
        priorities = session.get("attr_priorities", [])
        choice = choice.strip().title()
        valid = ["Mental", "Physical", "Social"]

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(valid):
                choice = valid[idx]
        except ValueError:
            pass

        remaining = [v for v in valid if v not in priorities]
        if choice not in remaining:
            await ctx.send(f"Choose from: {', '.join(remaining)}")
            return

        priorities.append(choice)
        session["attr_priorities"] = priorities

        if len(priorities) == 1:
            _set_session(ctx.author.id, session)
            remaining = [v for v in valid if v not in priorities]
            await self._send_with_reactions(
                ctx,
                f"Primary: **{priorities[0]}** (5 dots)\n\nChoose your **SECONDARY** category:",
                remaining,
                display_options=[f"**{r}**" for r in remaining],
                expected_step="attr_priority",
            )
        elif len(priorities) == 2:
            tertiary = [v for v in valid if v not in priorities][0]
            priorities.append(tertiary)
            session["attr_priorities"] = priorities
            # Now assign primary attributes
            session["step"] = "attr_assign_primary"
            session["attr_dots_remaining"] = 5
            session["attr_current_category"] = priorities[0]
            _set_session(ctx.author.id, session)

            await ctx.send(
                f"Priorities set: **{priorities[0]}** (5) > **{priorities[1]}** (4) > **{priorities[2]}** (3)\n\n"
                f"Now distribute **5 dots** among your {priorities[0]} attributes.\n"
                f"All start at 1. Max 5 each. Assign dots with:\n"
                f"`!wcc <Attribute> <dots>`\n"
                f"Example: `!wcc Intelligence 3` (sets Intelligence to 1+3=4)\n\n"
                f"**{priorities[0]} Attributes:** {', '.join(self._get_attrs_for_category(priorities[0]))}\n"
                f"Dots remaining: **5**"
            )

    def _get_attrs_for_category(self, category: str) -> list[str]:
        if category == "Mental":
            return WOD_MENTAL_ATTRIBUTES
        elif category == "Physical":
            return WOD_PHYSICAL_ATTRIBUTES
        elif category == "Social":
            return WOD_SOCIAL_ATTRIBUTES
        return []

    def _get_skills_for_category(self, category: str) -> list[str]:
        if category == "Mental":
            return WOD_MENTAL_SKILLS
        elif category == "Physical":
            return WOD_PHYSICAL_SKILLS
        elif category == "Social":
            return WOD_SOCIAL_SKILLS
        return []

    async def _step_attr_assign(self, ctx, session, char: WoDCharacter, choice: str):
        """Handle attribute dot assignment for current category."""
        category = session["attr_current_category"]
        attrs = self._get_attrs_for_category(category)
        remaining = session["attr_dots_remaining"]

        # Parse "AttributeName dots" or "done"
        choice = choice.strip()
        if choice.lower() == "done":
            if remaining > 0:
                await ctx.send(f"You still have **{remaining}** dots to assign!")
                return
            # Move to next category
            await self._advance_attr_category(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("Format: `!wcc <Attribute> <dots>` — e.g., `!wcc Strength 3`")
            return

        attr_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("Format: `!wcc <Attribute> <dots>` — dots must be a number.")
            return

        # Match attribute name
        match = None
        for a in attrs:
            if a.lower() == attr_name.lower() or a.lower().startswith(attr_name.lower()):
                match = a
                break
        if not match:
            await ctx.send(f"Unknown attribute. Choose from: {', '.join(attrs)}")
            return

        # Validate
        already_assigned = char.attributes[match] - 1  # subtract base 1
        available = remaining + already_assigned  # give back any previously assigned
        if dots < 0 or dots > 4:  # max +4 (base 1 + 4 = 5)
            await ctx.send("Dots must be 0-4 (attributes range 1-5, start at 1).")
            return
        if dots > available:
            await ctx.send(f"Not enough dots. You have {remaining} remaining (this attribute has {already_assigned} assigned).")
            return

        # Apply
        session["attr_dots_remaining"] = remaining + already_assigned - dots
        char.attributes[match] = 1 + dots
        _set_session(ctx.author.id, session)

        # Show status
        lines = [f"**{match}** set to **{char.attributes[match]}**"]
        lines.append(f"\n**{category} Attributes:**")
        for a in attrs:
            dot_str = "O" * char.attributes[a] + "." * (5 - char.attributes[a])
            lines.append(f"  {a}: {dot_str} ({char.attributes[a]})")
        lines.append(f"\nDots remaining: **{session['attr_dots_remaining']}**")

        if session["attr_dots_remaining"] == 0:
            lines.append("\nAll dots assigned! Type `!wcc done` to continue, or adjust with `!wcc <Attr> <dots>`.")

        await ctx.send("\n".join(lines))

    async def _advance_attr_category(self, ctx, session, char: WoDCharacter):
        """Move to the next attribute category or to skills."""
        priorities = session["attr_priorities"]
        step = session["step"]

        if step == "attr_assign_primary":
            session["step"] = "attr_assign_secondary"
            session["attr_dots_remaining"] = 4
            session["attr_current_category"] = priorities[1]
            _set_session(ctx.author.id, session)
            attrs = self._get_attrs_for_category(priorities[1])
            await ctx.send(
                f"**{priorities[1]} Attributes** — distribute **4 dots**:\n"
                f"Attributes: {', '.join(attrs)}\n"
                f"Dots remaining: **4**\n\n"
                f"`!wcc <Attribute> <dots>` — then `!wcc done` when finished."
            )
        elif step == "attr_assign_secondary":
            session["step"] = "attr_assign_tertiary"
            session["attr_dots_remaining"] = 3
            session["attr_current_category"] = priorities[2]
            _set_session(ctx.author.id, session)
            attrs = self._get_attrs_for_category(priorities[2])
            await ctx.send(
                f"**{priorities[2]} Attributes** — distribute **3 dots**:\n"
                f"Attributes: {', '.join(attrs)}\n"
                f"Dots remaining: **3**\n\n"
                f"`!wcc <Attribute> <dots>` — then `!wcc done` when finished."
            )
        elif step == "attr_assign_tertiary":
            # Attributes done — move to skills
            session["step"] = "skill_priority"
            _set_session(ctx.author.id, session)
            await ctx.send(
                "Attributes complete!\n\n"
                "**Step 9: Skills**\n"
                "Prioritize skill categories just like attributes:\n"
                "- **Primary:** 11 dots\n"
                "- **Secondary:** 7 dots\n"
                "- **Tertiary:** 4 dots\n"
                "(Skills start at 0. Max 5, but during creation max 3.)\n\n"
                "Choose your **PRIMARY** skill category:"
            )
            await self._send_with_reactions(
                ctx, "",
                ["Mental", "Physical", "Social"],
                display_options=[
                    f"**Mental** ({', '.join(WOD_MENTAL_SKILLS[:4])}...)",
                    f"**Physical** ({', '.join(WOD_PHYSICAL_SKILLS[:4])}...)",
                    f"**Social** ({', '.join(WOD_SOCIAL_SKILLS[:4])}...)",
                ],
                expected_step="skill_priority",
            )

    async def _step_skill_priority(self, ctx, session, char: WoDCharacter, choice: str):
        priorities = session.get("skill_priorities", [])
        choice = choice.strip().title()
        valid = ["Mental", "Physical", "Social"]

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(valid):
                choice = valid[idx]
        except ValueError:
            pass

        remaining = [v for v in valid if v not in priorities]
        if choice not in remaining:
            await ctx.send(f"Choose from: {', '.join(remaining)}")
            return

        priorities.append(choice)
        session["skill_priorities"] = priorities

        if len(priorities) == 1:
            _set_session(ctx.author.id, session)
            remaining = [v for v in valid if v not in priorities]
            await self._send_with_reactions(
                ctx,
                f"Primary: **{priorities[0]}** (11 dots)\n\nChoose your **SECONDARY** category:",
                remaining,
                display_options=[f"**{r}**" for r in remaining],
                expected_step="skill_priority",
            )
        elif len(priorities) == 2:
            tertiary = [v for v in valid if v not in priorities][0]
            priorities.append(tertiary)
            session["skill_priorities"] = priorities
            session["step"] = "skill_assign_primary"
            dots_map = {0: 11, 1: 7, 2: 4}
            session["skill_dots_remaining"] = dots_map[0]
            session["skill_current_category"] = priorities[0]
            _set_session(ctx.author.id, session)

            skills = self._get_skills_for_category(priorities[0])
            await ctx.send(
                f"Priorities: **{priorities[0]}** (11) > **{priorities[1]}** (7) > **{priorities[2]}** (4)\n\n"
                f"Distribute **11 dots** among {priorities[0]} skills (max 3 each at creation):\n"
                f"Skills: {', '.join(skills)}\n\n"
                f"`!wcc <Skill> <dots>` — then `!wcc done` when finished.\n"
                f"Dots remaining: **11**"
            )

    async def _step_skill_assign(self, ctx, session, char: WoDCharacter, choice: str):
        """Handle skill dot assignment for current category."""
        category = session["skill_current_category"]
        skills = self._get_skills_for_category(category)
        remaining = session["skill_dots_remaining"]

        choice = choice.strip()
        if choice.lower() == "done":
            if remaining > 0:
                await ctx.send(f"You still have **{remaining}** dots to assign!")
                return
            await self._advance_skill_category(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("Format: `!wcc <Skill> <dots>` — e.g., `!wcc Athletics 3`")
            return

        skill_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("Format: `!wcc <Skill> <dots>` — dots must be a number.")
            return

        # Match skill name
        match = None
        for s in skills:
            if s.lower() == skill_name.lower() or s.lower().startswith(skill_name.lower()):
                match = s
                break
        # Also try "Animal Ken" as "animal"
        if not match:
            for s in skills:
                if skill_name.lower() in s.lower():
                    match = s
                    break
        if not match:
            await ctx.send(f"Unknown skill. Choose from: {', '.join(skills)}")
            return

        already_assigned = char.skills.get(match, 0)
        available = remaining + already_assigned
        if dots < 0 or dots > 3:
            await ctx.send("Dots must be 0-3 during character creation.")
            return
        if dots > available:
            await ctx.send(f"Not enough dots. You have {remaining} remaining.")
            return

        session["skill_dots_remaining"] = remaining + already_assigned - dots
        char.skills[match] = dots
        _set_session(ctx.author.id, session)

        lines = [f"**{match}** set to **{dots}**"]
        lines.append(f"\n**{category} Skills:**")
        for s in skills:
            v = char.skills.get(s, 0)
            dot_str = ("O" * v + "." * (3 - v)) if v > 0 else "..."
            lines.append(f"  {s}: {dot_str} ({v})")
        lines.append(f"\nDots remaining: **{session['skill_dots_remaining']}**")

        if session["skill_dots_remaining"] == 0:
            lines.append("\nAll dots assigned! Type `!wcc done` to continue.")

        await ctx.send("\n".join(lines))

    async def _advance_skill_category(self, ctx, session, char: WoDCharacter):
        """Move to next skill category or to specialties."""
        priorities = session["skill_priorities"]
        step = session["step"]
        dots_map = {"skill_assign_primary": 7, "skill_assign_secondary": 4}
        next_step = {
            "skill_assign_primary": "skill_assign_secondary",
            "skill_assign_secondary": "skill_assign_tertiary",
        }

        if step in next_step:
            next_s = next_step[step]
            idx = 1 if step == "skill_assign_primary" else 2
            session["step"] = next_s
            session["skill_dots_remaining"] = dots_map.get(step, 4)
            session["skill_current_category"] = priorities[idx]
            _set_session(ctx.author.id, session)

            skills = self._get_skills_for_category(priorities[idx])
            dots = session["skill_dots_remaining"]
            await ctx.send(
                f"**{priorities[idx]} Skills** — distribute **{dots} dots** (max 3 each):\n"
                f"Skills: {', '.join(skills)}\n"
                f"Dots remaining: **{dots}**\n\n"
                f"`!wcc <Skill> <dots>` — then `!wcc done` when finished."
            )
        else:
            # Skills done — move to specialties
            session["step"] = "specialties"
            session["specialties_remaining"] = 3
            _set_session(ctx.author.id, session)
            await ctx.send(
                "Skills complete!\n\n"
                "**Step 10: Specialties**\n"
                "Choose **3 skill specialties** — a narrow focus within a skill you have.\n"
                "Format: `!wcc <Skill>: <Specialty>`\n"
                "Example: `!wcc Firearms: Pistols`\n"
                "Example: `!wcc Academics: History`\n\n"
                f"Specialties remaining: **3**"
            )

    async def _step_specialties(self, ctx, session, char: WoDCharacter, choice: str):
        remaining = session.get("specialties_remaining", 3)

        if choice.strip().lower() == "done":
            if remaining > 0:
                await ctx.send(f"You still have **{remaining}** specialties to assign. Use `!wcc skip` to skip.")
                return
            await self._advance_to_disciplines(ctx, session, char)
            return

        if choice.strip().lower() == "skip":
            await self._advance_to_disciplines(ctx, session, char)
            return

        if ":" not in choice:
            await ctx.send("Format: `!wcc <Skill>: <Specialty>` — e.g., `!wcc Firearms: Pistols`")
            return

        parts = choice.split(":", 1)
        skill_name = parts[0].strip()
        specialty = parts[1].strip()

        if not specialty:
            await ctx.send("Please provide a specialty name after the colon.")
            return

        # Match skill
        match = None
        for s in WOD_ALL_SKILLS:
            if s.lower() == skill_name.lower() or s.lower().startswith(skill_name.lower()):
                match = s
                break
        if not match:
            for s in WOD_ALL_SKILLS:
                if skill_name.lower() in s.lower():
                    match = s
                    break
        if not match:
            await ctx.send(f"Unknown skill: {skill_name}")
            return

        if match not in char.specialties:
            char.specialties[match] = []
        char.specialties[match].append(specialty)
        session["specialties_remaining"] = remaining - 1
        _set_session(ctx.author.id, session)

        rem = session["specialties_remaining"]
        await ctx.send(
            f"Added specialty: **{match}: {specialty}**\n"
            f"Specialties remaining: **{rem}**" +
            ("\nType `!wcc done` to continue." if rem == 0 else "")
        )

        if rem == 0:
            await self._advance_to_disciplines(ctx, session, char)

    async def _advance_to_disciplines(self, ctx, session, char: WoDCharacter):
        """Move to discipline selection."""
        clan_discs = get_clan_disciplines(char.clan)
        session["step"] = "disciplines"
        session["discipline_dots_remaining"] = 3
        session["clan_disciplines"] = clan_discs
        _set_session(ctx.author.id, session)

        disc_display = []
        for d in clan_discs:
            data = get_discipline_data(d)
            if data:
                p1 = data["powers"].get(1, {})
                disc_display.append(f"**{d}** — {data['description']}\n  Level 1: {p1.get('name', '?')}: {p1.get('description', '')}")

        await ctx.send(
            "**Step 11: Disciplines**\n"
            f"As a **{char.clan}**, your clan disciplines are:\n\n"
            + "\n".join(disc_display) + "\n\n"
            "Distribute **3 dots** among your clan disciplines (max 2 per discipline at creation).\n"
            "Format: `!wcc <Discipline> <dots>`\n"
            "Example: `!wcc Celerity 2`\n\n"
            f"Dots remaining: **3**"
        )

    async def _step_disciplines(self, ctx, session, char: WoDCharacter, choice: str):
        remaining = session.get("discipline_dots_remaining", 3)
        clan_discs = session.get("clan_disciplines", [])

        if choice.strip().lower() == "done":
            if remaining > 0:
                await ctx.send(f"You still have **{remaining}** dots to assign!")
                return
            await self._advance_to_merits(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("Format: `!wcc <Discipline> <dots>` — e.g., `!wcc Celerity 2`")
            return

        disc_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("Dots must be a number.")
            return

        # Match discipline
        match = None
        for d in clan_discs:
            if d.lower() == disc_name.lower() or d.lower().startswith(disc_name.lower()):
                match = d
                break
        if not match:
            await ctx.send(f"Choose from your clan disciplines: {', '.join(clan_discs)}")
            return

        already = char.disciplines.get(match, 0)
        available = remaining + already
        if dots < 0 or dots > 2:
            await ctx.send("Max 2 dots per discipline at character creation.")
            return
        if dots > available:
            await ctx.send(f"Not enough dots. You have {remaining} remaining.")
            return

        session["discipline_dots_remaining"] = remaining + already - dots
        if dots > 0:
            char.disciplines[match] = dots
        elif match in char.disciplines:
            del char.disciplines[match]
        _set_session(ctx.author.id, session)

        lines = [f"**{match}** set to **{dots}**"]
        for d in clan_discs:
            v = char.disciplines.get(d, 0)
            dot_str = "O" * v + "." * (2 - v)
            lines.append(f"  {d}: {dot_str} ({v})")
        lines.append(f"\nDots remaining: **{session['discipline_dots_remaining']}**")

        if session["discipline_dots_remaining"] == 0:
            lines.append("\nType `!wcc done` to continue.")

        await ctx.send("\n".join(lines))

    async def _advance_to_merits(self, ctx, session, char: WoDCharacter):
        """Move to merit selection."""
        session["step"] = "merits"
        session["merit_dots_remaining"] = MERIT_DOTS_AT_CREATION
        _set_session(ctx.author.id, session)

        # Show available merits
        categories = ["Physical", "Mental", "Social", "Vampire"]
        lines = [
            "**Step 12: Merits**\n"
            f"You have **{MERIT_DOTS_AT_CREATION} dots** to spend on merits.\n"
        ]
        for cat in categories:
            cat_merits = {k: v for k, v in MERITS.items() if v["category"] == cat}
            if cat_merits:
                lines.append(f"**{cat}:**")
                for name, data in sorted(cat_merits.items()):
                    dot_options = "/".join(str(d) for d in data["dots"])
                    lines.append(f"  {name} ({dot_options}) — {data['description'][:60]}")

        lines.append(
            f"\nFormat: `!wcc <Merit> <dots>`\n"
            f"Example: `!wcc Resources 3`\n"
            f"Type `!wcc done` when finished (unspent dots are lost)."
        )
        # Split if too long
        text = "\n".join(lines)
        while len(text) > 1900:
            split_at = text.rfind("\n", 0, 1900)
            await ctx.send(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            await ctx.send(text)

    async def _step_merits(self, ctx, session, char: WoDCharacter, choice: str):
        remaining = session.get("merit_dots_remaining", 7)

        if choice.strip().lower() == "done" or choice.strip().lower() == "skip":
            await self._advance_to_backstory(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("Format: `!wcc <Merit> <dots>` — e.g., `!wcc Resources 3`")
            return

        merit_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("Dots must be a number.")
            return

        # Match merit
        all_merits = get_merit_names()
        match = None
        for m in all_merits:
            if m.lower() == merit_name.lower():
                match = m
                break
        if not match:
            for m in all_merits:
                if m.lower().startswith(merit_name.lower()):
                    match = m
                    break
        if not match:
            for m in all_merits:
                if merit_name.lower() in m.lower():
                    match = m
                    break
        if not match:
            await ctx.send(f"Unknown merit: {merit_name}. Type `!wcc done` to skip merits.")
            return

        merit_data = MERITS[match]
        if dots not in merit_data["dots"]:
            valid = ", ".join(str(d) for d in merit_data["dots"])
            await ctx.send(f"{match} can only be taken at: {valid} dots.")
            return

        already = char.merits.get(match, 0)
        cost = dots - already
        if cost > remaining:
            await ctx.send(f"Not enough dots. You have {remaining} remaining, need {cost}.")
            return

        char.merits[match] = dots
        session["merit_dots_remaining"] = remaining - cost
        _set_session(ctx.author.id, session)

        await ctx.send(
            f"**{match}** set to **{dots}** dots.\n"
            f"Merit dots remaining: **{session['merit_dots_remaining']}**\n"
            f"Current merits: {', '.join(f'{k} {v}' for k, v in char.merits.items())}\n"
            f"Type `!wcc done` when finished."
        )

    async def _advance_to_backstory(self, ctx, session, char: WoDCharacter):
        session["step"] = "backstory"
        _set_session(ctx.author.id, session)
        await ctx.send(
            "**Step 13: Backstory**\n"
            "Write a brief backstory for your character. Include:\n"
            "- Who they were as a mortal\n"
            "- How they were Embraced (turned into a vampire)\n"
            "- What drives them in their Requiem (undead existence)\n\n"
            "Reply with: `!wcc <backstory>`\n"
            "(Or `!wcc skip` to skip for now)"
        )

    async def _step_backstory(self, ctx, session, char: WoDCharacter, choice: str):
        if choice.strip().lower() != "skip":
            char.backstory = choice.strip()[:1000]

        # Finalize character
        char.finalize()

        session["step"] = "confirm"
        _set_session(ctx.author.id, session)

        sheet = char.format_sheet()
        await self._send_long(ctx, sheet)
        await ctx.send(
            "\n**Does this look correct?**\n"
            "Reply `!wcc yes` to confirm or `!wcc no` to start over."
        )

    async def _step_confirm(self, ctx, session, char: WoDCharacter, choice: str):
        choice = choice.strip().lower()
        if choice in ("yes", "y", "confirm"):
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
                f"Use `!wodsheet` in the server channel to view your character sheet."
            )

            try:
                guild_channel = self.bot.get_channel(int(channel_id))
                if guild_channel:
                    cov_str = f", {char.covenant}" if char.covenant else ""
                    await guild_channel.send(
                        f"**{char.name}** (Clan {char.clan}{cov_str}) has joined the coterie! "
                        f"Created by {ctx.author.mention}."
                    )
            except Exception:
                pass

        elif choice in ("no", "n", "restart"):
            _clear_session(ctx.author.id)
            await ctx.send("Character creation cancelled. Use `!createwod` in a server channel to start over.")
        else:
            await ctx.send("Reply `!wcc yes` to confirm or `!wcc no` to start over.")

    async def _send_long(self, ctx, text: str):
        while len(text) > 1990:
            split_at = text.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await ctx.send(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            await ctx.send(text)


async def setup(bot: commands.Bot):
    await bot.add_cog(WoDCharacterCog(bot))

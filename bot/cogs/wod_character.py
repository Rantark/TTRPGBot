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
    VIRTUE_DATA, VICE_DATA,
    get_clan_names, get_clan_data, get_covenant_names,
)
from bot.data.wod_disciplines import (
    get_clan_disciplines, get_discipline_data, get_discipline_names,
)
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


# ── Emoji constants ──
NUMBER_EMOJIS = [
    "1\u20e3", "2\u20e3", "3\u20e3", "4\u20e3", "5\u20e3",
    "6\u20e3", "7\u20e3", "8\u20e3", "9\u20e3", "\U0001f51f"
]
CONFIRM_EMOJIS = ["\u2705", "\u274c"]
# Edit-mode navigation emojis
NAV_PREV = "\u25c0\ufe0f"   # ◀️
NAV_NEXT = "\u25b6\ufe0f"   # ▶️
EDIT_PLUS = "\u2795"         # ➕
EDIT_MINUS = "\u2796"        # ➖
EDIT_SAVE = "\u2705"         # ✅
EDIT_NAV_EMOJIS = [NAV_PREV, NAV_NEXT, EDIT_PLUS, EDIT_MINUS, EDIT_SAVE]

# Step emojis for the progress bar
STEP_EMOJIS = {
    "name": "\U0001f4db",          # 📛
    "gender": "\u26a7\ufe0f",      # ⚧️
    "concept": "\U0001f4a1",       # 💡
    "clan": "\U0001f9db",          # 🧛
    "covenant": "\U0001f3db\ufe0f",  # 🏛️
    "virtue": "\u2728",            # ✨
    "vice": "\U0001f608",          # 😈
    "attributes": "\U0001f4aa",    # 💪
    "skills": "\U0001f4da",        # 📚
    "specialties": "\U0001f3af",   # 🎯
    "disciplines": "\U0001fa78",   # 🩸
    "merits": "\u2b50",            # ⭐
    "backstory": "\U0001f4d6",     # 📖
    "confirm": "\u2705",           # ✅
}

# Category emojis
CAT_EMOJIS = {
    "Mental": "\U0001f9e0",    # 🧠
    "Physical": "\U0001f4aa",  # 💪
    "Social": "\U0001f5e3\ufe0f",  # 🗣️
}

# Merit category emojis
MERIT_CAT_EMOJIS = {
    "Physical": "\U0001f3cb\ufe0f",  # 🏋️
    "Mental": "\U0001f9e0",          # 🧠
    "Social": "\U0001f465",          # 👥
    "Vampire": "\U0001f9db",         # 🧛
}

# Creation step order for progress tracking
CREATION_STEPS = [
    "name", "gender", "concept", "clan", "covenant",
    "virtue", "vice", "attributes", "skills",
    "specialties", "disciplines", "merits", "backstory", "confirm",
]

# Map internal step names to progress steps
STEP_TO_PROGRESS = {
    "name": "name", "gender": "gender", "concept": "concept",
    "clan": "clan", "covenant": "covenant", "virtue": "virtue", "vice": "vice",
    "attr_priority": "attributes", "attr_assign_primary": "attributes",
    "attr_assign_secondary": "attributes", "attr_assign_tertiary": "attributes",
    "skill_priority": "skills", "skill_assign_primary": "skills",
    "skill_assign_secondary": "skills", "skill_assign_tertiary": "skills",
    "specialties": "specialties", "disciplines": "disciplines",
    "merits": "merits", "backstory": "backstory", "confirm": "confirm",
}


def _progress_bar(current_step: str) -> str:
    """Generate a visual progress bar for character creation."""
    progress_step = STEP_TO_PROGRESS.get(current_step, current_step)
    try:
        idx = CREATION_STEPS.index(progress_step)
    except ValueError:
        idx = 0

    total = len(CREATION_STEPS)
    filled = idx
    pct = int((filled / total) * 100)

    bar_len = 14
    filled_blocks = int((filled / total) * bar_len)
    bar = "\u2593" * filled_blocks + "\u2591" * (bar_len - filled_blocks)

    return f"`[{bar}]` {pct}% \u2014 Step {idx + 1}/{total}"


def _dot_display(current: int, maximum: int = 5) -> str:
    """Render dots as filled/empty circles."""
    return "\u25cf" * current + "\u25cb" * (maximum - current)


def _make_embed(title: str, description: str = "", color: discord.Color = None,
                step: str = None) -> discord.Embed:
    """Create a styled embed with optional progress footer."""
    if color is None:
        color = discord.Color.dark_red()
    embed = discord.Embed(title=title, description=description, color=color)
    if step:
        embed.set_footer(text=_progress_bar(step))
    return embed


class WoDCharacterCog(commands.Cog, name="WoD Character"):
    """Commands for World of Darkness character creation and management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx: commands.Context):
        return load_campaign(str(ctx.channel.id))

    def _is_wod_campaign(self, campaign) -> bool:
        return campaign and campaign.game_system == GameSystem.WOD

    async def _wizard_send(self, ctx, session, embed: discord.Embed):
        """Update the wizard message in place, or send a new one.

        Keeps the creation flow in a single updating message.
        """
        # Add progress bar to footer
        step = session.get("step", "")
        embed.set_footer(text=_progress_bar(step))

        wizard_msg = session.get("wizard_msg")
        if wizard_msg:
            try:
                await wizard_msg.edit(embed=embed)
                # Clear old reactions — try bulk clear first, fall back to
                # removing the bot's own reactions one-by-one if that fails
                # (e.g. missing Manage Messages permission).
                cleared = False
                try:
                    await wizard_msg.clear_reactions()
                    cleared = True
                except discord.HTTPException:
                    pass
                if not cleared:
                    old_emojis = session.pop("_active_emojis", [])
                    for em in old_emojis:
                        try:
                            await wizard_msg.remove_reaction(em, self.bot.user)
                        except discord.HTTPException:
                            pass
                return wizard_msg
            except discord.HTTPException:
                pass

        msg = await ctx.send(embed=embed)
        session["wizard_msg"] = msg
        _set_session(ctx.author.id, session)
        return msg

    async def _send_with_reactions(self, ctx, embed: discord.Embed,
                                    options: list[str],
                                    emojis: list[str] = None,
                                    expected_step: str = ""):
        """Update the wizard embed with emoji reactions for selection."""
        session = _get_session(ctx.author.id)

        if len(options) > 10 or not options:
            if session:
                msg = await self._wizard_send(ctx, session, embed)
            else:
                await ctx.send(embed=embed)
            return

        if emojis is None:
            emojis = NUMBER_EMOJIS[:len(options)]
        else:
            emojis = emojis[:len(options)]

        if session:
            msg = await self._wizard_send(ctx, session, embed)
        else:
            msg = await ctx.send(embed=embed)

        # Add reactions and track them so _wizard_send can remove them later
        for emoji in emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                pass
        session = _get_session(ctx.author.id)
        if session:
            session["_active_emojis"] = list(emojis)
            _set_session(ctx.author.id, session)

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
        embeds = self._build_sheet_embeds(char)
        for embed in embeds:
            await ctx.send(embed=embed)

    def _build_sheet_embeds(self, char) -> list[discord.Embed]:
        """Build rich Discord embeds for a WoD character sheet."""
        embeds = []
        dots = _dot_display

        # ── Header embed ──
        clan_data = get_clan_data(char.clan) if char.clan else None
        clan_emoji = clan_data.get("emoji", "\U0001f9db") if clan_data else "\U0001f9db"
        gender_str = f" | {char.gender}" if char.gender else ""

        desc_lines = [f"{clan_emoji} **Clan {char.clan}**{gender_str}"]
        if char.covenant:
            cov_data = COVENANTS.get(char.covenant, {})
            cov_emoji = cov_data.get("emoji", "\U0001f3db\ufe0f")
            desc_lines.append(f"{cov_emoji} {char.covenant}")
        if char.concept:
            desc_lines.append(f"\U0001f4a1 *{char.concept}*")

        header = discord.Embed(
            title=f"\U0001f9db {char.name}",
            description="\n".join(desc_lines),
            color=discord.Color.dark_red(),
        )

        # Virtue / Vice
        virtue_vice_parts = []
        if char.virtue:
            v_data = VIRTUE_DATA.get(char.virtue, {})
            v_emoji = v_data.get("emoji", "\u2728")
            virtue_vice_parts.append(f"{v_emoji} **Virtue:** {char.virtue}")
        if char.vice:
            vc_data = VICE_DATA.get(char.vice, {})
            vc_emoji = vc_data.get("emoji", "\U0001f608")
            virtue_vice_parts.append(f"{vc_emoji} **Vice:** {char.vice}")
        if virtue_vice_parts:
            header.add_field(name="\u200b", value="\n".join(virtue_vice_parts), inline=False)

        # Vampire-specific stats
        if char.creature_type == "Vampire":
            bp_line = f"\U0001fa78 **Blood Potency:** {dots(char.blood_potency, 10)}"
            hum_line = f"\u2764\ufe0f **Humanity:** {dots(char.humanity, 10)}"
            vitae_line = f"\U0001f7e5 **Vitae:** {dots(char.vitae, char.vitae_max)} ({char.vitae}/{char.vitae_max}, {char.vitae_per_turn}/turn)"
            header.add_field(name="\u200b", value=f"{bp_line}\n{hum_line}\n{vitae_line}", inline=False)

        # Health & Willpower
        health_symbols = {"": "\u25a1", "B": "\u25a8", "L": "\u2716", "A": "\u2738"}
        if char.health_track:
            health_str = " ".join(health_symbols.get(d, "\u25a1") for d in char.health_track)
        else:
            health_str = "\u25a1 " * char.health_max
        wp_str = dots(char.willpower_current, char.willpower_max)

        header.add_field(
            name="\U0001f3e5 Health",
            value=f"{health_str}\n`[ ] Empty  [▨] Bash  [✖] Lethal  [✸] Agg`",
            inline=False,
        )
        header.add_field(
            name="\U0001f4a0 Willpower",
            value=f"{wp_str} ({char.willpower_current}/{char.willpower_max})",
            inline=True,
        )

        # Derived stats
        derived_parts = [
            f"\U0001f6e1\ufe0f **Defense:** {char.defense}",
            f"\u26a1 **Initiative:** +{char.initiative_mod}",
            f"\U0001f3c3 **Speed:** {char.speed}",
        ]
        if char.armor:
            derived_parts.append(f"\U0001f6e1\ufe0f **Armor:** {char.armor}")
        header.add_field(name="\u200b", value=" \u2502 ".join(derived_parts), inline=False)

        embeds.append(header)

        # ── Attributes embed ──
        attr_embed = discord.Embed(
            title="\U0001f4aa Attributes",
            color=discord.Color.dark_red(),
        )
        for cat_name, attr_list in [
            ("Mental", WOD_MENTAL_ATTRIBUTES),
            ("Physical", WOD_PHYSICAL_ATTRIBUTES),
            ("Social", WOD_SOCIAL_ATTRIBUTES),
        ]:
            cat_emoji = CAT_EMOJIS.get(cat_name, "")
            lines = []
            for attr in attr_list:
                val = char.attributes.get(attr, 1)
                lines.append(f"**{attr}:** {dots(val, 5)}")
            attr_embed.add_field(
                name=f"{cat_emoji} {cat_name}",
                value="\n".join(lines),
                inline=True,
            )
        embeds.append(attr_embed)

        # ── Skills embed ──
        skills_embed = discord.Embed(
            title="\U0001f4da Skills",
            color=discord.Color.dark_red(),
        )
        for cat_name, skill_list in [
            ("Mental", WOD_MENTAL_SKILLS),
            ("Physical", WOD_PHYSICAL_SKILLS),
            ("Social", WOD_SOCIAL_SKILLS),
        ]:
            cat_emoji = CAT_EMOJIS.get(cat_name, "")
            lines = []
            for sk in skill_list:
                val = char.skills.get(sk, 0)
                if val > 0:
                    lines.append(f"**{sk}:** {dots(val, 5)}")
                else:
                    lines.append(f"{sk}: {dots(0, 5)}")
            skills_embed.add_field(
                name=f"{cat_emoji} {cat_name}",
                value="\n".join(lines),
                inline=True,
            )

        # Specialties inline
        if char.specialties:
            spec_lines = []
            for skill, specs in char.specialties.items():
                spec_lines.append(f"\U0001f3af **{skill}:** {', '.join(specs)}")
            skills_embed.add_field(
                name="\U0001f3af Specialties",
                value="\n".join(spec_lines),
                inline=False,
            )
        embeds.append(skills_embed)

        # ── Disciplines & Merits embed ──
        if char.disciplines or char.merits:
            powers_embed = discord.Embed(
                title="\U0001fa78 Disciplines & \u2b50 Merits",
                color=discord.Color.dark_red(),
            )
            if char.disciplines:
                disc_lines = []
                for disc, val in sorted(char.disciplines.items()):
                    disc_lines.append(f"**{disc}:** {dots(val, 5)}")
                powers_embed.add_field(
                    name="\U0001fa78 Disciplines",
                    value="\n".join(disc_lines),
                    inline=True,
                )
            if char.merits:
                merit_lines = []
                for merit, val in sorted(char.merits.items()):
                    merit_lines.append(f"**{merit}:** {dots(val, 5)}")
                powers_embed.add_field(
                    name="\u2b50 Merits",
                    value="\n".join(merit_lines),
                    inline=True,
                )
            embeds.append(powers_embed)

        # ── Weapons & Equipment embed ──
        if char.weapons or char.inventory:
            gear_embed = discord.Embed(
                title="\u2694\ufe0f Gear",
                color=discord.Color.dark_red(),
            )
            if char.weapons:
                wep_lines = []
                for w in char.weapons:
                    dmg = w.get("damage", 0)
                    dtype = w.get("type", "B")
                    wep_lines.append(f"\u2694\ufe0f **{w['name']}** — Damage +{dmg} ({dtype})")
                gear_embed.add_field(
                    name="Weapons",
                    value="\n".join(wep_lines),
                    inline=False,
                )
            if char.inventory:
                items = [char._format_inv_item(e) for e in char.inventory[:10]]
                gear_embed.add_field(
                    name="\U0001f392 Equipment",
                    value=", ".join(items),
                    inline=False,
                )
            embeds.append(gear_embed)

        return embeds

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
                    f"\U0001fa78 **{char.name}** Vitae: {old} \u2192 {char.vitae}/{char.vitae_max}"
                )
            except ValueError:
                await ctx.send("Usage: `!vitae +3` or `!vitae -2`")
        else:
            pips = _dot_display(char.vitae, char.vitae_max)
            await ctx.send(
                f"\U0001fa78 **{char.name}** \u2014 Vitae: {char.vitae}/{char.vitae_max} [{pips}] "
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
        dots = _dot_display(char.humanity, 10)
        await ctx.send(f"\u2728 **{char.name}** \u2014 Humanity: {char.humanity}/10 [{dots}]")

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
                    f"\U0001f4a0 **{char.name}** Willpower: {old} \u2192 {char.willpower_current}/{char.willpower_max}"
                )
            except ValueError:
                await ctx.send("Usage: `!willpower -1` or `!willpower +1`")
        else:
            pips = _dot_display(char.willpower_current, char.willpower_max)
            await ctx.send(
                f"\U0001f4a0 **{char.name}** \u2014 Willpower: {char.willpower_current}/{char.willpower_max} [{pips}]"
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
            embed = _make_embed(
                "\U0001f9db Vampire: The Requiem \u2014 Character Creation",
                (
                    "Welcome to the World of Darkness! Let's build your Kindred, "
                    "step by step.\n\n"
                    "You'll choose your name, clan, covenant, attributes, skills, "
                    "and more. Each step has clear instructions.\n\n"
                    "\U0001f4cb **How it works:**\n"
                    "\u2022 React to emoji buttons **or** type `!wcc <choice>`\n"
                    "\u2022 Type `!wcc restart` at any point to start over\n"
                    "\u2022 Take your time \u2014 there's no rush!\n"
                    "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                    f"{STEP_EMOJIS['name']} **Step 1 of 14: Character Name**\n"
                    "What is your character's name?\n\n"
                    "Type: `!wcc <name>`\n"
                    "*Example:* `!wcc Marcus Ashton`"
                ),
                step="name",
            )
            wizard_msg = await ctx.author.send(embed=embed)
            session["wizard_msg"] = wizard_msg
            _set_session(ctx.author.id, session)
            await ctx.send(f"\U0001f9db {ctx.author.mention} Check your DMs \u2014 character creation has started!")
        except discord.Forbidden:
            _clear_session(ctx.author.id)
            await ctx.send("\u274c I can't DM you! Please enable DMs from server members.")

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
            embed = _make_embed(
                "\U0001f504 Restarting Character Creation",
                (
                    f"{STEP_EMOJIS['name']} **Step 1 of 14: Character Name**\n"
                    "What is your character's name?\n\n"
                    "Type: `!wcc <name>`\n"
                    "*Example:* `!wcc Marcus Ashton`"
                ),
                step="name",
            )
            await self._wizard_send(ctx, session, embed)
            return

        await self._dispatch_step(ctx, choice)

    # ------------------------------------------------------------------
    # Creation steps
    # ------------------------------------------------------------------

    async def _step_name(self, ctx, session, char: WoDCharacter, choice: str):
        char.name = choice.strip()[:50]
        session["step"] = "gender"
        _set_session(ctx.author.id, session)

        embed = _make_embed(
            f"{STEP_EMOJIS['gender']} Step 2 of 14: Gender",
            (
                f"\U0001f44d **{char.name}** \u2014 great name!\n\n"
                "Choose your character's gender:\n\n"
                "\u2642\ufe0f **Male**\n"
                "\u2640\ufe0f **Female**\n"
                "\u26a7\ufe0f **Non-Binary**\n\n"
                "*React below or type `!wcc Male/Female/Non-Binary`*"
            ),
            step="gender",
        )
        await self._send_with_reactions(
            ctx, embed,
            ["Male", "Female", "Non-Binary"],
            emojis=["\u2642\ufe0f", "\u2640\ufe0f", "\u26a7\ufe0f"],
            expected_step="gender",
        )

    async def _step_gender(self, ctx, session, char: WoDCharacter, choice: str):
        char.gender = choice.strip()[:30]
        session["step"] = "concept"
        _set_session(ctx.author.id, session)

        embed = _make_embed(
            f"{STEP_EMOJIS['concept']} Step 3 of 14: Character Concept",
            (
                "A **concept** is a one-line summary of who your character is.\n"
                "Think of it as their elevator pitch \u2014 what defined them in life?\n\n"
                "\U0001f4a1 **Examples:**\n"
                "\u2022 *Jaded detective who trusts no one*\n"
                "\u2022 *Ambitious socialite chasing power*\n"
                "\u2022 *Underground fight club owner*\n"
                "\u2022 *Disgraced surgeon seeking redemption*\n\n"
                "Type: `!wcc <your concept>`"
            ),
            step="concept",
        )
        await self._wizard_send(ctx, session, embed)

    async def _step_concept(self, ctx, session, char: WoDCharacter, choice: str):
        char.concept = choice.strip()[:100]
        session["step"] = "clan"
        _set_session(ctx.author.id, session)

        clan_names = get_clan_names()
        clan_emojis = []
        lines = [
            "Your **clan** determines your vampiric bloodline, supernatural powers "
            "(Disciplines), and your curse.\n"
        ]

        for i, name in enumerate(clan_names):
            data = get_clan_data(name)
            emoji = data.get("emoji", NUMBER_EMOJIS[i])
            clan_emojis.append(emoji)
            disc = ", ".join(data["clan_disciplines"])
            lines.append(
                f"{emoji} **{name}** \u2014 *\"{data['nickname']}\"*\n"
                f"> {data['description'][:120]}\n"
                f"> \U0001fa78 Disciplines: `{disc}`\n"
                f"> \U0001f3ae Playstyle: *{data.get('playstyle', '')}*\n"
            )

        lines.append("*React below or type `!wcc <clan name>`*")

        embed = _make_embed(
            f"{STEP_EMOJIS['clan']} Step 4 of 14: Choose Your Clan",
            "\n".join(lines),
            step="clan",
        )

        await self._send_with_reactions(
            ctx, embed, clan_names,
            emojis=clan_emojis,
            expected_step="clan",
        )

    async def _step_clan(self, ctx, session, char: WoDCharacter, choice: str):
        clan_names = get_clan_names()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(clan_names):
                choice = clan_names[idx]
        except ValueError:
            pass

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
            await ctx.send(f"\u274c Unknown clan. Choose from: {', '.join(clan_names)}")
            return

        char.clan = match
        clan_data = get_clan_data(match)

        # Move to covenant — clan info is included in the covenant prompt header
        session["step"] = "covenant"
        _set_session(ctx.author.id, session)

        cov_names = get_covenant_names()
        cov_emojis = []
        disc_str = ", ".join(clan_data['clan_disciplines'])
        lines = [
            f"\u2705 **Clan {match}** \u2014 *\"{clan_data['nickname']}\"* | \U0001fa78 {disc_str}\n\n"
            "Your **covenant** is your political and philosophical faction in vampire society. "
            "You can also go unaligned.\n"
        ]

        for name in cov_names:
            data = COVENANTS[name]
            emoji = data.get("emoji", "\u2b1b")
            cov_emojis.append(emoji)
            special = f"\n> \U0001f52e *{data['special']}*" if data.get("special") else ""
            lines.append(
                f"{emoji} **{name}**\n"
                f"> {data['description'][:150]}{special}\n"
            )

        cov_emojis.append("\U0001f6b6")  # 🚶 for Unaligned
        lines.append("\U0001f6b6 **Unaligned** \u2014 *No covenant allegiance*\n")
        lines.append("*React below or type `!wcc <covenant name>`*")

        embed = _make_embed(
            f"{STEP_EMOJIS['covenant']} Step 5 of 14: Choose Your Covenant",
            "\n".join(lines),
            step="covenant",
        )

        await self._send_with_reactions(
            ctx, embed, cov_names + ["Unaligned"],
            emojis=cov_emojis,
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
            await ctx.send(f"\u274c Unknown covenant. Choose from: {', '.join(cov_names)}")
            return

        char.covenant = match if match != "Unaligned" else ""

        session["step"] = "virtue"
        _set_session(ctx.author.id, session)

        # Virtue selection with descriptions
        virtue_emojis = []
        lines = [
            "Your **Virtue** represents your character's highest moral aspiration. "
            "When you act according to your Virtue in a meaningful way, you regain "
            "**all spent Willpower**.\n"
        ]

        for v in VIRTUES:
            vdata = VIRTUE_DATA.get(v, {})
            emoji = vdata.get("emoji", "\u2728")
            virtue_emojis.append(emoji)
            lines.append(f"{emoji} **{v}** \u2014 {vdata.get('description', '')}")

        lines.append("\n*React below or type `!wcc <virtue name>`*")

        embed = _make_embed(
            f"{STEP_EMOJIS['virtue']} Step 6 of 14: Choose Your Virtue",
            "\n".join(lines),
            step="virtue",
        )

        await self._send_with_reactions(
            ctx, embed, VIRTUES,
            emojis=virtue_emojis,
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
            await ctx.send(f"\u274c Choose from: {', '.join(VIRTUES)}")
            return

        char.virtue = choice
        session["step"] = "vice"
        _set_session(ctx.author.id, session)

        # Vice selection with descriptions
        vice_emojis = []
        lines = [
            "Your **Vice** represents your character's greatest moral failing. "
            "When you indulge your Vice, you regain **1 Willpower**. "
            "It's the easy temptation that always calls.\n"
        ]

        for v in VICES:
            vdata = VICE_DATA.get(v, {})
            emoji = vdata.get("emoji", "\U0001f608")
            vice_emojis.append(emoji)
            lines.append(f"{emoji} **{v}** \u2014 {vdata.get('description', '')}")

        lines.append("\n*React below or type `!wcc <vice name>`*")

        embed = _make_embed(
            f"{STEP_EMOJIS['vice']} Step 7 of 14: Choose Your Vice",
            "\n".join(lines),
            step="vice",
        )

        await self._send_with_reactions(
            ctx, embed, VICES,
            emojis=vice_emojis,
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
            await ctx.send(f"\u274c Choose from: {', '.join(VICES)}")
            return

        char.vice = choice
        session["step"] = "attr_priority"
        _set_session(ctx.author.id, session)

        embed = _make_embed(
            f"{STEP_EMOJIS['attributes']} Step 8 of 14: Attributes",
            (
                "Attributes represent your character's raw capabilities.\n"
                "All attributes start at **1 dot**. You'll prioritize three categories "
                "and distribute bonus dots:\n\n"
                "\U0001f947 **Primary** \u2014 5 bonus dots *(your strongest area)*\n"
                "\U0001f948 **Secondary** \u2014 4 bonus dots\n"
                "\U0001f949 **Tertiary** \u2014 3 bonus dots *(your weakest area)*\n\n"
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                "**Choose your PRIMARY (strongest) category:**\n\n"
                f"{CAT_EMOJIS['Mental']} **Mental** \u2014 Intelligence, Wits, Resolve\n"
                f"> *Thinking, reacting, staying focused*\n"
                f"{CAT_EMOJIS['Physical']} **Physical** \u2014 Strength, Dexterity, Stamina\n"
                f"> *Raw power, agility, endurance*\n"
                f"{CAT_EMOJIS['Social']} **Social** \u2014 Presence, Manipulation, Composure\n"
                f"> *Charisma, persuasion, keeping cool*\n\n"
                "*React below or type `!wcc Mental/Physical/Social`*"
            ),
            step="attr_priority",
        )

        cat_emojis = [CAT_EMOJIS["Mental"], CAT_EMOJIS["Physical"], CAT_EMOJIS["Social"]]
        await self._send_with_reactions(
            ctx, embed,
            ["Mental", "Physical", "Social"],
            emojis=cat_emojis,
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
            await ctx.send(f"\u274c Choose from: {', '.join(remaining)}")
            return

        priorities.append(choice)
        session["attr_priorities"] = priorities

        if len(priorities) == 1:
            _set_session(ctx.author.id, session)
            remaining = [v for v in valid if v not in priorities]
            cat_emojis = [CAT_EMOJIS[r] for r in remaining]

            embed = _make_embed(
                f"{STEP_EMOJIS['attributes']} Step 8: Attributes \u2014 Priority",
                (
                    f"\U0001f947 Primary: **{priorities[0]}** (5 dots)\n\n"
                    f"Now choose your **SECONDARY** category:\n\n"
                    + "\n".join(f"{CAT_EMOJIS[r]} **{r}**" for r in remaining)
                    + "\n\n*React or type `!wcc <category>`*"
                ),
                step="attr_priority",
            )
            await self._send_with_reactions(
                ctx, embed, remaining,
                emojis=cat_emojis,
                expected_step="attr_priority",
            )
        elif len(priorities) == 2:
            tertiary = [v for v in valid if v not in priorities][0]
            priorities.append(tertiary)
            session["attr_priorities"] = priorities
            session["step"] = "attr_assign_primary"
            session["attr_dots_remaining"] = 5
            session["attr_current_category"] = priorities[0]
            _set_session(ctx.author.id, session)

            attrs = self._get_attrs_for_category(priorities[0])
            embed = _make_embed(
                f"{STEP_EMOJIS['attributes']} Step 8: Attributes \u2014 {priorities[0]}",
                (
                    f"\U0001f947 **{priorities[0]}** (5 dots) > "
                    f"\U0001f948 **{priorities[1]}** (4 dots) > "
                    f"\U0001f949 **{priorities[2]}** (3 dots)\n\n"
                    f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                    f"{CAT_EMOJIS[priorities[0]]} Distribute **5 dots** among your **{priorities[0]}** attributes.\n"
                    f"All start at 1. You're adding bonus dots on top (max 4 bonus = 5 total).\n\n"
                    + "\n".join(f"\u2022 **{a}**: {_dot_display(1, 5)}" for a in attrs)
                    + f"\n\n\U0001f4ac **How to assign:** `!wcc <Attribute> <dots>`\n"
                    f"*Example:* `!wcc Intelligence 3` *(sets it to 1+3 = 4)*\n\n"
                    f"\U0001f4b0 Dots remaining: **5**"
                ),
                step="attr_assign_primary",
            )
            await self._wizard_send(ctx, session, embed)

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

        choice = choice.strip()
        if choice.lower() == "done":
            if remaining > 0:
                await ctx.send(f"\u26a0\ufe0f You still have **{remaining}** dots to assign!")
                return
            await self._advance_attr_category(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("\U0001f4ac Format: `!wcc <Attribute> <dots>` \u2014 e.g., `!wcc Strength 3`")
            return

        attr_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("\U0001f4ac Format: `!wcc <Attribute> <dots>` \u2014 dots must be a number.")
            return

        match = None
        for a in attrs:
            if a.lower() == attr_name.lower() or a.lower().startswith(attr_name.lower()):
                match = a
                break
        if not match:
            await ctx.send(f"\u274c Unknown attribute. Choose from: {', '.join(attrs)}")
            return

        already_assigned = char.attributes[match] - 1
        available = remaining + already_assigned
        if dots < 0 or dots > 4:
            await ctx.send("\u274c Bonus dots must be 0\u20134 (attributes range 1\u20135, start at 1).")
            return
        if dots > available:
            await ctx.send(f"\u274c Not enough dots. You have **{remaining}** remaining (this attribute has {already_assigned} assigned).")
            return

        session["attr_dots_remaining"] = remaining + already_assigned - dots
        char.attributes[match] = 1 + dots
        _set_session(ctx.author.id, session)

        # Show status embed
        lines = [f"\u2705 **{match}** set to **{char.attributes[match]}**\n"]
        lines.append(f"{CAT_EMOJIS[category]} **{category} Attributes:**")
        for a in attrs:
            lines.append(f"\u2022 {a}: {_dot_display(char.attributes[a], 5)} **({char.attributes[a]})**")
        lines.append(f"\n\U0001f4b0 Dots remaining: **{session['attr_dots_remaining']}**")

        if session["attr_dots_remaining"] == 0:
            lines.append("\n\u2705 All dots assigned! Type `!wcc done` to continue, or adjust any attribute.")

        embed = _make_embed(
            f"{STEP_EMOJIS['attributes']} Attributes \u2014 {category}",
            "\n".join(lines),
            step=session["step"],
        )
        await self._wizard_send(ctx, session, embed)

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
            embed = _make_embed(
                f"{STEP_EMOJIS['attributes']} Step 8: Attributes \u2014 {priorities[1]}",
                (
                    f"{CAT_EMOJIS[priorities[1]]} Distribute **4 dots** among your **{priorities[1]}** attributes:\n\n"
                    + "\n".join(f"\u2022 **{a}**: {_dot_display(1, 5)}" for a in attrs)
                    + f"\n\n\U0001f4ac `!wcc <Attribute> <dots>` \u2014 then `!wcc done` when finished.\n"
                    f"\U0001f4b0 Dots remaining: **4**"
                ),
                step="attr_assign_secondary",
            )
            await self._wizard_send(ctx, session, embed)
        elif step == "attr_assign_secondary":
            session["step"] = "attr_assign_tertiary"
            session["attr_dots_remaining"] = 3
            session["attr_current_category"] = priorities[2]
            _set_session(ctx.author.id, session)
            attrs = self._get_attrs_for_category(priorities[2])
            embed = _make_embed(
                f"{STEP_EMOJIS['attributes']} Step 8: Attributes \u2014 {priorities[2]}",
                (
                    f"{CAT_EMOJIS[priorities[2]]} Distribute **3 dots** among your **{priorities[2]}** attributes:\n\n"
                    + "\n".join(f"\u2022 **{a}**: {_dot_display(1, 5)}" for a in attrs)
                    + f"\n\n\U0001f4ac `!wcc <Attribute> <dots>` \u2014 then `!wcc done` when finished.\n"
                    f"\U0001f4b0 Dots remaining: **3**"
                ),
                step="attr_assign_tertiary",
            )
            await self._wizard_send(ctx, session, embed)
        elif step == "attr_assign_tertiary":
            # Attributes done — move to skills
            session["step"] = "skill_priority"
            _set_session(ctx.author.id, session)

            embed = _make_embed(
                f"{STEP_EMOJIS['skills']} Step 9 of 14: Skills",
                (
                    "\u2705 **Attributes complete!**\n\n"
                    "Skills represent trained abilities. Same priority system:\n\n"
                    "\U0001f947 **Primary** \u2014 11 dots *(your area of expertise)*\n"
                    "\U0001f948 **Secondary** \u2014 7 dots\n"
                    "\U0001f949 **Tertiary** \u2014 4 dots\n\n"
                    "Skills start at **0** and cap at **3** during creation.\n\n"
                    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                    "**Choose your PRIMARY skill category:**\n\n"
                    f"{CAT_EMOJIS['Mental']} **Mental** \u2014 Academics, Computer, Investigation...\n"
                    f"{CAT_EMOJIS['Physical']} **Physical** \u2014 Athletics, Brawl, Firearms...\n"
                    f"{CAT_EMOJIS['Social']} **Social** \u2014 Empathy, Expression, Persuasion...\n\n"
                    "*React below or type `!wcc Mental/Physical/Social`*"
                ),
                step="skill_priority",
            )
            cat_emojis = [CAT_EMOJIS["Mental"], CAT_EMOJIS["Physical"], CAT_EMOJIS["Social"]]
            await self._send_with_reactions(
                ctx, embed,
                ["Mental", "Physical", "Social"],
                emojis=cat_emojis,
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
            await ctx.send(f"\u274c Choose from: {', '.join(remaining)}")
            return

        priorities.append(choice)
        session["skill_priorities"] = priorities

        if len(priorities) == 1:
            _set_session(ctx.author.id, session)
            remaining = [v for v in valid if v not in priorities]
            cat_emojis = [CAT_EMOJIS[r] for r in remaining]

            embed = _make_embed(
                f"{STEP_EMOJIS['skills']} Step 9: Skills \u2014 Priority",
                (
                    f"\U0001f947 Primary: **{priorities[0]}** (11 dots)\n\n"
                    f"Choose your **SECONDARY** category:\n\n"
                    + "\n".join(f"{CAT_EMOJIS[r]} **{r}**" for r in remaining)
                    + "\n\n*React or type `!wcc <category>`*"
                ),
                step="skill_priority",
            )
            await self._send_with_reactions(
                ctx, embed, remaining,
                emojis=cat_emojis,
                expected_step="skill_priority",
            )
        elif len(priorities) == 2:
            tertiary = [v for v in valid if v not in priorities][0]
            priorities.append(tertiary)
            session["skill_priorities"] = priorities
            session["step"] = "skill_assign_primary"
            session["skill_dots_remaining"] = 11
            session["skill_current_category"] = priorities[0]
            _set_session(ctx.author.id, session)

            skills = self._get_skills_for_category(priorities[0])
            skill_list = "\n".join(f"\u2022 {s}" for s in skills)
            embed = _make_embed(
                f"{STEP_EMOJIS['skills']} Step 9: Skills \u2014 {priorities[0]}",
                (
                    f"\U0001f947 **{priorities[0]}** (11) > "
                    f"\U0001f948 **{priorities[1]}** (7) > "
                    f"\U0001f949 **{priorities[2]}** (4)\n\n"
                    f"{CAT_EMOJIS[priorities[0]]} Distribute **11 dots** among **{priorities[0]}** skills (max 3 each):\n\n"
                    f"{skill_list}\n\n"
                    f"\U0001f4ac `!wcc <Skill> <dots>` \u2014 then `!wcc done` when finished.\n"
                    f"*Example:* `!wcc Athletics 3`\n\n"
                    f"\U0001f4b0 Dots remaining: **11**"
                ),
                step="skill_assign_primary",
            )
            await self._wizard_send(ctx, session, embed)

    async def _step_skill_assign(self, ctx, session, char: WoDCharacter, choice: str):
        """Handle skill dot assignment for current category."""
        category = session["skill_current_category"]
        skills = self._get_skills_for_category(category)
        remaining = session["skill_dots_remaining"]

        choice = choice.strip()
        if choice.lower() == "done":
            if remaining > 0:
                await ctx.send(f"\u26a0\ufe0f You still have **{remaining}** dots to assign!")
                return
            await self._advance_skill_category(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("\U0001f4ac Format: `!wcc <Skill> <dots>` \u2014 e.g., `!wcc Athletics 3`")
            return

        skill_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("\U0001f4ac Format: `!wcc <Skill> <dots>` \u2014 dots must be a number.")
            return

        match = None
        for s in skills:
            if s.lower() == skill_name.lower() or s.lower().startswith(skill_name.lower()):
                match = s
                break
        if not match:
            for s in skills:
                if skill_name.lower() in s.lower():
                    match = s
                    break
        if not match:
            await ctx.send(f"\u274c Unknown skill. Choose from: {', '.join(skills)}")
            return

        already_assigned = char.skills.get(match, 0)
        available = remaining + already_assigned
        if dots < 0 or dots > 3:
            await ctx.send("\u274c Dots must be 0\u20133 during character creation.")
            return
        if dots > available:
            await ctx.send(f"\u274c Not enough dots. You have **{remaining}** remaining.")
            return

        session["skill_dots_remaining"] = remaining + already_assigned - dots
        char.skills[match] = dots
        _set_session(ctx.author.id, session)

        lines = [f"\u2705 **{match}** set to **{dots}**\n"]
        lines.append(f"{CAT_EMOJIS[category]} **{category} Skills:**")
        for s in skills:
            v = char.skills.get(s, 0)
            lines.append(f"\u2022 {s}: {_dot_display(v, 3)} **({v})**")
        lines.append(f"\n\U0001f4b0 Dots remaining: **{session['skill_dots_remaining']}**")

        if session["skill_dots_remaining"] == 0:
            lines.append("\n\u2705 All dots assigned! Type `!wcc done` to continue.")

        embed = _make_embed(
            f"{STEP_EMOJIS['skills']} Skills \u2014 {category}",
            "\n".join(lines),
            step=session["step"],
        )
        await self._wizard_send(ctx, session, embed)

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
            skill_list = "\n".join(f"\u2022 {s}" for s in skills)
            embed = _make_embed(
                f"{STEP_EMOJIS['skills']} Step 9: Skills \u2014 {priorities[idx]}",
                (
                    f"{CAT_EMOJIS[priorities[idx]]} Distribute **{dots} dots** among **{priorities[idx]}** skills (max 3 each):\n\n"
                    f"{skill_list}\n\n"
                    f"\U0001f4ac `!wcc <Skill> <dots>` \u2014 then `!wcc done` when finished.\n"
                    f"\U0001f4b0 Dots remaining: **{dots}**"
                ),
                step=next_s,
            )
            await self._wizard_send(ctx, session, embed)
        else:
            # Skills done — move to specialties
            session["step"] = "specialties"
            session["specialties_remaining"] = 3
            _set_session(ctx.author.id, session)

            embed = _make_embed(
                f"{STEP_EMOJIS['specialties']} Step 10 of 14: Specialties",
                (
                    "\u2705 **Skills complete!**\n\n"
                    "Specialties represent a narrow focus within a skill. "
                    "They give you a **+1 bonus** when that specialty applies.\n"
                    "You get **3 specialties** to assign.\n\n"
                    "\U0001f4ac **Format:** `!wcc <Skill>: <Specialty>`\n\n"
                    "\U0001f4a1 **Examples:**\n"
                    "\u2022 `!wcc Firearms: Pistols`\n"
                    "\u2022 `!wcc Academics: History`\n"
                    "\u2022 `!wcc Persuasion: Seduction`\n"
                    "\u2022 `!wcc Athletics: Climbing`\n\n"
                    "*You should pick skills your character already has dots in!*\n"
                    "*Type `!wcc skip` to skip remaining specialties.*\n\n"
                    f"\U0001f3af Specialties remaining: **3**"
                ),
                step="specialties",
            )
            await self._wizard_send(ctx, session, embed)

    async def _step_specialties(self, ctx, session, char: WoDCharacter, choice: str):
        remaining = session.get("specialties_remaining", 3)

        if choice.strip().lower() == "done":
            if remaining > 0:
                await ctx.send(f"\u26a0\ufe0f You still have **{remaining}** specialties to assign. Use `!wcc skip` to skip.")
                return
            await self._advance_to_disciplines(ctx, session, char)
            return

        if choice.strip().lower() == "skip":
            await self._advance_to_disciplines(ctx, session, char)
            return

        if ":" not in choice:
            await ctx.send("\U0001f4ac Format: `!wcc <Skill>: <Specialty>` \u2014 e.g., `!wcc Firearms: Pistols`")
            return

        parts = choice.split(":", 1)
        skill_name = parts[0].strip()
        specialty = parts[1].strip()

        if not specialty:
            await ctx.send("\u274c Please provide a specialty name after the colon.")
            return

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
            await ctx.send(f"\u274c Unknown skill: {skill_name}")
            return

        if match not in char.specialties:
            char.specialties[match] = []
        char.specialties[match].append(specialty)
        session["specialties_remaining"] = remaining - 1
        _set_session(ctx.author.id, session)

        rem = session["specialties_remaining"]
        embed = _make_embed(
            f"{STEP_EMOJIS['specialties']} Specialties",
            (
                f"\u2705 Added: **{match}: {specialty}**\n\n"
                "\U0001f4cb **Current specialties:**\n"
                + "\n".join(
                    f"\u2022 {sk}: {', '.join(sp)}"
                    for sk, sp in char.specialties.items()
                )
                + f"\n\n\U0001f3af Specialties remaining: **{rem}**"
                + ("\n\nType `!wcc done` to continue." if rem == 0 else "")
            ),
            step="specialties",
        )
        await self._wizard_send(ctx, session, embed)

        if rem == 0:
            await self._advance_to_disciplines(ctx, session, char)

    async def _advance_to_disciplines(self, ctx, session, char: WoDCharacter):
        """Move to discipline selection."""
        clan_discs = get_clan_disciplines(char.clan)
        session["step"] = "disciplines"
        session["discipline_dots_remaining"] = 3
        session["clan_disciplines"] = clan_discs
        _set_session(ctx.author.id, session)

        clan_data = get_clan_data(char.clan)
        clan_emoji = clan_data.get("emoji", "\U0001f9db") if clan_data else "\U0001f9db"

        disc_lines = []
        for d in clan_discs:
            data = get_discipline_data(d)
            if data:
                p1 = data["powers"].get(1, {})
                p2 = data["powers"].get(2, {})
                disc_lines.append(
                    f"\U0001fa78 **{d}** \u2014 *{data['description']}*\n"
                    f"> \u25cf **Lvl 1:** {p1.get('name', '?')} \u2014 {p1.get('description', '')}\n"
                    f"> \u25cb **Lvl 2:** {p2.get('name', '?')} \u2014 {p2.get('description', '')}"
                )

        embed = _make_embed(
            f"{STEP_EMOJIS['disciplines']} Step 11 of 14: Disciplines",
            (
                f"{clan_emoji} As a **{char.clan}**, your clan disciplines are:\n\n"
                + "\n\n".join(disc_lines) + "\n\n"
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
                "Distribute **3 dots** (max **2** per discipline at creation).\n\n"
                "\U0001f4ac `!wcc <Discipline> <dots>`\n"
                "*Example:* `!wcc Celerity 2`\n\n"
                "\U0001f4b0 Dots remaining: **3**"
            ),
            step="disciplines",
        )
        await self._wizard_send(ctx, session, embed)

    async def _step_disciplines(self, ctx, session, char: WoDCharacter, choice: str):
        remaining = session.get("discipline_dots_remaining", 3)
        clan_discs = session.get("clan_disciplines", [])

        if choice.strip().lower() == "done":
            if remaining > 0:
                await ctx.send(f"\u26a0\ufe0f You still have **{remaining}** dots to assign!")
                return
            await self._advance_to_merits(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("\U0001f4ac Format: `!wcc <Discipline> <dots>` \u2014 e.g., `!wcc Celerity 2`")
            return

        disc_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("\u274c Dots must be a number.")
            return

        match = None
        for d in clan_discs:
            if d.lower() == disc_name.lower() or d.lower().startswith(disc_name.lower()):
                match = d
                break
        if not match:
            await ctx.send(f"\u274c Choose from your clan disciplines: {', '.join(clan_discs)}")
            return

        already = char.disciplines.get(match, 0)
        available = remaining + already
        if dots < 0 or dots > 2:
            await ctx.send("\u274c Max 2 dots per discipline at character creation.")
            return
        if dots > available:
            await ctx.send(f"\u274c Not enough dots. You have **{remaining}** remaining.")
            return

        session["discipline_dots_remaining"] = remaining + already - dots
        if dots > 0:
            char.disciplines[match] = dots
        elif match in char.disciplines:
            del char.disciplines[match]
        _set_session(ctx.author.id, session)

        lines = [f"\u2705 **{match}** set to **{dots}**\n"]
        lines.append("\U0001fa78 **Clan Disciplines:**")
        for d in clan_discs:
            v = char.disciplines.get(d, 0)
            lines.append(f"\u2022 {d}: {_dot_display(v, 2)} **({v})**")
        lines.append(f"\n\U0001f4b0 Dots remaining: **{session['discipline_dots_remaining']}**")

        if session["discipline_dots_remaining"] == 0:
            lines.append("\n\u2705 Type `!wcc done` to continue.")

        embed = _make_embed(
            f"{STEP_EMOJIS['disciplines']} Disciplines",
            "\n".join(lines),
            step="disciplines",
        )
        await self._wizard_send(ctx, session, embed)

    async def _advance_to_merits(self, ctx, session, char: WoDCharacter):
        """Move to merit selection."""
        session["step"] = "merits"
        session["merit_dots_remaining"] = MERIT_DOTS_AT_CREATION
        _set_session(ctx.author.id, session)

        categories = ["Physical", "Mental", "Social", "Vampire"]
        embeds = []

        # Intro embed
        intro_embed = _make_embed(
            f"{STEP_EMOJIS['merits']} Step 12 of 14: Merits",
            (
                "Merits represent special advantages, backgrounds, and resources.\n"
                f"You have **{MERIT_DOTS_AT_CREATION} dots** to spend.\n\n"
                "\U0001f4ac `!wcc <Merit> <dots>` \u2014 e.g., `!wcc Resources 3`\n"
                "Type `!wcc done` when finished (unspent dots are lost).\n"
            ),
            step="merits",
        )
        await self._wizard_send(ctx, session, intro_embed)

        # Category embeds (sent as separate reference messages)
        for cat in categories:
            cat_merits = {k: v for k, v in MERITS.items() if v["category"] == cat}
            if not cat_merits:
                continue

            cat_emoji = MERIT_CAT_EMOJIS.get(cat, "\u2b50")
            lines = []
            for name, data in sorted(cat_merits.items()):
                dot_options = "/".join(str(d) for d in data["dots"])
                lines.append(f"\u2022 **{name}** `({dot_options})` \u2014 {data['description']}")

            embed = discord.Embed(
                title=f"{cat_emoji} {cat} Merits",
                description="\n".join(lines),
                color=discord.Color.dark_gold(),
            )
            embeds.append(embed)

        for embed in embeds:
            await ctx.send(embed=embed)

        await ctx.send(f"\U0001f4b0 Merit dots remaining: **{MERIT_DOTS_AT_CREATION}**")

    async def _step_merits(self, ctx, session, char: WoDCharacter, choice: str):
        remaining = session.get("merit_dots_remaining", 7)

        if choice.strip().lower() == "done" or choice.strip().lower() == "skip":
            await self._advance_to_backstory(ctx, session, char)
            return

        parts = choice.rsplit(None, 1)
        if len(parts) != 2:
            await ctx.send("\U0001f4ac Format: `!wcc <Merit> <dots>` \u2014 e.g., `!wcc Resources 3`")
            return

        merit_name = parts[0].strip()
        try:
            dots = int(parts[1])
        except ValueError:
            await ctx.send("\u274c Dots must be a number.")
            return

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
            await ctx.send(f"\u274c Unknown merit: {merit_name}. Type `!wcc done` to skip merits.")
            return

        merit_data = MERITS[match]
        if dots not in merit_data["dots"]:
            valid = ", ".join(str(d) for d in merit_data["dots"])
            await ctx.send(f"\u274c **{match}** can only be taken at: **{valid}** dots.")
            return

        already = char.merits.get(match, 0)
        cost = dots - already
        if cost > remaining:
            await ctx.send(f"\u274c Not enough dots. You have **{remaining}** remaining, need **{cost}**.")
            return

        char.merits[match] = dots
        session["merit_dots_remaining"] = remaining - cost
        _set_session(ctx.author.id, session)

        merit_list = "\n".join(f"\u2022 {k}: {_dot_display(v, 5)} **({v})**" for k, v in char.merits.items())
        embed = _make_embed(
            f"{STEP_EMOJIS['merits']} Merits",
            (
                f"\u2705 **{match}** set to **{dots}** dots.\n\n"
                "\u2b50 **Current Merits:**\n"
                f"{merit_list}\n\n"
                f"\U0001f4b0 Dots remaining: **{session['merit_dots_remaining']}**\n"
                "Type `!wcc done` when finished."
            ),
            step="merits",
        )
        await self._wizard_send(ctx, session, embed)

    async def _advance_to_backstory(self, ctx, session, char: WoDCharacter):
        session["step"] = "backstory"
        _set_session(ctx.author.id, session)

        embed = _make_embed(
            f"{STEP_EMOJIS['backstory']} Step 13 of 14: Backstory",
            (
                "Write a brief backstory for your character. This helps the Storyteller "
                "weave your history into the chronicle.\n\n"
                "\U0001f4dd **Consider including:**\n"
                "\u2022 \U0001f464 Who were they as a **mortal**?\n"
                "\u2022 \U0001f9db How were they **Embraced** (turned into a vampire)?\n"
                "\u2022 \U0001f5e1\ufe0f What **drives** them in their Requiem?\n\n"
                "Type: `!wcc <your backstory>`\n"
                "*Or `!wcc skip` to write it later*"
            ),
            step="backstory",
        )
        await self._wizard_send(ctx, session, embed)

    async def _step_backstory(self, ctx, session, char: WoDCharacter, choice: str):
        if choice.strip().lower() != "skip":
            char.backstory = choice.strip()[:1000]

        char.finalize()

        session["step"] = "confirm"
        _set_session(ctx.author.id, session)

        # Send sheet preview as separate embeds
        preview_embeds = self._build_sheet_embeds(char)
        for pe in preview_embeds:
            await ctx.send(embed=pe)

        # Clear wizard msg so confirm gets a fresh one after the preview
        session["wizard_msg"] = None
        _set_session(ctx.author.id, session)

        embed = _make_embed(
            f"{STEP_EMOJIS['confirm']} Step 14 of 14: Confirm Your Character",
            (
                "\U0001f4cb **Review your character sheet above.**\n\n"
                "\u2705 Type `!wcc yes` to **confirm and save**\n"
                "\u274c Type `!wcc no` to **start over**\n\n"
                "*Once confirmed, your character joins the coterie!*"
            ),
            color=discord.Color.green(),
            step="confirm",
        )
        await self._wizard_send(ctx, session, embed)

    async def _step_confirm(self, ctx, session, char: WoDCharacter, choice: str):
        choice = choice.strip().lower()
        if choice in ("yes", "y", "confirm"):
            channel_id = session.get("channel_id", str(ctx.channel.id))
            campaign = load_campaign(channel_id)
            if not campaign:
                await ctx.send("\u274c Campaign not found. Something went wrong.")
                _clear_session(ctx.author.id)
                return

            campaign.add_character(str(ctx.author.id), char)
            save_campaign(campaign)
            _clear_session(ctx.author.id)

            embed = _make_embed(
                "\U0001f389 Character Created!",
                (
                    f"**{char.name}** has been saved to the campaign!\n\n"
                    "\U0001f4cb Use `!wodsheet` in the server channel to view your sheet.\n"
                    "\U0001fa78 Use `!vitae` to track blood points.\n"
                    "\U0001f4a0 Use `!willpower` to track willpower.\n"
                    "\U0001f3b2 Use `!wroll` to make dice rolls."
                ),
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)

            try:
                guild_channel = self.bot.get_channel(int(channel_id))
                if guild_channel:
                    clan_data = get_clan_data(char.clan)
                    clan_emoji = clan_data.get("emoji", "\U0001f9db") if clan_data else "\U0001f9db"
                    cov_str = f", {char.covenant}" if char.covenant else ""
                    announce_embed = discord.Embed(
                        title=f"{clan_emoji} New Kindred Rises",
                        description=(
                            f"**{char.name}** (Clan {char.clan}{cov_str}) has joined the coterie!\n"
                            f"Created by {ctx.author.mention}."
                        ),
                        color=discord.Color.dark_red(),
                    )
                    await guild_channel.send(embed=announce_embed)
            except Exception:
                pass

        elif choice in ("no", "n", "restart"):
            _clear_session(ctx.author.id)
            await ctx.send("\u274c Character creation cancelled. Use `!createwod` in a server channel to start over.")
        else:
            await ctx.send("Reply `!wcc yes` to confirm or `!wcc no` to start over.")

    # ------------------------------------------------------------------
    # Interactive sheet editor (!wodedit)
    # ------------------------------------------------------------------

    # Page definitions: (page_title, category_emoji, item_list_fn, getter, setter, min_val, max_val)
    # item_list_fn returns the list of item names for the page
    # getter(char, name) returns current dots
    # setter(char, name, val) sets the dots

    _EDIT_PAGES = None  # built lazily per character

    def _build_edit_pages(self, char):
        """Build the list of editor pages for a character."""
        pages = [
            {
                "title": "🧠 Mental Attributes",
                "items": WOD_MENTAL_ATTRIBUTES,
                "kind": "attributes",
                "min": 1, "max": 5,
            },
            {
                "title": "💪 Physical Attributes",
                "items": WOD_PHYSICAL_ATTRIBUTES,
                "kind": "attributes",
                "min": 1, "max": 5,
            },
            {
                "title": "🗣️ Social Attributes",
                "items": WOD_SOCIAL_ATTRIBUTES,
                "kind": "attributes",
                "min": 1, "max": 5,
            },
            {
                "title": "🧠 Mental Skills",
                "items": WOD_MENTAL_SKILLS,
                "kind": "skills",
                "min": 0, "max": 5,
            },
            {
                "title": "💪 Physical Skills",
                "items": WOD_PHYSICAL_SKILLS,
                "kind": "skills",
                "min": 0, "max": 5,
            },
            {
                "title": "🗣️ Social Skills",
                "items": WOD_SOCIAL_SKILLS,
                "kind": "skills",
                "min": 0, "max": 5,
            },
            {
                "title": "🩸 Disciplines",
                "items": list(char.disciplines.keys()) if char.disciplines else get_clan_disciplines(char.clan),
                "kind": "disciplines",
                "min": 0, "max": 5,
            },
            {
                "title": "⭐ Merits",
                "items": list(char.merits.keys()) if char.merits else [],
                "kind": "merits",
                "min": 0, "max": 5,
            },
        ]
        return pages

    def _edit_get_val(self, char, kind: str, name: str) -> int:
        if kind == "attributes":
            return char.attributes.get(name, 1)
        elif kind == "skills":
            return char.skills.get(name, 0)
        elif kind == "disciplines":
            return char.disciplines.get(name, 0)
        elif kind == "merits":
            return char.merits.get(name, 0)
        return 0

    def _edit_set_val(self, char, kind: str, name: str, val: int):
        if kind == "attributes":
            char.attributes[name] = val
        elif kind == "skills":
            char.skills[name] = val
        elif kind == "disciplines":
            if val <= 0:
                char.disciplines.pop(name, None)
            else:
                char.disciplines[name] = val
        elif kind == "merits":
            if val <= 0:
                char.merits.pop(name, None)
            else:
                char.merits[name] = val

    def _build_edit_embed(self, char, pages, page_idx: int, cursor: int) -> discord.Embed:
        """Build the embed for the current editor page."""
        page = pages[page_idx]
        items = page["items"]
        kind = page["kind"]

        embed = discord.Embed(
            title=f"✏️ Editing: {char.name}",
            description=f"**{page['title']}**\nPage {page_idx + 1}/{len(pages)}",
            color=discord.Color.gold(),
        )

        if not items:
            embed.add_field(
                name="No items",
                value=f"No {kind} to edit. Use `!wcc` commands to add them first.",
                inline=False,
            )
        else:
            lines = []
            for i, name in enumerate(items):
                val = self._edit_get_val(char, kind, name)
                dot_str = _dot_display(val, page["max"])
                pointer = "▸ " if i == cursor else "  "
                num = NUMBER_EMOJIS[i] if i < len(NUMBER_EMOJIS) else f"{i+1}."
                lines.append(f"{pointer}{num} **{name}:** {dot_str} ({val}/{page['max']})")
            embed.add_field(name="\u200b", value="\n".join(lines), inline=False)

        # Controls legend
        embed.set_footer(
            text="◀️▶️ Change page │ 1️⃣-🔟 Select item │ ➕➖ Add/Remove dot │ ✅ Save & Exit"
        )
        return embed

    @commands.command(name="wodedit", aliases=["wedit", "editwod"])
    async def wod_edit(self, ctx: commands.Context):
        """Interactively edit your WoD character sheet with emoji reactions.

        Navigate pages with ◀️▶️, select items with number emojis,
        and use ➕➖ to adjust dots. Press ✅ to save and exit.

        Usage: !wodedit
        """
        campaign = self._get_campaign(ctx)
        if not self._is_wod_campaign(campaign):
            return
        char = campaign.get_character(str(ctx.author.id))
        if not char:
            return await ctx.send("You don't have a character. Use `!createwod` to create one.")
        if not char.creation_complete:
            return await ctx.send("Finish character creation first with `!wcc`.")

        pages = self._build_edit_pages(char)
        page_idx = 0
        cursor = 0

        # Send initial embed
        embed = self._build_edit_embed(char, pages, page_idx, cursor)
        msg = await ctx.send(embed=embed)

        # Add all control reactions
        all_emojis = NUMBER_EMOJIS[:len(pages[page_idx]["items"])] + EDIT_NAV_EMOJIS
        for emoji in all_emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                pass

        # ── Reaction loop ──
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
                # Auto-save on timeout
                if changed:
                    char.calc_derived()
                    save_campaign(campaign)
                embed = self._build_edit_embed(char, pages, page_idx, cursor)
                embed.set_footer(text="⏰ Editor timed out. Changes saved." if changed else "⏰ Editor timed out.")
                try:
                    await msg.edit(embed=embed)
                except discord.HTTPException:
                    pass
                return

            emoji_str = str(reaction.emoji)

            # Remove the user's reaction so they can tap again
            try:
                await msg.remove_reaction(reaction.emoji, user)
            except discord.HTTPException:
                pass

            page = pages[page_idx]
            items = page["items"]

            if emoji_str == EDIT_SAVE:
                # Save and exit
                if changed:
                    char.calc_derived()
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

            elif emoji_str in (NAV_PREV, NAV_NEXT):
                page_idx = (page_idx + (-1 if emoji_str == NAV_PREV else 1)) % len(pages)
                cursor = 0
                # Clear old reactions and re-add for the new page
                try:
                    await msg.clear_reactions()
                except discord.HTTPException:
                    pass
                new_emojis = NUMBER_EMOJIS[:len(pages[page_idx]["items"])] + EDIT_NAV_EMOJIS
                for e in new_emojis:
                    try:
                        await msg.add_reaction(e)
                    except discord.HTTPException:
                        pass

            elif emoji_str == EDIT_PLUS and items:
                name = items[cursor]
                val = self._edit_get_val(char, page["kind"], name)
                if val < page["max"]:
                    self._edit_set_val(char, page["kind"], name, val + 1)
                    changed = True

            elif emoji_str == EDIT_MINUS and items:
                name = items[cursor]
                val = self._edit_get_val(char, page["kind"], name)
                if val > page["min"]:
                    self._edit_set_val(char, page["kind"], name, val - 1)
                    changed = True

            elif emoji_str in NUMBER_EMOJIS:
                idx = NUMBER_EMOJIS.index(emoji_str)
                if idx < len(items):
                    cursor = idx

            # Update the embed
            embed = self._build_edit_embed(char, pages, page_idx, cursor)
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass

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

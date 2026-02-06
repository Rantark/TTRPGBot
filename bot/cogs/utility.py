"""Utility commands: recap, status, clues, npcs, whisper, help."""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.storage import load_campaign, save_campaign


class UtilityCog(commands.Cog, name="Utility"):
    """Utility and information commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx):
        return load_campaign(str(ctx.channel.id))

    @commands.command(name="recap")
    async def recap(self, ctx: commands.Context):
        """Get a DM-narrated recap of recent events.

        Usage: !recap
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.ACTIVE:
            await ctx.send("No active campaign to recap.")
            return

        async with ctx.typing():
            recap_text = await self.bot.dm_engine.get_recap(campaign)

        await ctx.send(f"**Recap of Recent Events:**\n{recap_text}")

    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        """Show campaign and party status at a glance.

        Usage: !status
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        lines = [f"**{campaign.name or 'Unnamed Campaign'}** — Phase: {campaign.phase.value.title()}"]

        if campaign.combat.active:
            lines.append(f"**COMBAT** — Round {campaign.combat.round_number}")
            if campaign.combat.current_turn:
                lines.append(f"Current turn: **{campaign.combat.current_turn['name']}**")

        if campaign.characters:
            lines.append("\n**Party Status:**")
            for char in campaign.characters.values():
                if not char.creation_complete:
                    lines.append(f"  {char.owner_name} — *Creating character...*")
                    continue
                hp_pct = (char.current_hp / char.max_hp * 100) if char.max_hp else 0
                if hp_pct >= 75:
                    condition = "Healthy"
                elif hp_pct >= 50:
                    condition = "Wounded"
                elif hp_pct >= 25:
                    condition = "Bloodied"
                elif hp_pct > 0:
                    condition = "Critical"
                else:
                    condition = "DOWN"
                insp = " | Inspiration" if char.inspiration else ""
                lines.append(f"  **{char.name}** — HP {char.current_hp}/{char.max_hp} ({condition}) | AC {char.ac}{insp}")

        await ctx.send("\n".join(lines))

    @commands.command(name="clues")
    async def clues(self, ctx: commands.Context, *, action: str = ""):
        """View or manage investigation clues.

        Usage: !clues (list all clues)
        Usage: !clues add Found a bloody dagger behind the tavern
        Usage: !clues remove 1
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        if not action:
            if not campaign.clues:
                await ctx.send("No clues recorded yet. Add one with `!clues add <clue>`")
                return
            lines = ["**Investigation Clues:**"]
            for i, clue in enumerate(campaign.clues, 1):
                lines.append(f"  `{i}.` {clue}")
            await ctx.send("\n".join(lines))
            return

        parts = action.split(None, 1)
        sub = parts[0].lower()

        if sub == "add" and len(parts) > 1:
            campaign.clues.append(parts[1])
            save_campaign(campaign)
            await ctx.send(f"Clue added: *{parts[1]}*")

        elif sub == "remove" and len(parts) > 1:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(campaign.clues):
                    removed = campaign.clues.pop(idx)
                    save_campaign(campaign)
                    await ctx.send(f"Removed clue: *{removed}*")
                else:
                    await ctx.send(f"Invalid clue number. Use 1-{len(campaign.clues)}.")
            except ValueError:
                await ctx.send("Usage: `!clues remove <number>`")

        else:
            await ctx.send("Usage: `!clues`, `!clues add <text>`, or `!clues remove <number>`")

    @commands.command(name="npcs")
    async def npcs(self, ctx: commands.Context, *, action: str = ""):
        """View or manage known NPCs.

        Usage: !npcs (list all known NPCs)
        Usage: !npcs add Thorne | A grizzled half-orc blacksmith
        Usage: !npcs remove 1
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        if not action:
            if not campaign.known_npcs:
                await ctx.send("No known NPCs yet. Add one with `!npcs add <name> | <description>`")
                return
            lines = ["**Known NPCs:**"]
            for i, npc in enumerate(campaign.known_npcs, 1):
                lines.append(f"  `{i}.` **{npc['name']}** — {npc['description']}")
            await ctx.send("\n".join(lines))
            return

        parts = action.split(None, 1)
        sub = parts[0].lower()

        if sub == "add" and len(parts) > 1:
            npc_parts = parts[1].split("|", 1)
            name = npc_parts[0].strip()
            desc = npc_parts[1].strip() if len(npc_parts) > 1 else "No description"
            campaign.known_npcs.append({"name": name, "description": desc})
            save_campaign(campaign)
            await ctx.send(f"NPC added: **{name}** — {desc}")

        elif sub == "remove" and len(parts) > 1:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(campaign.known_npcs):
                    removed = campaign.known_npcs.pop(idx)
                    save_campaign(campaign)
                    await ctx.send(f"Removed NPC: **{removed['name']}**")
                else:
                    await ctx.send(f"Invalid NPC number. Use 1-{len(campaign.known_npcs)}.")
            except ValueError:
                await ctx.send("Usage: `!npcs remove <number>`")

        else:
            await ctx.send("Usage: `!npcs`, `!npcs add <name> | <desc>`, or `!npcs remove <number>`")

    @commands.command(name="whisper")
    async def whisper(self, ctx: commands.Context, *, message: str):
        """Send a private message to the DM (Claude). Other players won't see the response.

        Usage: !whisper I want to secretly pocket the gem
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.ACTIVE:
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_summary = char.short_summary() if char else ""

        # Try to DM the user
        try:
            async with ctx.typing():
                response = await self.bot.dm_engine.get_dm_response(
                    campaign,
                    f"[WHISPER — PRIVATE MESSAGE FROM PLAYER, respond privately] {message}",
                    ctx.author.display_name,
                    char_summary,
                    "This is a private whisper. Respond only to this player. "
                    "Other players should not know the contents.",
                )
            save_campaign(campaign)

            # Send response as DM (private message)
            await ctx.author.send(f"**DM whispers back:**\n{response}")
            await ctx.send(f"*{ctx.author.display_name} whispers something to the DM...*")

        except discord.Forbidden:
            await ctx.send("I can't send you a DM. Please enable DMs from server members in your privacy settings.")

    # Category definitions for !commands
    HELP_CATEGORIES = {
        "campaign": {
            "title": "Campaign Management",
            "description": "Create and manage your campaign.",
            "commands": (
                "`!newcampaign [name]` — Create a new campaign (you become DM)\n"
                "`!pitch <title> | <desc>` — Propose a campaign concept\n"
                "`!pitches` — View all pitches\n"
                "`!vote <#>` — Vote for a pitch\n"
                "`!selectpitch <#>` — DM selects a pitch\n"
                "`!startcampaign` — DM begins the adventure\n"
                "`!endcampaign` — DM ends the campaign\n"
                "`!campaigninfo` — View campaign status"
            ),
        },
        "character": {
            "title": "Character Creation & Sheets",
            "description": "Build and view your character.",
            "commands": (
                "`!createchar` — Start interactive character creation\n"
                "`!cc <choice>` — Make a creation choice (name, gender, race, etc.)\n"
                "`!deletechar` — Delete your character and start over\n"
                "`!sheet` — View your full character sheet\n"
                "`!sheet @player` — View another player's sheet"
            ),
        },
        "gameplay": {
            "title": "Gameplay",
            "description": "RP actions are **queued** until all players act or `!pass`, then the DM responds to everyone at once.",
            "commands": (
                "`!action <desc>` — Describe what you do *(queued)*\n"
                "`!ic <dialogue>` — Speak in character *(queued)*\n"
                "`!emote <action>` — Describe expressions/actions *(queued)*\n"
                "`!look` — Ask the DM to describe the scene *(queued)*\n"
                "`!inspect <target>` — Examine something closely *(queued)*\n"
                "`!talk <NPC>` — Speak to an NPC *(queued)*\n"
                "`!pass` — Do nothing this round\n"
                "`!pending` — See who hasn't acted yet\n"
                "`!resolve` — *(DM)* Force the round to resolve now\n"
                "`!ask <question>` — Ask the DM a rules question *(no story impact)*\n"
                "`!ooc <message>` — Out-of-character chat *(not queued)*"
            ),
        },
        "dice": {
            "title": "Dice & Rolls",
            "description": "Roll dice and make checks using your character's stats.",
            "commands": (
                "`!roll <notation>` — Roll dice (d20, 2d6+3, 4d6, etc.)\n"
                "`!check <skill/ability>` — Ability or skill check\n"
                "`!save <ability>` — Saving throw (STR, DEX, CON, INT, WIS, CHA)\n"
                "`!attack` — Attack roll (d20 + mod + proficiency)"
            ),
        },
        "combat": {
            "title": "Combat",
            "description": "Initiative tracking and turn order management.",
            "commands": (
                "`!combatstart` — *(DM)* Begin a combat encounter\n"
                "`!initiative` — Roll initiative (d20 + DEX mod)\n"
                "`!addnpc <name> <init>` — *(DM)* Add NPC to initiative\n"
                "`!removenpc <name>` — *(DM)* Remove NPC from initiative\n"
                "`!begincombat` — *(DM)* Sort initiative and start turns\n"
                "`!turnorder` — Display the current initiative order\n"
                "`!next` — *(DM)* Advance to the next turn\n"
                "`!pass` — Skip your combat turn\n"
                "`!combatend` — *(DM)* End combat"
            ),
        },
        "progression": {
            "title": "Progression & Resources",
            "description": "Rest, level up, and manage HP/XP.",
            "commands": (
                "`!rest short` — Short rest (spend hit dice to heal)\n"
                "`!rest long` — Long rest (full HP, restore hit dice)\n"
                "`!hp` — View your current HP\n"
                "`!hp +5` / `!hp -3` — Heal or take damage\n"
                "`!xp <amount>` — *(DM)* Award XP to all players\n"
                "`!xp <amount> @player` — *(DM)* Award XP to one player\n"
                "`!levelup` — Level up (if you have enough XP)\n"
                "`!inspiration @player` — *(DM)* Grant inspiration\n"
                "`!deathsave` — Roll a death saving throw"
            ),
        },
        "utility": {
            "title": "Utility",
            "description": "Recaps, tracking, and private messages.",
            "commands": (
                "`!recap` — AI-narrated recap of recent events\n"
                "`!status` — Campaign and party status at a glance\n"
                "`!clues` — View investigation clues\n"
                "`!clues add <text>` — Add a clue\n"
                "`!clues remove <#>` — Remove a clue\n"
                "`!npcs` — View known NPCs\n"
                "`!npcs add <name> | <desc>` — Add an NPC\n"
                "`!npcs remove <#>` — Remove an NPC\n"
                "`!whisper <msg>` — Private message to the DM\n"
                "`!commands` — This help menu"
            ),
        },
    }

    # Aliases so users can type partial names
    CATEGORY_ALIASES = {
        "camp": "campaign", "campaigns": "campaign",
        "char": "character", "characters": "character", "sheet": "character",
        "game": "gameplay", "play": "gameplay", "rp": "gameplay", "actions": "gameplay",
        "roll": "dice", "rolls": "dice", "rolling": "dice",
        "fight": "combat", "initiative": "combat", "battle": "combat",
        "prog": "progression", "level": "progression", "rest": "progression", "hp": "progression", "xp": "progression",
        "util": "utility", "utils": "utility", "misc": "utility",
    }

    @commands.command(name="commands")
    async def command_list(self, ctx: commands.Context, *, category: str = ""):
        """Show available commands. Use !commands <category> for details.

        Usage: !commands
        Usage: !commands combat
        Usage: !commands dice
        """
        category = category.strip().lower()

        if not category:
            # Show the overview menu
            lines = [
                "**D&D 5e Bot — Command Categories**",
                "Type `!commands <category>` for details.\n",
            ]
            for key, cat in self.HELP_CATEGORIES.items():
                lines.append(f"> **{cat['title']}** — `!commands {key}`")
            lines.append("\n*Example:* `!commands gameplay`, `!commands combat`, `!commands dice`")
            await ctx.send("\n".join(lines))
            return

        # Resolve alias
        resolved = self.CATEGORY_ALIASES.get(category, category)

        if resolved not in self.HELP_CATEGORIES:
            valid = ", ".join(f"`{k}`" for k in self.HELP_CATEGORIES)
            await ctx.send(f"Unknown category: `{category}`\nAvailable: {valid}")
            return

        cat = self.HELP_CATEGORIES[resolved]
        await ctx.send(
            f"**{cat['title']}**\n"
            f"*{cat['description']}*\n\n"
            f"{cat['commands']}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))

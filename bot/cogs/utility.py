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
                conds = f" | {', '.join(char.conditions)}" if char.conditions else ""
                lines.append(f"  **{char.name}** — HP {char.current_hp}/{char.max_hp} ({condition}) | AC {char.ac}{insp}{conds}")

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
                "`!setlevel <level>` — *(DM)* Set starting level for new characters\n"
                "`!loot @player <item>` — *(DM)* Give item/gold to a player\n"
                "`!giveall <item>` — *(DM)* Give item/gold to all players\n"
                "`!suggestcampaign` — Ask Claude to suggest campaign ideas\n"
                "`!startcampaign` — DM begins the adventure (creates game thread)\n"
                "`!endcampaign` — DM ends the campaign (archives thread)\n"
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
                "`!sheet @player` — View another player's sheet\n"
                "`!ac` — View your AC breakdown\n"
                "`!stats` — View your ability scores and modifiers\n"
                "`!skills` — View all skill modifiers\n"
                "`!saves` — View saving throw modifiers\n"
                "`!weapons` — View your weapons and attack bonuses\n"
                "`!equipment` — View your inventory/gear\n"
                "`!equipment add/remove <item>` — Manage inventory\n"
                "`!gold` — View your gold | `!gold +/-<amt>` — Adjust\n"
                "`!equip` — View equipped armor | `!equip armor/shield <name>`\n"
                "`!give @player <item>` — Give item/gold to a player\n"
                "`!use <item>` — Use a consumable (auto-effects for potions)\n"
                "`!backstory` — View your backstory\n"
                "`!backstory <text>` — Set/update your backstory"
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
                "`!undo` — Cancel your pending action before the round resolves\n"
                "`!pending` — See who hasn't acted yet\n"
                "`!resolve` — *(DM)* Force the round to resolve now\n"
                "`!rewind` — *(DM)* Undo last DM response\n"
                "`!rewind <prompt>` — *(DM)* Undo and replace with new scene\n"
                "`!dm <prompt>` — *(DM)* Narrate a scene or event\n"
                "`!dm-whisper @player <msg>` — *(DM)* Private message to a player\n"
                "`!ask <question>` — Ask the DM a rules question *(no story impact)*\n"
                "`!ooc <message>` — Out-of-character chat *(not queued)*"
            ),
        },
        "dice": {
            "title": "Dice & Rolls",
            "description": "Roll dice and make checks using your character's stats.",
            "commands": (
                "`!roll <notation> [adv|dis]` — Roll dice (d20, 2d6+3, etc.)\n"
                "`!check <skill/ability> [adv|dis]` — Ability or skill check\n"
                "`!save <ability> [adv|dis]` — Saving throw (STR, DEX, CON, INT, WIS, CHA)\n"
                "`!attack [adv|dis]` — Attack roll (d20 + mod + proficiency)"
            ),
        },
        "combat": {
            "title": "Combat",
            "description": "Initiative tracking, turn order, and tactical map.",
            "commands": (
                "`!combatstart` — *(DM)* Begin a combat encounter\n"
                "`!initiative [adv|dis]` — Roll initiative (d20 + DEX mod)\n"
                "`!addnpc <name> <init>` — *(DM)* Add NPC to initiative\n"
                "`!removenpc <name>` — *(DM)* Remove NPC from initiative\n"
                "`!begincombat` — *(DM)* Sort initiative and start turns\n"
                "`!turnorder` — Display the current initiative order\n"
                "`!next` — *(DM)* Advance to the next turn\n"
                "`!pass` — Skip your combat turn\n"
                "`!map` — Display the combat map\n"
                "`!place <name> <x> <y>` — *(DM)* Place a token on the map\n"
                "`!move <dir> <dist>` — Move on the map (n/s/e/w/ne/nw/se/sw)\n"
                "`!move <x> <y>` — Move to absolute coordinates\n"
                "`!mapsize <w> <h>` — *(DM)* Resize the map (5-20)\n"
                "`!combatend` — *(DM)* End combat"
            ),
        },
        "progression": {
            "title": "Progression & Resources",
            "description": "Rest, level up, and manage HP/XP.",
            "commands": (
                "`!rest short` — Short rest (spend hit dice to heal)\n"
                "`!rest long` — Long rest (full HP, restore hit dice)\n"
                "`!hitdie [count]` — Spend hit dice to heal (alias: `!hd`)\n"
                "`!hp` — View your current HP\n"
                "`!hp +5` / `!hp -3` — Heal or take damage\n"
                "`!xp <amount>` — *(DM)* Award XP to all players\n"
                "`!xp <amount> @player` — *(DM)* Award XP to one player\n"
                "`!levelup` — Level up (if you have enough XP)\n"
                "`!inspiration @player` — *(DM)* Grant inspiration\n"
                "`!deathsave` — Roll a death saving throw\n"
                "`!stabilize @player` — Stabilize an unconscious character\n"
                "`!feat` — List your feats\n"
                "`!feat add <name>` — Add a feat\n"
                "`!feat remove <name>` — Remove a feat\n"
                "`!modifier` — List active modifiers (buffs, items, etc.)\n"
                "`!modifier add <source> <stat> <+/-val>` — Add a modifier\n"
                "`!modifier remove <source>` — Remove a modifier"
            ),
        },
        "spells": {
            "title": "Spells & Spellcasting",
            "description": "Track spell slots, learn spells, prepare, and cast.",
            "commands": (
                "`!spells` — View your known spells, prepared spells, and cantrips\n"
                "`!slots` — View your current spell slots\n"
                "`!learn <spell>` — Add a spell to your known spells\n"
                "`!learncantrip <name>` — Learn a cantrip\n"
                "`!forget <spell>` — Remove a spell from your known list\n"
                "`!forget cantrip <name>` — Remove a cantrip\n"
                "`!prepare <spell>` — Prepare/unprepare a known spell\n"
                "`!cast <spell>` — Cast a spell (uses lowest slot)\n"
                "`!cast <spell> <level>` — Cast at a specific slot level"
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
        "camp": "campaign", "campaigns": "campaign", "suggest": "campaign", "suggestcampaign": "campaign",
        "char": "character", "characters": "character", "sheet": "character", "equip": "character", "equipment": "character", "inventory": "character", "backstory": "character", "stats": "character", "skills": "character", "saves": "character", "weapons": "character", "ac": "character", "gold": "character", "give": "character", "use": "character", "loot": "campaign",
        "game": "gameplay", "play": "gameplay", "rp": "gameplay", "actions": "gameplay", "dm": "gameplay",
        "roll": "dice", "rolls": "dice", "rolling": "dice",
        "fight": "combat", "initiative": "combat", "battle": "combat", "map": "combat",
        "spell": "spells", "magic": "spells", "casting": "spells", "slots": "spells", "cantrips": "spells",
        "prog": "progression", "level": "progression", "rest": "progression", "hp": "progression", "xp": "progression", "feat": "progression", "feats": "progression", "modifier": "progression", "mod": "progression", "buff": "progression", "modifiers": "progression", "hitdie": "progression", "hd": "progression", "stabilize": "progression", "deathsave": "progression",
        "util": "utility", "utils": "utility", "misc": "utility",
    }

    @commands.command(name="commands")
    async def command_list(self, ctx: commands.Context, *, category: str = ""):
        """Show available commands (sent via DM to keep game chat clean).

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
            help_text = "\n".join(lines)
        else:
            # Resolve alias
            resolved = self.CATEGORY_ALIASES.get(category, category)

            if resolved not in self.HELP_CATEGORIES:
                valid = ", ".join(f"`{k}`" for k in self.HELP_CATEGORIES)
                await ctx.send(f"Unknown category: `{category}`\nAvailable: {valid}")
                return

            cat = self.HELP_CATEGORIES[resolved]
            help_text = (
                f"**{cat['title']}**\n"
                f"*{cat['description']}*\n\n"
                f"{cat['commands']}"
            )

        # Send via DM to keep game chat clean
        if isinstance(ctx.channel, discord.DMChannel):
            # Already in DMs, just send here
            await ctx.send(help_text)
        else:
            try:
                await ctx.author.send(help_text)
                await ctx.send(f"{ctx.author.mention} Command help sent to your DMs!")
            except discord.Forbidden:
                # DMs disabled — fall back to channel
                await ctx.send(help_text)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))

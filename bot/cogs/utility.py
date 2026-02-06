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

    @commands.command(name="commands")
    async def command_list(self, ctx: commands.Context):
        """Show all available commands grouped by category."""
        help_text = """**D&D 5e Discord Bot — Command Reference**

**Campaign Management**
`!newcampaign [name]` — Create a new campaign (you become DM)
`!pitch <title> | <desc>` — Propose a campaign concept
`!pitches` — View all pitches
`!vote <#>` — Vote for a pitch
`!selectpitch <#>` — DM selects a pitch
`!startcampaign` — DM begins the adventure
`!endcampaign` — DM ends the campaign
`!campaigninfo` — View campaign status

**Character**
`!createchar` — Start character creation
`!cc <choice>` — Make creation choices
`!deletechar` — Delete your character
`!sheet` — View your character sheet

**Gameplay** (actions are queued until all players act or pass)
`!action <desc>` — Do something (queued)
`!ic <dialogue>` — Speak in character (queued)
`!emote <action>` — Describe actions (queued)
`!look` — Describe the scene (queued)
`!inspect <target>` — Examine something (queued)
`!talk <NPC>` — Talk to an NPC (queued)
`!pass` — Do nothing this round
`!pending` — See who hasn't acted yet
`!resolve` — DM forces round to resolve now
`!ask <question>` — Ask DM a rules question (no story impact)
`!ooc <message>` — Out-of-character chat (not queued)

**Dice**
`!roll <notation>` — Roll dice (d20, 2d6+3, etc.)
`!check <skill/ability>` — Ability/skill check
`!save <ability>` — Saving throw
`!attack` — Attack roll

**Combat**
`!combatstart` — DM starts combat
`!initiative` — Roll initiative
`!addnpc <name> <init>` — DM adds NPC
`!begincombat` — DM starts turn order
`!turnorder` — Show initiative
`!next` — DM advances turn
`!combatend` — DM ends combat

**Progression**
`!rest short/long` — Take a rest
`!hp [+/-amount]` — View/adjust HP
`!xp <amount>` — DM awards XP
`!levelup` — Level up
`!inspiration @player` — DM grants inspiration
`!deathsave` — Roll death save

**Utility**
`!recap` — AI recap of events
`!status` — Party status
`!clues [add/remove]` — Track clues
`!npcs [add/remove]` — Track NPCs
`!whisper <msg>` — Private DM message
`!commands` — This help message"""

        # Split for Discord limit
        parts = help_text.split("\n\n")
        msg = ""
        for part in parts:
            if len(msg) + len(part) + 2 > 1990:
                await ctx.send(msg)
                msg = ""
            msg += part + "\n\n"
        if msg:
            await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))

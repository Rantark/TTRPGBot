"""Campaign management cog: pitch, vote, setup, start, end."""

import discord
from discord.ext import commands

from bot.models.campaign import Campaign, CampaignPhase
from bot.storage import save_campaign, load_campaign, delete_campaign


class CampaignCog(commands.Cog, name="Campaign"):
    """Commands for managing campaigns."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx: commands.Context) -> Campaign | None:
        return load_campaign(str(ctx.channel.id))

    def _get_or_create_campaign(self, ctx: commands.Context) -> Campaign:
        campaign = load_campaign(str(ctx.channel.id))
        if campaign is None:
            campaign = Campaign(str(ctx.channel.id), str(ctx.guild.id))
        return campaign

    @commands.command(name="newcampaign")
    async def new_campaign(self, ctx: commands.Context, *, name: str = ""):
        """Start a new campaign in this channel. You become the DM.

        Usage: !newcampaign My Epic Adventure
        """
        existing = self._get_campaign(ctx)
        if existing and existing.phase != CampaignPhase.NONE:
            await ctx.send("There's already an active campaign in this channel. "
                           "Use `!endcampaign` to end it first.")
            return

        campaign = Campaign(str(ctx.channel.id), str(ctx.guild.id))
        campaign.dm_id = str(ctx.author.id)
        campaign.phase = CampaignPhase.PITCHING

        if name:
            campaign.name = name
            campaign.phase = CampaignPhase.SETUP
            save_campaign(campaign)
            await ctx.send(
                f"**Campaign Created: {name}**\n"
                f"DM: {ctx.author.display_name}\n"
                f"Phase: **Setup** — Players can now create characters with `!createchar`\n"
                f"DM: Use `!setlevel <level>` to set the starting level (default: 1)\n"
                f"When everyone is ready, the DM uses `!startcampaign` to begin!"
            )
        else:
            save_campaign(campaign)
            await ctx.send(
                "**New Campaign Started!**\n"
                f"DM: {ctx.author.display_name}\n"
                "Phase: **Pitching** — Use `!pitch <title> | <description>` to propose campaign concepts.\n"
                "Players vote with `!vote <number>`. DM picks with `!selectpitch <number>`."
            )

    @commands.command(name="pitch")
    async def pitch(self, ctx: commands.Context, *, text: str):
        """Propose a campaign concept.

        Usage: !pitch Dragon's Bane | A quest to slay an ancient red dragon threatening the realm
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.PITCHING:
            await ctx.send("No campaign in pitching phase. Use `!newcampaign` first.")
            return

        parts = text.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""

        campaign.pitches.append({
            "author_id": str(ctx.author.id),
            "author_name": ctx.author.display_name,
            "title": title,
            "description": description,
            "votes": [],
        })
        save_campaign(campaign)

        idx = len(campaign.pitches)
        await ctx.send(
            f"**Pitch #{idx}: {title}**\n"
            f"*by {ctx.author.display_name}*\n"
            f"{description}\n"
            f"Vote for this with `!vote {idx}`"
        )

    @commands.command(name="pitches")
    async def list_pitches(self, ctx: commands.Context):
        """View all campaign pitches."""
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.pitches:
            await ctx.send("No pitches yet. Use `!pitch <title> | <description>` to propose one.")
            return

        lines = ["**Campaign Pitches:**"]
        for i, p in enumerate(campaign.pitches, 1):
            vote_count = len(p["votes"])
            lines.append(f"**#{i}** — {p['title']} (by {p['author_name']}) — {vote_count} vote(s)")
            if p["description"]:
                lines.append(f"  *{p['description']}*")
        lines.append("\nVote with `!vote <number>` — DM selects with `!selectpitch <number>`")
        await ctx.send("\n".join(lines))

    @commands.command(name="vote")
    async def vote(self, ctx: commands.Context, number: int):
        """Vote for a campaign pitch.

        Usage: !vote 2
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.PITCHING:
            await ctx.send("No campaign in pitching phase.")
            return

        if number < 1 or number > len(campaign.pitches):
            await ctx.send(f"Invalid pitch number. Choose 1-{len(campaign.pitches)}.")
            return

        pitch = campaign.pitches[number - 1]
        voter_id = str(ctx.author.id)

        # Remove previous votes
        for p in campaign.pitches:
            if voter_id in p["votes"]:
                p["votes"].remove(voter_id)

        pitch["votes"].append(voter_id)
        save_campaign(campaign)
        await ctx.send(f"{ctx.author.display_name} voted for **{pitch['title']}**!")

    @commands.command(name="selectpitch")
    async def select_pitch(self, ctx: commands.Context, number: int):
        """DM selects a campaign pitch to move to setup phase.

        Usage: !selectpitch 1
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.PITCHING:
            await ctx.send("No campaign in pitching phase.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can select a pitch.")
            return
        if number < 1 or number > len(campaign.pitches):
            await ctx.send(f"Invalid pitch number. Choose 1-{len(campaign.pitches)}.")
            return

        pitch = campaign.pitches[number - 1]
        campaign.name = pitch["title"]
        campaign.description = pitch["description"]
        campaign.phase = CampaignPhase.SETUP
        save_campaign(campaign)

        await ctx.send(
            f"**Campaign Selected: {pitch['title']}!**\n"
            f"*{pitch['description']}*\n\n"
            "Phase: **Setup** — Players, create your characters with `!createchar`!\n"
            "When everyone is ready, the DM uses `!startcampaign` to begin the adventure."
        )

    @commands.command(name="loot")
    async def loot(self, ctx: commands.Context, target: discord.Member, *, item_description: str):
        """DM adds items or gold to a player's inventory.

        Usage: !loot @Player Potion of Healing
        Usage: !loot @Player 50 gold
        Usage: !loot @Player 2 Arrows
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can give loot.")
            return

        char = campaign.get_character(str(target.id))
        if not char:
            await ctx.send(f"{target.display_name} doesn't have a character.")
            return

        # Parse "50 gold" or "2 Arrows" or "Potion of Healing"
        parts = item_description.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            quantity = int(parts[0])
            item_name = parts[1]
        else:
            quantity = 1
            item_name = item_description.strip()

        if item_name.lower() in ("gold", "gp", "gold pieces"):
            char.gold += quantity
            save_campaign(campaign)
            await ctx.send(f"**{char.name}** received **{quantity} gp**. Total: {char.gold} gp")
        else:
            char.add_item(item_name, quantity)
            save_campaign(campaign)
            qty_str = f"{quantity}x " if quantity > 1 else ""
            await ctx.send(f"**{char.name}** received {qty_str}**{item_name}**.")

    @commands.command(name="giveall")
    async def give_all(self, ctx: commands.Context, *, item_description: str):
        """DM gives items or gold to all players.

        Usage: !giveall 100 gold
        Usage: !giveall Potion of Healing
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can give loot.")
            return

        complete_chars = [c for c in campaign.characters.values() if c.creation_complete]
        if not complete_chars:
            await ctx.send("No characters to give items to.")
            return

        # Parse
        parts = item_description.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            quantity = int(parts[0])
            item_name = parts[1]
        else:
            quantity = 1
            item_name = item_description.strip()

        is_gold = item_name.lower() in ("gold", "gp", "gold pieces")
        for char in complete_chars:
            if is_gold:
                char.gold += quantity
            else:
                char.add_item(item_name, quantity)

        save_campaign(campaign)

        qty_str = f"{quantity}x " if quantity > 1 else ""
        names = ", ".join(c.name for c in complete_chars)
        if is_gold:
            await ctx.send(f"**{quantity} gp** given to all players: {names}")
        else:
            await ctx.send(f"{qty_str}**{item_name}** given to all players: {names}")

    @commands.command(name="setlevel")
    async def set_level(self, ctx: commands.Context, level: int = 0):
        """DM sets the starting level for new characters.

        Usage: !setlevel 3
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel. Use `!newcampaign` first.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can set the starting level.")
            return
        if level < 1 or level > 20:
            await ctx.send("Starting level must be between 1 and 20.")
            return

        campaign.starting_level = level
        save_campaign(campaign)
        await ctx.send(
            f"**Starting level set to {level}.**\n"
            f"New characters created with `!createchar` will begin at level {level}."
        )

    @commands.command(name="startcampaign")
    async def start_campaign(self, ctx: commands.Context):
        """DM starts the campaign — adventure begins! Requires at least one character."""
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel. Use `!newcampaign` to create one.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can start the campaign.")
            return
        if campaign.phase == CampaignPhase.ACTIVE:
            await ctx.send("Campaign is already active!")
            return
        if campaign.phase not in (CampaignPhase.SETUP, CampaignPhase.PITCHING):
            await ctx.send("Campaign isn't in setup phase.")
            return

        complete_chars = [c for c in campaign.characters.values() if c.creation_complete]
        if not complete_chars:
            await ctx.send("No completed characters yet! Players need to finish `!createchar` first.")
            return

        campaign.phase = CampaignPhase.ACTIVE
        save_campaign(campaign)

        # Get opening narration from Claude
        dm_engine = self.bot.dm_engine
        async with ctx.typing():
            narration = await dm_engine.narrate_start(campaign)
        save_campaign(campaign)

        # Split long messages for Discord's 2000 char limit
        await self._send_long(ctx, narration)

    @commands.command(name="endcampaign")
    async def end_campaign(self, ctx: commands.Context):
        """DM ends the campaign permanently."""
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can end the campaign.")
            return

        name = campaign.name or "Unnamed Campaign"
        delete_campaign(str(ctx.channel.id))
        await ctx.send(f"**{name}** has ended. The tale is concluded.\nUse `!newcampaign` to start a new adventure.")

    @commands.command(name="campaigninfo")
    async def campaign_info(self, ctx: commands.Context):
        """Show campaign status and player list."""
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel. Use `!newcampaign` to create one.")
            return

        lines = [f"**{campaign.name or 'Unnamed Campaign'}**"]
        lines.append(f"Phase: **{campaign.phase.value.title()}**")
        if campaign.dm_id:
            lines.append(f"DM: <@{campaign.dm_id}>")
        if campaign.starting_level > 1:
            lines.append(f"Starting Level: **{campaign.starting_level}**")
        if campaign.description:
            lines.append(f"*{campaign.description}*")

        if campaign.characters:
            lines.append("\n**Party:**")
            for char in campaign.characters.values():
                if char.creation_complete:
                    lines.append(f"  {char.short_summary()}")
                else:
                    lines.append(f"  {char.owner_name} — Character creation in progress")
        else:
            lines.append("\nNo characters yet.")

        await ctx.send("\n".join(lines))

    async def _send_long(self, ctx: commands.Context, text: str):
        """Send a message, splitting if it exceeds Discord's limit."""
        while len(text) > 1990:
            # Find a good split point
            split_at = text.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await ctx.send(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            await ctx.send(text)


async def setup(bot: commands.Bot):
    await bot.add_cog(CampaignCog(bot))

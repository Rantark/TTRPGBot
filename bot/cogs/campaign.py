"""Campaign management cog: pitch, vote, setup, start, end."""

import asyncio
import io
import os
import random
import re

import discord
from discord.ext import commands

from bot.models.campaign import Campaign, CampaignPhase, CampaignPace, GameSystem
from bot.storage import save_campaign, save_campaign_by_id, load_campaign, delete_campaign, load_guild_settings, save_guild_settings


class CampaignCog(commands.Cog, name="Campaign"):
    """Commands for managing campaigns."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx: commands.Context) -> Campaign | None:
        """Load campaign for the current channel.

        Checks the current channel ID first. If we're in a thread,
        also checks the thread ID directly (for forum post campaigns).
        """
        # Direct lookup by current channel/thread ID
        campaign = load_campaign(str(ctx.channel.id))
        if campaign:
            return campaign

        # If we're in a thread, the campaign might be stored under the thread ID
        if isinstance(ctx.channel, discord.Thread):
            campaign = load_campaign(str(ctx.channel.id))
            if campaign:
                return campaign

        return None

    def _get_or_create_campaign(self, ctx: commands.Context) -> Campaign:
        campaign = load_campaign(str(ctx.channel.id))
        if campaign is None:
            campaign = Campaign(str(ctx.channel.id), str(ctx.guild.id))
            campaign.setup_channel_id = str(ctx.channel.id)
        return campaign

    @commands.command(name="newcampaign")
    async def new_campaign(self, ctx: commands.Context, *, name: str = ""):
        """Start a new campaign in this channel. You become the DM.

        Usage: !newcampaign My Epic Adventure
        """
        # If we're already in a forum post thread, don't allow newcampaign there
        if isinstance(ctx.channel, discord.Thread):
            await ctx.send(
                "Use `!newcampaign` in a regular channel, not inside a forum post.\n"
                "The bot will automatically create a forum post when you `!startcampaign`."
            )
            return

        existing = self._get_campaign(ctx)
        if existing and existing.phase != CampaignPhase.NONE:
            await ctx.send("There's already an active campaign in this channel. "
                           "Use `!endcampaign` to end it first.")
            return

        # Ask for game system selection
        msg = await ctx.send(
            "**New Campaign — Choose Game System**\n\n"
            "1\u20e3 **D&D 5th Edition** — Classic fantasy adventure\n"
            "2\u20e3 **World of Darkness** — Vampire: The Requiem / Gothic horror\n\n"
            "*React to choose or type `1` or `2`*"
        )
        emojis = ["1\u20e3", "2\u20e3"]
        for emoji in emojis:
            await msg.add_reaction(emoji)

        system_map = {"1\u20e3": "dnd5e", "2\u20e3": "wod"}

        def check_reaction(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in emojis
                and reaction.message.id == msg.id
            )

        def check_message(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.strip() in ("1", "2")
            )

        game_system = None
        done, pending = await asyncio.wait(
            [
                asyncio.ensure_future(self.bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)),
                asyncio.ensure_future(self.bot.wait_for("message", timeout=60.0, check=check_message)),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        try:
            result = done.pop().result()
            if isinstance(result, tuple):
                reaction, _ = result
                game_system = system_map.get(str(reaction.emoji), "dnd5e")
            else:
                game_system = "dnd5e" if result.content.strip() == "1" else "wod"
        except (asyncio.TimeoutError, Exception):
            await ctx.send("Campaign creation timed out. Try again with `!newcampaign`.")
            return

        campaign = Campaign(str(ctx.channel.id), str(ctx.guild.id), game_system=game_system)
        campaign.dm_id = str(ctx.author.id)
        campaign.setup_channel_id = str(ctx.channel.id)
        campaign.phase = CampaignPhase.PITCHING

        system_label = "World of Darkness" if game_system == "wod" else "D&D 5e"
        create_cmd = "`!createwod`" if game_system == "wod" else "`!createchar`"

        if name:
            campaign.name = name
            campaign.phase = CampaignPhase.SETUP
            save_campaign(campaign)
            await ctx.send(
                f"**Campaign Created: {name}** ({system_label})\n"
                f"DM: {ctx.author.display_name}\n"
                f"Phase: **Setup** — Players can now create characters with {create_cmd}\n"
                + (f"DM: Use `!setlevel <level>` to set the starting level (default: 1)\n" if game_system == "dnd5e" else "")
                + "When everyone is ready, the DM uses `!startcampaign` to begin!"
            )
        else:
            save_campaign(campaign)
            await ctx.send(
                f"**New Campaign Started!** ({system_label})\n"
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

    @commands.command(name="randompitch")
    async def random_pitch(self, ctx: commands.Context):
        """DM selects a random pitch to move to setup phase.

        Usage: !randompitch
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.PITCHING:
            await ctx.send("No campaign in pitching phase.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can select a pitch.")
            return
        if not campaign.pitches:
            await ctx.send("No pitches to choose from. Use `!pitch <title> | <description>` first.")
            return

        pitch = random.choice(campaign.pitches)
        campaign.name = pitch["title"]
        campaign.description = pitch["description"]
        campaign.phase = CampaignPhase.SETUP
        save_campaign(campaign)

        await ctx.send(
            f"**The fates have chosen: {pitch['title']}!**\n"
            f"*{pitch['description']}*\n\n"
            "Phase: **Setup** — Players, create your characters with `!createchar`!\n"
            "When everyone is ready, the DM uses `!startcampaign` to begin the adventure."
        )

    @commands.command(name="deletepitch")
    async def delete_pitch(self, ctx: commands.Context, number: int = 0):
        """Delete a pitch by number. Authors can delete their own; DM can delete any.

        Usage: !deletepitch 2
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.PITCHING:
            await ctx.send("No campaign in pitching phase.")
            return

        if not campaign.pitches:
            await ctx.send("No pitches to delete.")
            return

        if number < 1 or number > len(campaign.pitches):
            await ctx.send(f"Invalid pitch number. Choose 1-{len(campaign.pitches)}.")
            return

        pitch = campaign.pitches[number - 1]
        is_author = str(ctx.author.id) == pitch["author_id"]
        is_dm = str(ctx.author.id) == campaign.dm_id
        if not is_author and not is_dm:
            await ctx.send("You can only delete your own pitches (or be the DM).")
            return

        campaign.pitches.pop(number - 1)
        save_campaign(campaign)
        await ctx.send(f"Pitch **#{number}: {pitch['title']}** has been deleted.")

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
        """DM starts the campaign — creates a forum post or thread and begins the adventure!

        If CAMPAIGN_FORUM_ID is set in .env, creates a forum post.
        Otherwise falls back to creating a thread or playing in the current channel.
        Requires at least one character.
        """
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

        campaign.setup_channel_id = str(ctx.channel.id)

        # Try creating a forum post first if configured
        # Check guild settings first (set via !setforum), then fall back to .env
        guild_settings = load_guild_settings(str(ctx.guild.id))
        forum_channel_id = guild_settings.get("campaign_forum_id") or os.getenv("CAMPAIGN_FORUM_ID")
        if forum_channel_id:
            try:
                forum_channel = self.bot.get_channel(int(forum_channel_id))
                if forum_channel and isinstance(forum_channel, discord.ForumChannel):
                    await self._start_in_forum(ctx, campaign, forum_channel)
                    return
                elif forum_channel:
                    await ctx.send("Configured CAMPAIGN_FORUM_ID is not a forum channel. Falling back to thread.")
                else:
                    await ctx.send("Configured forum channel not found. Falling back to thread.")
            except (ValueError, Exception) as e:
                import traceback
                tb = traceback.format_exc()
                await ctx.send(
                    f"❌ **Error Accessing Forum Channel**\n"
                    f"```\n{tb[-1500:] if len(tb) > 1500 else tb}\n```\n"
                    f"Falling back to thread..."
                )

        # Fall back to thread-based or channel-based start
        await self._start_in_thread(ctx, campaign)

    async def _start_in_forum(self, ctx: commands.Context, campaign: Campaign, forum_channel: discord.ForumChannel):
        """Start the campaign by creating a new forum post thread."""
        system_label = "WoD" if campaign.game_system == GameSystem.WOD else "D&D"
        campaign_name = campaign.name or f"{system_label} Campaign"
        player_mentions = ", ".join(f"<@{pid}>" for pid in campaign.characters.keys())

        await ctx.send(f"Creating forum post for **{campaign_name}**...")

        try:
            # Create the forum post
            forum_post = await forum_channel.create_thread(
                name=f"{campaign_name}",
                content=(
                    f"# {campaign_name}\n\n"
                    f"**DM:** <@{campaign.dm_id}>\n"
                    f"**Players:** {player_mentions}\n\n"
                    f"*The adventure is about to begin...*"
                ),
                reason=f"D&D Campaign: {campaign_name}",
            )

            # Handle both tuple and direct Thread returns
            thread = forum_post[0] if isinstance(forum_post, tuple) else forum_post

            # Update campaign tracking
            old_channel_id = campaign.channel_id
            campaign.forum_post_id = str(thread.id)
            campaign.thread_id = str(thread.id)
            campaign.setup_channel_id = str(ctx.channel.id)
            campaign.parent_channel_id = str(forum_channel.id)

            # IMPORTANT: Update the campaign's primary channel_id to the forum post thread
            # This allows all gameplay commands to find it when used inside the forum post
            campaign.channel_id = str(thread.id)
            campaign.phase = CampaignPhase.ACTIVE

            # Save under BOTH the new forum post thread ID AND the old setup channel ID
            # This way it's findable from both locations
            save_campaign(campaign)  # Saves under campaign.channel_id (forum post thread ID)
            save_campaign_by_id(campaign, old_channel_id)  # Also save under setup channel

            # Announce in the setup channel with link to forum post
            await ctx.send(
                f"**{campaign_name}** has begun!\n"
                f"Forum Post: {thread.mention}\n"
                f"All gameplay happens there — head over to begin your adventure!\n"
                f"Players: {player_mentions}"
            )

            # Generate and send opening narration in the forum post
            async with ctx.typing():
                narration = await self.bot.dm_engine.narrate_start(campaign)
            save_campaign(campaign)

            await self._send_long_to(thread, narration)

        except discord.Forbidden as e:
            await ctx.send(
                f"❌ **Forum Permission Error**\n"
                f"```\n{type(e).__name__}: {e}\n```\n"
                f"Fix: Give me 'Create Posts' permission in the forum channel.\n"
                f"Falling back to thread..."
            )
            await self._start_in_thread(ctx, campaign)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            await ctx.send(
                f"❌ **Forum Post Creation Failed**\n"
                f"```\n{tb[-1500:] if len(tb) > 1500 else tb}\n```\n"
                f"Falling back to thread..."
            )
            await self._start_in_thread(ctx, campaign)

    async def _start_in_thread(self, ctx: commands.Context, campaign: Campaign):
        """Start the campaign by creating a thread (or playing in current channel)."""
        # Create a game thread for the campaign
        thread = None
        if not isinstance(ctx.channel, discord.Thread):
            try:
                thread_name = campaign.name or "D&D Campaign"
                thread = await ctx.channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.public_thread,
                    reason=f"D&D Campaign: {thread_name}",
                )
                campaign.thread_id = str(thread.id)
                campaign.parent_channel_id = str(ctx.channel.id)
            except discord.Forbidden:
                # No thread permissions — fall back to playing in the channel
                pass

        campaign.phase = CampaignPhase.ACTIVE
        save_campaign(campaign)

        # Get opening narration from Claude
        dm_engine = self.bot.dm_engine
        target = thread or ctx.channel

        if thread:
            # Announce in the main channel
            player_mentions = ", ".join(f"<@{pid}>" for pid in campaign.characters.keys())
            await ctx.send(
                f"**{campaign.name}** has begun!\n"
                f"All gameplay will happen in {thread.mention}\n"
                f"Players: {player_mentions}"
            )
            # Welcome message in thread
            await thread.send(
                f"**Welcome to {campaign.name}!**\n"
                f"DM: <@{campaign.dm_id}>\n"
                f"All commands (`!action`, `!roll`, etc.) should be used in this thread.\n"
            )

        async with ctx.typing():
            narration = await dm_engine.narrate_start(campaign)
        save_campaign(campaign)

        # Send narration to thread (or channel if no thread)
        await self._send_long_to(target, narration)

    def _cleanup_campaign(self, campaign: Campaign, current_channel_id: str):
        """Delete all save files associated with a campaign."""
        ids_to_delete = set()
        ids_to_delete.add(current_channel_id)
        if campaign.channel_id:
            ids_to_delete.add(campaign.channel_id)
        if campaign.thread_id:
            ids_to_delete.add(campaign.thread_id)
        if campaign.forum_post_id:
            ids_to_delete.add(campaign.forum_post_id)
        if campaign.setup_channel_id:
            ids_to_delete.add(campaign.setup_channel_id)
        if campaign.parent_channel_id:
            ids_to_delete.add(campaign.parent_channel_id)

        for cid in ids_to_delete:
            delete_campaign(cid)

    async def _archive_and_notify(self, ctx: commands.Context, campaign: Campaign, name: str):
        """Archive thread/forum post and notify setup channel."""
        if isinstance(ctx.channel, discord.Thread):
            try:
                await ctx.channel.edit(archived=True)
            except discord.Forbidden:
                pass

            # Notify the setup/parent channel
            notify_id = campaign.setup_channel_id or campaign.parent_channel_id
            if notify_id:
                try:
                    notify_ch = self.bot.get_channel(int(notify_id))
                    if notify_ch:
                        await notify_ch.send(f"**{name}** has ended. The forum post has been archived.")
                except Exception:
                    pass

    async def _generate_and_upload_story(self, ctx, campaign):
        """Generate a campaign story and upload it as a text file to Discord."""
        name = campaign.name or "Unnamed Campaign"
        safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

        await ctx.send(f"*The chronicler begins writing the tale of **{name}**... This may take a moment.*")

        async with ctx.typing():
            story_text = await self.bot.dm_engine.generate_campaign_story(campaign)

        if story_text.startswith("Failed to generate"):
            await ctx.send(f"Could not generate the story: {story_text}")
            return

        # Upload as a .txt file
        file_bytes = story_text.encode("utf-8")
        file = discord.File(
            io.BytesIO(file_bytes),
            filename=f"{safe_name}_story.txt",
        )
        await ctx.send(
            f"**The Tale of {name}**\n"
            f"*{len(story_text):,} characters, uploaded as a text file for your reading pleasure.*",
            file=file,
        )

    @commands.command(name="exportstory", aliases=["story"])
    async def export_story(self, ctx: commands.Context):
        """Generate a polished narrative of the campaign and upload it as a text file.

        Claude writes the entire campaign story as a fantasy narrative,
        using session logs, conversation history, and character info.
        Anyone can use this at any time during the campaign.

        Usage: !exportstory
        Usage: !story
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase == CampaignPhase.NONE:
            await ctx.send("No campaign in this channel.")
            return

        await self._generate_and_upload_story(ctx, campaign)

    @commands.command(name="endcampaign")
    async def end_campaign(self, ctx: commands.Context):
        """DM ends the campaign permanently. Archives the game thread/forum post if one exists."""
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if str(ctx.author.id) != campaign.dm_id:
            await ctx.send("Only the DM can end the campaign.")
            return

        name = campaign.name or "Unnamed Campaign"

        # Generate and upload the campaign story BEFORE cleanup deletes the data
        await self._generate_and_upload_story(ctx, campaign)

        # Delete all save files for this campaign
        self._cleanup_campaign(campaign, str(ctx.channel.id))

        await ctx.send(
            f"**{name}** has ended. The tale is concluded.\n"
            f"Use `!newcampaign` to start a new adventure."
        )

        await self._archive_and_notify(ctx, campaign, name)

    @commands.command(name="forceend")
    @commands.has_permissions(administrator=True)
    async def force_end_campaign(self, ctx: commands.Context):
        """(Admin) Force end a campaign even if the DM is absent.

        Usage: !forceend
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        name = campaign.name or "Unnamed Campaign"
        dm_mention = f"<@{campaign.dm_id}>" if campaign.dm_id else "Unknown"

        # Generate and upload the campaign story BEFORE cleanup deletes the data
        await self._generate_and_upload_story(ctx, campaign)

        # Delete all save files for this campaign
        self._cleanup_campaign(campaign, str(ctx.channel.id))

        await ctx.send(
            f"**{name}** has been force-ended by {ctx.author.display_name}.\n"
            f"(Original DM: {dm_mention})\n"
            f"Use `!newcampaign` to start a new adventure."
        )

        await self._archive_and_notify(ctx, campaign, name)

    @commands.command(name="setpace")
    async def set_pace(self, ctx: commands.Context, *, pace: str = ""):
        """DM or Admin: Set the campaign pace mode.

        ASYNC = no timeout, players take as long as they need (default).
        LIVE = 30-minute AFK timeout; idle players auto-pass.

        Usage: !setpace live
        Usage: !setpace async
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        is_dm = str(ctx.author.id) == campaign.dm_id
        is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
        if not is_dm and not is_admin:
            await ctx.send("Only the DM or an admin can change the campaign pace.")
            return

        pace = pace.strip().lower()
        if pace not in ("async", "live"):
            await ctx.send(
                "**Usage:** `!setpace <async|live>`\n"
                f"Current pace: **{campaign.pace.value}**\n\n"
                "**async** — No timeout, players take as long as they need (default)\n"
                "**live** — 30-minute AFK timeout; idle players auto-pass each round"
            )
            return

        campaign.pace = CampaignPace(pace)
        save_campaign(campaign)
        if pace == "live":
            await ctx.send(
                "Campaign pace set to **LIVE**.\n"
                "Players who haven't acted within 30 minutes will auto-pass."
            )
        else:
            await ctx.send(
                "Campaign pace set to **ASYNC**.\n"
                "No timeout — players can take as long as they need."
            )

    @commands.command(name="suggestcampaign")
    async def suggest_campaign(self, ctx: commands.Context):
        """Ask Claude to suggest campaign ideas based on your play style.

        Usage: !suggestcampaign
        """
        existing = self._get_campaign(ctx)
        if existing and existing.phase != CampaignPhase.NONE:
            await ctx.send("There's already an active campaign in this channel. "
                           "Use `!endcampaign` to end it first.")
            return

        # ── Step 1: Choose game system ──
        system_msg = await ctx.send(
            "**\U0001f3b2 Campaign Suggestions**\n\n"
            "First, which game system?\n\n"
            "\u2694\ufe0f **D&D 5th Edition** \u2014 Classic fantasy adventure\n"
            "\U0001f9db **World of Darkness** \u2014 Vampire: The Requiem / Gothic horror\n\n"
            "*React to choose or type `1` or `2`*"
        )

        sys_emojis = ["\u2694\ufe0f", "\U0001f9db"]
        for emoji in sys_emojis:
            await system_msg.add_reaction(emoji)

        def check_sys_reaction(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in sys_emojis
                and reaction.message.id == system_msg.id
            )

        def check_sys_message(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.strip() in ("1", "2")
            )

        game_system = None
        done, pending = await asyncio.wait(
            [
                asyncio.ensure_future(self.bot.wait_for("reaction_add", timeout=60.0, check=check_sys_reaction)),
                asyncio.ensure_future(self.bot.wait_for("message", timeout=60.0, check=check_sys_message)),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        try:
            result = done.pop().result()
            if isinstance(result, tuple):
                reaction, _ = result
                game_system = "dnd5e" if str(reaction.emoji) == "\u2694\ufe0f" else "wod"
            else:
                game_system = "dnd5e" if result.content.strip() == "1" else "wod"
        except (asyncio.TimeoutError, Exception):
            await ctx.send("Campaign suggestion timed out. Try again with `!suggestcampaign`.")
            return

        is_wod = game_system == "wod"
        system_label = "World of Darkness" if is_wod else "D&D 5e"
        system_emoji = "\U0001f9db" if is_wod else "\u2694\ufe0f"

        # ── Step 2: Choose play style (system-appropriate) ──
        if is_wod:
            style_prompt = (
                f"**{system_emoji} {system_label} \u2014 What kind of chronicle?**\n\n"
                "1\u20e3 **Political Intrigue** \u2014 Vampire court politics, power struggles, and betrayal\n"
                "2\u20e3 **Horror/Survival** \u2014 Hunted by ancient terrors, fighting to survive the night\n"
                "3\u20e3 **Mystery/Investigation** \u2014 Uncover conspiracies, track down rogue Kindred\n"
                "4\u20e3 **Personal Drama** \u2014 Struggle with humanity, relationships, and the Beast within\n"
                "5\u20e3 **Surprise Me** \u2014 Let Claude decide!\n\n"
                "React with a number or type `1`\u2013`5`"
            )
            style_map = {
                "1\u20e3": "political intrigue with vampire court politics, power struggles between covenants, and backstabbing betrayal",
                "2\u20e3": "horror and survival where the coterie is hunted by ancient terrors and must fight to survive against powerful enemies",
                "3\u20e3": "mystery and investigation focused on uncovering Kindred conspiracies, tracking rogue vampires, and solving supernatural crimes",
                "4\u20e3": "personal drama exploring the struggle with humanity, mortal relationships, the Beast within, and what it means to be Kindred",
                "5\u20e3": "a balanced mix of all elements \u2014 surprise me with something unique and compelling",
            }
        else:
            style_prompt = (
                f"**{system_emoji} {system_label} \u2014 What kind of campaign?**\n\n"
                "1\u20e3 **Combat-Focused** \u2014 Battles and tactical encounters\n"
                "2\u20e3 **Roleplay-Heavy** \u2014 Political intrigue, social encounters\n"
                "3\u20e3 **Mystery/Investigation** \u2014 Solve crimes, uncover conspiracies\n"
                "4\u20e3 **Exploration** \u2014 Discover new lands, dungeon crawling\n"
                "5\u20e3 **Surprise Me** \u2014 Let Claude decide!\n\n"
                "React with a number or type `1`\u2013`5`"
            )
            style_map = {
                "1\u20e3": "combat-focused with lots of battles and tactical encounters",
                "2\u20e3": "roleplay-heavy with political intrigue and social encounters",
                "3\u20e3": "mystery and investigation focused on solving crimes and uncovering secrets",
                "4\u20e3": "exploration-focused with dungeon crawling and discovering new lands",
                "5\u20e3": "a balanced mix of all elements \u2014 surprise me with something unique",
            }

        msg = await ctx.send(style_prompt)
        emojis = ["1\u20e3", "2\u20e3", "3\u20e3", "4\u20e3", "5\u20e3"]
        for emoji in emojis:
            await msg.add_reaction(emoji)

        def check_reaction(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in emojis
                and reaction.message.id == msg.id
            )

        def check_message(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.strip() in ("1", "2", "3", "4", "5")
            )

        style = None
        done, pending = await asyncio.wait(
            [
                asyncio.ensure_future(self.bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)),
                asyncio.ensure_future(self.bot.wait_for("message", timeout=60.0, check=check_message)),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        try:
            result = done.pop().result()
            if isinstance(result, tuple):
                reaction, _ = result
                style = style_map.get(str(reaction.emoji))
            else:
                idx = int(result.content.strip()) - 1
                style = list(style_map.values())[idx]
        except (asyncio.TimeoutError, Exception):
            await ctx.send("Campaign suggestion timed out. Try again with `!suggestcampaign`.")
            return

        if not style:
            await ctx.send("Invalid choice.")
            return

        # ── Step 3: Generate suggestions from Claude ──
        await ctx.send(f"{system_emoji} Claude is brainstorming {system_label} campaign ideas...")

        if is_wod:
            prompt = (
                f"Generate 3 World of Darkness (Vampire: The Requiem) chronicle concepts that are {style}.\n\n"
                "These are campaigns for a coterie (group) of vampires in a modern gothic setting.\n"
                "The five clans are: Daeva (seductive), Gangrel (feral), Mekhet (shadowy), "
                "Nosferatu (monstrous), and Ventrue (commanding).\n"
                "The five covenants are: Carthian Movement, Circle of the Crone, Invictus, "
                "Lancea et Sanctum, and Ordo Dracul.\n\n"
                "For each chronicle, provide:\n"
                "- A compelling title (3-6 words, gothic/dark tone)\n"
                "- A 2-3 sentence hook that makes players want to join\n"
                "- The setting city or region\n"
                "- Which clans/covenants are most relevant\n\n"
                "Format as:\n\n"
                "**1. [Title]**\n[Hook]\n*Setting: [city/region]* | *Key Factions: [clans/covenants]*\n\n"
                "**2. [Title]**\n[Hook]\n*Setting: [city/region]* | *Key Factions: [clans/covenants]*\n\n"
                "**3. [Title]**\n[Hook]\n*Setting: [city/region]* | *Key Factions: [clans/covenants]*"
            )
        else:
            prompt = (
                f"Generate 3 D&D 5e campaign concepts that are {style}.\n\n"
                "For each campaign, provide:\n"
                "- A compelling title (3-6 words)\n"
                "- A 2-3 sentence hook that makes players want to join\n"
                "- Suggested starting level (1-5)\n\n"
                "Format as:\n\n"
                "**1. [Title]**\n[Hook]\n*Starting Level: [level]*\n\n"
                "**2. [Title]**\n[Hook]\n*Starting Level: [level]*\n\n"
                "**3. [Title]**\n[Hook]\n*Starting Level: [level]*"
            )

        async with ctx.typing():
            suggestions = await self.bot.dm_engine.generate_simple_response(prompt)

        suggestion_msg = await ctx.send(
            f"**{system_emoji} {system_label} Campaign Suggestions:**\n\n"
            f"{suggestions}\n\n"
            "React with 1\u20e3, 2\u20e3, or 3\u20e3 to start that campaign, "
            "or use `!newcampaign <name>` to create your own."
        )

        pick_emojis = ["1\u20e3", "2\u20e3", "3\u20e3"]
        for emoji in pick_emojis:
            await suggestion_msg.add_reaction(emoji)

        def check_pick(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in pick_emojis
                and reaction.message.id == suggestion_msg.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=120.0, check=check_pick)
        except asyncio.TimeoutError:
            await ctx.send("Campaign selection timed out. Use `!newcampaign <name>` to create one manually.")
            return

        choice = pick_emojis.index(str(reaction.emoji))

        # Extract title from suggestions
        titles = re.findall(r'\*\*\d+\.\s*(.+?)\*\*', suggestions)
        if len(titles) > choice:
            campaign_name = titles[choice].strip()
        else:
            campaign_name = f"Campaign {choice + 1}"

        # Extract starting level if mentioned (D&D only)
        starting_level = 1
        if not is_wod:
            levels = re.findall(r'\*Starting Level:\s*(\d+)\*', suggestions)
            if len(levels) > choice:
                try:
                    starting_level = max(1, min(20, int(levels[choice])))
                except ValueError:
                    pass

        # Create the campaign with the chosen game system
        campaign = Campaign(str(ctx.channel.id), str(ctx.guild.id), game_system=game_system)
        campaign.dm_id = str(ctx.author.id)
        campaign.name = campaign_name
        campaign.phase = CampaignPhase.SETUP
        campaign.starting_level = starting_level
        save_campaign(campaign)

        create_cmd = "`!createwod`" if is_wod else "`!createchar`"
        level_note = f"\nStarting Level: **{starting_level}**" if starting_level > 1 and not is_wod else ""
        await ctx.send(
            f"**{system_emoji} Campaign Created: {campaign_name}** ({system_label})\n"
            f"DM: {ctx.author.display_name}{level_note}\n"
            f"Phase: **Setup** \u2014 Players can now create characters with {create_cmd}\n"
            + (f"DM: Use `!setlevel <level>` to set the starting level (default: 1)\n" if not is_wod else "")
            + "When everyone is ready, the DM uses `!startcampaign` to begin!"
        )

    @commands.command(name="campaigninfo")
    async def campaign_info(self, ctx: commands.Context):
        """Show campaign status and player list."""
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel. Use `!newcampaign` to create one.")
            return

        system_label = "World of Darkness" if campaign.game_system == GameSystem.WOD else "D&D 5e"
        lines = [f"**{campaign.name or 'Unnamed Campaign'}** ({system_label})"]
        lines.append(f"Phase: **{campaign.phase.value.title()}**")
        if campaign.dm_id:
            lines.append(f"DM: <@{campaign.dm_id}>")
        if campaign.starting_level > 1:
            lines.append(f"Starting Level: **{campaign.starting_level}**")
        if campaign.forum_post_id:
            lines.append(f"Forum Post: <#{campaign.forum_post_id}>")
        elif campaign.thread_id:
            lines.append(f"Game Thread: <#{campaign.thread_id}>")
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

    @commands.command(name="setforum")
    @commands.has_permissions(administrator=True)
    async def set_forum(self, ctx: commands.Context, channel: discord.ForumChannel = None):
        """(Admin) Set the forum channel where campaigns will be created.

        Usage: !setforum #campaigns
        Usage: !setforum 1234567890123456789
        """
        if channel is None:
            await ctx.send(
                "**Usage:** `!setforum #forum-channel`\n"
                "Mention or paste the ID of a **forum channel** where campaign posts will be created.\n"
                "Use `!clearforum` to remove the setting."
            )
            return

        settings = load_guild_settings(str(ctx.guild.id))
        settings["campaign_forum_id"] = str(channel.id)
        save_guild_settings(str(ctx.guild.id), settings)

        await ctx.send(
            f"Campaign forum set to {channel.mention}\n"
            f"New campaigns started with `!startcampaign` will create posts there."
        )

    @commands.command(name="clearforum")
    @commands.has_permissions(administrator=True)
    async def clear_forum(self, ctx: commands.Context):
        """(Admin) Remove the forum channel setting. Campaigns will use threads instead.

        Usage: !clearforum
        """
        settings = load_guild_settings(str(ctx.guild.id))
        if "campaign_forum_id" in settings:
            del settings["campaign_forum_id"]
            save_guild_settings(str(ctx.guild.id), settings)
            await ctx.send("Campaign forum cleared. `!startcampaign` will create threads instead.")
        else:
            await ctx.send("No forum channel was set. Nothing to clear.")

    @commands.command(name="debugforum")
    @commands.has_permissions(administrator=True)
    async def debug_forum(self, ctx: commands.Context):
        """(Admin) Debug forum channel configuration.

        Shows current forum settings and tests access.
        Usage: !debugforum
        """
        import traceback

        lines = ["**Forum Debug Info:**\n"]

        # Check .env setting
        env_forum_id = os.getenv("CAMPAIGN_FORUM_ID")
        lines.append(f"`.env CAMPAIGN_FORUM_ID`: `{env_forum_id or 'NOT SET'}`")

        # Check guild settings
        guild_settings = load_guild_settings(str(ctx.guild.id))
        settings_forum_id = guild_settings.get("campaign_forum_id")
        lines.append(f"`!setforum` setting: `{settings_forum_id or 'NOT SET'}`")

        # Determine which ID will be used
        active_id = settings_forum_id or env_forum_id
        lines.append(f"\nActive forum ID: `{active_id or 'NONE - will use threads instead'}`")

        if active_id:
            lines.append(f"\n**Testing channel access...**")
            try:
                channel = self.bot.get_channel(int(active_id))
                if channel is None:
                    lines.append(f"❌ Channel not found! ID `{active_id}` returned None.")
                    lines.append("Bot may not be in that server or channel doesn't exist.")
                elif isinstance(channel, discord.ForumChannel):
                    lines.append(f"✅ Found forum channel: **{channel.name}**")

                    # Check permissions
                    perms = channel.permissions_for(ctx.guild.me)
                    lines.append(f"\n**Bot Permissions in forum:**")
                    lines.append(f"View Channel: {'✅' if perms.view_channel else '❌'}")
                    lines.append(f"Send Messages: {'✅' if perms.send_messages else '❌'}")
                    lines.append(f"Create Posts: {'✅' if perms.create_public_threads else '❌'}")
                    lines.append(f"Send in Threads: {'✅' if perms.send_messages_in_threads else '❌'}")
                    lines.append(f"Embed Links: {'✅' if perms.embed_links else '❌'}")

                    if not perms.create_public_threads:
                        lines.append(f"\n⚠️ **Missing 'Create Posts' permission** — this is why forum posts fail!")
                else:
                    lines.append(f"❌ Channel found but it's a `{type(channel).__name__}`, not a ForumChannel!")
                    lines.append(f"Channel name: **{channel.name}**")
                    lines.append("Make sure you're pointing to a Forum channel, not a text channel.")
            except ValueError:
                lines.append(f"❌ Invalid channel ID format: `{active_id}`")
            except Exception as e:
                tb = traceback.format_exc()
                lines.append(f"❌ Error checking channel:\n```\n{tb[-1000:]}\n```")
        else:
            lines.append("\n⚠️ No forum configured. Use `!setforum #channel` or set `CAMPAIGN_FORUM_ID` in `.env`")

        # Also show current channel info
        lines.append(f"\n**Current channel type:** `{type(ctx.channel).__name__}`")
        lines.append(f"**Current channel ID:** `{ctx.channel.id}`")

        await ctx.send("\n".join(lines))

    async def _send_long(self, ctx: commands.Context, text: str):
        """Send a message to ctx, splitting if it exceeds Discord's limit."""
        await self._send_long_to(ctx, text)

    async def _send_long_to(self, target, text: str):
        """Send a message to any channel/thread, splitting if it exceeds Discord's limit."""
        while len(text) > 1990:
            split_at = text.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await target.send(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            await target.send(text)


async def setup(bot: commands.Bot):
    await bot.add_cog(CampaignCog(bot))

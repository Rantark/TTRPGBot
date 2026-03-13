"""Gameplay commands: action, IC, emote, OOC, look, inspect, talk, ask, roll, check, save, attack.

RP scene coordination: During non-combat RP, player actions are queued.
Once every active player has submitted an action (or used !pass), all
actions are bundled and sent to Claude as a single prompt so the DM can
respond to everyone at once without overlapping storylines.
"""

import time

import discord
from discord.ext import commands, tasks

from bot.models.campaign import CampaignPhase, CampaignPace, GameSystem
from bot.data.rules import ABILITY_NAMES, ABILITY_FULL_NAMES, SKILLS, modifier_str
from bot.dice import parse_and_roll, roll_check, roll_initiative, parse_adv_dis
from bot.wod_dice import roll_pool, parse_pool_args, roll_initiative_wod
from bot.dm_engine import parse_action_tags, extract_whispers
from bot.storage import load_campaign, save_campaign, list_campaigns
from bot.utils.fuzzy_match import suggest_skill, suggest_ability

AFK_TIMEOUT_MINUTES = 30
ASYNC_REMINDER_HOURS = 24
REMIND_COOLDOWN_SECONDS = 3600  # 1 hour


class GameplayCog(commands.Cog, name="Gameplay"):
    """In-game commands for playing D&D."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Per-channel cooldown for !remind: channel_id -> last use timestamp
        self._remind_cooldowns: dict[str, float] = {}
        self._afk_checker_loop.start()

    def cog_unload(self):
        self._afk_checker_loop.cancel()

    def _get_campaign(self, ctx):
        return load_campaign(str(ctx.channel.id))

    def _require_active(self, campaign):
        return campaign and campaign.phase == CampaignPhase.ACTIVE

    # ------------------------------------------------------------------
    # RP scene coordination helpers
    # ------------------------------------------------------------------

    async def _queue_action(self, ctx, campaign, action_text: str):
        """Queue a player's action. If all players have acted, resolve the round."""
        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_name = char.name if char else ctx.author.display_name

        # During combat, skip queuing — actions go straight to DM
        if campaign.combat.active:
            await self._dm_respond_immediate(ctx, campaign, action_text)
            return

        # If this player was holding, their action is a solo follow-up
        if player_id in campaign.held_players:
            campaign.held_players.remove(player_id)
            save_campaign(campaign)
            await self._send_status(ctx, f"**{char_name}** acts on their held action!")
            await self._dm_respond_immediate(ctx, campaign, action_text)
            save_campaign(campaign)
            # If more held players remain, prompt the next one
            if campaign.held_players:
                await self._prompt_next_held(ctx, campaign)
            else:
                await self._send_status(ctx, "*A new round begins.* Submit your actions!")
            return

        # Queue the action
        campaign.pending_actions[player_id] = action_text
        campaign.last_action_time = time.time()
        save_campaign(campaign)

        # Tell the channel this player has acted (status — auto-deletes)
        waiting = campaign.get_waiting_player_ids()
        if waiting:
            waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
            await self._send_status(
                ctx,
                f"**{char_name}**'s action is locked in.\n"
                f"Waiting on: {waiting_mentions}\n"
                f"Use `!action`, `!ic`, `!emote`, `!look`, `!inspect`, `!talk`, or `!pass` to continue."
            )
        # Check if everyone has acted
        if campaign.all_players_acted():
            await self._resolve_round(ctx, campaign)

    async def _resolve_round(self, ctx, campaign):
        """All players have acted or passed — send the bundled actions to Claude."""
        if not campaign.pending_actions:
            # Everyone passed, nothing to send
            campaign.clear_pending()
            save_campaign(campaign)
            await self._send_status(ctx, "*Everyone passes. The scene continues...*\nSubmit actions when ready.")
            return

        # Build a combined action message for Claude
        action_lines = []
        for pid, action_text in campaign.pending_actions.items():
            char = campaign.get_character(pid)
            char_name = char.name if char else f"Player {pid}"
            action_lines.append(f"{char_name}: {action_text}")

        if campaign.passed_players:
            for pid in campaign.passed_players:
                char = campaign.get_character(pid)
                char_name = char.name if char else f"Player {pid}"
                action_lines.append(f"{char_name}: [does nothing / waits]")

        combined = "\n".join(action_lines)
        party_summary = campaign.get_party_summary()

        # Clear pending before the API call
        campaign.clear_pending()
        save_campaign(campaign)

        # Send to Claude
        async with ctx.typing():
            raw_response = await self.bot.dm_engine.get_dm_response(
                campaign,
                f"[ROUND OF ACTIONS — All players have acted simultaneously]\n{combined}",
                "Party",
                party_summary,
                "Multiple players acted at once. Narrate the results of ALL their actions "
                "together in one cohesive scene. Address each character's action. "
                "End with a prompt for what happens next or what the party sees.",
            )

        campaign.add_session_log(f"Round resolved: {combined[:120]}")

        # Process action tags (damage, conditions, whispers, etc.)
        clean_response = await self._process_dm_response(ctx, campaign, raw_response)
        save_campaign(campaign)

        await self._send_long(ctx, clean_response)

        # If anyone held their action, prompt them before starting a new round
        if campaign.held_players:
            await self._prompt_next_held(ctx, campaign)
        else:
            await self._send_status(ctx, "*A new round begins.* Submit your actions!")

    async def _dm_respond_immediate(self, ctx, campaign, action_text: str):
        """Send action directly to Claude (used during combat or for !ask)."""
        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_summary = char.short_summary() if char else ""

        async with ctx.typing():
            raw_response = await self.bot.dm_engine.get_dm_response(
                campaign, action_text, ctx.author.display_name,
                char_summary,
            )

        campaign.add_session_log(f"{ctx.author.display_name}: {action_text[:80]}")

        # Process action tags (damage, conditions, whispers, etc.)
        clean_response = await self._process_dm_response(ctx, campaign, raw_response)
        save_campaign(campaign)

        await self._send_long(ctx, clean_response)

    async def _process_dm_response(self, ctx, campaign, raw_response: str) -> str:
        """Parse action tags, execute game state changes, send whispers, return clean text."""
        # Parse and execute action tags (DAMAGE, CONDITION, NPC_DEFEAT, SPELL_SLOT, combat)
        clean_text, log_entries, combat_events = parse_action_tags(raw_response, campaign)

        # Extract and send whispers
        clean_text, whispers = extract_whispers(clean_text)
        for char_name, secret_msg in whispers:
            player_id = campaign.get_player_id_by_char_name(char_name)
            if player_id:
                try:
                    member = ctx.guild.get_member(int(player_id))
                    if member:
                        await member.send(f"**DM whispers to {char_name}:**\n{secret_msg}")
                except (discord.Forbidden, Exception):
                    pass  # DMs disabled or member not found

        # Log state changes
        for entry in log_entries:
            campaign.add_session_log(entry)

        # Handle combat events from Claude's tags
        if combat_events:
            await self._handle_combat_events(ctx, campaign, combat_events)

        # Save if anything changed
        if log_entries or whispers or combat_events:
            save_campaign(campaign)

        return clean_text

    async def _handle_combat_events(self, ctx, campaign, combat_events: list[str]):
        """Process combat control tags from Claude's response."""
        from bot.models.campaign import CombatMap

        for event in combat_events:
            if event == "COMBAT_START":
                if not campaign.combat.active:
                    campaign.combat.active = True
                    campaign.combat.initiative_order = []
                    campaign.combat.current_turn_index = 0
                    campaign.combat.round_number = 1
                    campaign.combat.combat_map = CombatMap()
                    save_campaign(campaign)
                    await ctx.send(
                        "**COMBAT STARTED!**\n"
                        "All players: Roll initiative with `!initiative`\n"
                        "Once everyone has rolled, DM uses `!begincombat` to set the order and start turns."
                    )

            elif event == "COMBAT_END":
                if campaign.combat.active:
                    rounds = campaign.combat.round_number
                    campaign.combat.active = False
                    campaign.combat.initiative_order = []
                    campaign.combat.current_turn_index = 0
                    campaign.combat.round_number = 1
                    save_campaign(campaign)
                    await ctx.send(
                        f"**Combat has ended** after {rounds} round(s).\n"
                        f"Resume roleplay freely!"
                    )

            elif event == "NEXT_TURN":
                if campaign.combat.active and campaign.combat.initiative_order:
                    campaign.combat.advance_turn()
                    save_campaign(campaign)
                    current = campaign.combat.current_turn
                    if current:
                        if current.get("player_id"):
                            await ctx.send(
                                f"<@{current['player_id']}>, it's **{current['name']}**'s turn! "
                                f"What do you do?"
                            )
                        else:
                            # NPC turn — tell Claude to narrate it
                            await self._auto_npc_turn(ctx, campaign, current["name"])

            elif event.startswith("ADD_NPC:"):
                parts = event.split(":", 2)
                if len(parts) == 3:
                    npc_name = parts[1]
                    try:
                        init_roll = int(parts[2])
                    except ValueError:
                        continue
                    # Don't add duplicates
                    existing = [e["name"].lower() for e in campaign.combat.initiative_order]
                    if npc_name.lower() not in existing:
                        campaign.combat.initiative_order.append({
                            "name": npc_name,
                            "roll": init_roll,
                            "player_id": None,
                        })

    async def _auto_npc_turn(self, ctx, campaign, npc_name: str):
        """When it's an NPC's turn, ask Claude to narrate their action."""
        party_summary = campaign.get_party_summary()

        async with ctx.typing():
            raw_response = await self.bot.dm_engine.get_dm_response(
                campaign,
                f"[NPC TURN] It is {npc_name}'s turn in combat. "
                f"Narrate what {npc_name} does — attack a player, cast a spell, move, etc. "
                f"Use [DAMAGE: Name -X] if they deal damage. Use [NEXT_TURN] at the end to "
                f"advance to the next combatant. If {npc_name} is defeated or flees, "
                f"use [NPC_DEFEAT: {npc_name}].",
                "DM",
                party_summary,
            )

        clean_response = await self._process_dm_response(ctx, campaign, raw_response)
        save_campaign(campaign)
        await self._send_long(ctx, clean_response)

    async def _send_long(self, ctx, text: str):
        """Send a message, splitting if it exceeds Discord's limit."""
        while len(text) > 1990:
            split_at = text.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await ctx.send(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            await ctx.send(text)

    async def _send_status(self, ctx, text: str):
        """Send a status message. Use !cleanup to remove these manually."""
        await ctx.send(text)

    async def _try_delete_command(self, ctx):
        """Try to delete the user's command message to reduce clutter."""
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    # ------------------------------------------------------------------
    # Held action helpers
    # ------------------------------------------------------------------

    async def _prompt_next_held(self, ctx, campaign):
        """Prompt the next held player to submit their follow-up action."""
        if not campaign.held_players:
            await self._send_status(ctx, "*A new round begins.* Submit your actions!")
            return

        next_pid = campaign.held_players[0]
        char = campaign.get_character(next_pid)
        char_name = char.name if char else f"<@{next_pid}>"
        await self._send_status(
            ctx,
            f"**{char_name}** (<@{next_pid}>), the scene has played out. "
            f"What do you do with your held action?\n"
            f"Use `!action`, `!ic`, `!emote`, etc. to respond, or `!pass` to do nothing."
        )

    # ------------------------------------------------------------------
    # AFK timeout checker (LIVE pace only)
    # ------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def _afk_checker_loop(self):
        """Periodically check campaigns for AFK players and send async reminders."""
        try:
            await self._check_afk_rounds()
            await self._check_async_reminders()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Error in AFK checker loop")

    @_afk_checker_loop.before_loop
    async def _before_afk_checker(self):
        await self.bot.wait_until_ready()

    async def _check_afk_rounds(self):
        """Scan all campaigns for stalled LIVE-pace rounds and auto-resolve."""
        for channel_id in list_campaigns():
            campaign = load_campaign(channel_id)
            if not campaign:
                continue
            if campaign.phase != CampaignPhase.ACTIVE:
                continue
            if campaign.pace != CampaignPace.LIVE:
                continue
            if campaign.combat.active:
                continue
            if not campaign.last_action_time:
                continue
            if not campaign.pending_actions and not campaign.passed_players:
                continue

            elapsed = time.time() - campaign.last_action_time
            if elapsed >= AFK_TIMEOUT_MINUTES * 60:
                await self._resolve_round_in_channel(channel_id, campaign)

    async def _check_async_reminders(self):
        """In ASYNC campaigns, ping idle players every 24 hours."""
        now = time.time()
        reminder_interval = ASYNC_REMINDER_HOURS * 3600

        for channel_id in list_campaigns():
            campaign = load_campaign(channel_id)
            if not campaign:
                continue
            if campaign.phase != CampaignPhase.ACTIVE:
                continue
            if campaign.pace != CampaignPace.ASYNC:
                continue
            if campaign.combat.active:
                continue
            if not campaign.last_action_time:
                continue

            # Must have waiting players
            waiting = campaign.get_waiting_player_ids()
            if not waiting:
                continue

            # Check time since last action or last reminder (whichever is more recent)
            last_event = max(campaign.last_action_time, campaign.last_reminder_time)
            if now - last_event < reminder_interval:
                continue

            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                continue

            waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
            await channel.send(
                f"**Reminder** — The party is waiting on: {waiting_mentions}\n"
                f"Submit your action (`!action`, `!ic`, `!pass`, etc.) to keep the adventure moving!"
            )

            campaign.last_reminder_time = now
            save_campaign(campaign)

    async def _resolve_round_in_channel(self, channel_id: str, campaign):
        """Auto-resolve a stalled round by passing all idle players."""
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return

        # Auto-pass any players who haven't acted
        waiting = campaign.get_waiting_player_ids()
        if not waiting:
            return

        for pid in waiting:
            if pid not in campaign.passed_players:
                campaign.passed_players.append(pid)

        waiting_names = []
        for pid in waiting:
            char = campaign.get_character(pid)
            waiting_names.append(char.name if char else f"<@{pid}>")

        await channel.send(
            f"**AFK Timeout** — {', '.join(waiting_names)} auto-passed after "
            f"{AFK_TIMEOUT_MINUTES} minutes of inactivity."
        )

        # Now resolve the round
        if not campaign.pending_actions:
            campaign.clear_pending()
            save_campaign(campaign)
            await channel.send("*Everyone passed. The scene continues...*\nSubmit actions when ready.")
            return

        # Build combined action message
        action_lines = []
        for pid, action_text in campaign.pending_actions.items():
            char = campaign.get_character(pid)
            char_name = char.name if char else f"Player {pid}"
            action_lines.append(f"{char_name}: {action_text}")

        for pid in campaign.passed_players:
            char = campaign.get_character(pid)
            char_name = char.name if char else f"Player {pid}"
            action_lines.append(f"{char_name}: [does nothing / waits]")

        combined = "\n".join(action_lines)
        party_summary = campaign.get_party_summary()

        campaign.clear_pending()
        campaign.held_players = []  # AFK timeout clears held actions too
        save_campaign(campaign)

        raw_response = await self.bot.dm_engine.get_dm_response(
            campaign,
            f"[ROUND OF ACTIONS — All players have acted simultaneously]\n{combined}",
            "Party",
            party_summary,
            "Multiple players acted at once. Narrate the results of ALL their actions "
            "together in one cohesive scene. Address each character's action. "
            "End with a prompt for what happens next or what the party sees.",
        )

        campaign.add_session_log(f"Round resolved (AFK timeout): {combined[:120]}")

        # Process action tags
        clean_text, log_entries, combat_events = parse_action_tags(raw_response, campaign)
        clean_text, whispers = extract_whispers(clean_text)
        for char_name, secret_msg in whispers:
            player_id = campaign.get_player_id_by_char_name(char_name)
            if player_id and channel.guild:
                try:
                    member = channel.guild.get_member(int(player_id))
                    if member:
                        await member.send(f"**DM whispers to {char_name}:**\n{secret_msg}")
                except Exception:
                    pass
        for entry in log_entries:
            campaign.add_session_log(entry)
        # Combat events from AFK-resolved rounds are rare but handle gracefully
        for event in combat_events:
            if event == "COMBAT_START" and not campaign.combat.active:
                from bot.models.campaign import CombatMap
                campaign.combat.active = True
                campaign.combat.initiative_order = []
                campaign.combat.current_turn_index = 0
                campaign.combat.round_number = 1
                campaign.combat.combat_map = CombatMap()
                await channel.send(
                    "**COMBAT STARTED!**\n"
                    "All players: Roll initiative with `!initiative`\n"
                    "Once everyone has rolled, DM uses `!begincombat` to start turns."
                )
            elif event == "COMBAT_END" and campaign.combat.active:
                rounds = campaign.combat.round_number
                campaign.combat.active = False
                campaign.combat.initiative_order = []
                campaign.combat.current_turn_index = 0
                campaign.combat.round_number = 1
                await channel.send(f"**Combat has ended** after {rounds} round(s).\nResume roleplay freely!")
            elif event.startswith("ADD_NPC:"):
                parts = event.split(":", 2)
                if len(parts) == 3:
                    npc_name = parts[1]
                    try:
                        init_roll = int(parts[2])
                        existing = [e["name"].lower() for e in campaign.combat.initiative_order]
                        if npc_name.lower() not in existing:
                            campaign.combat.initiative_order.append({
                                "name": npc_name, "roll": init_roll, "player_id": None,
                            })
                    except ValueError:
                        pass
        save_campaign(campaign)

        # Send the response
        while len(clean_text) > 1990:
            split_at = clean_text.rfind("\n", 0, 1990)
            if split_at == -1:
                split_at = 1990
            await channel.send(clean_text[:split_at])
            clean_text = clean_text[split_at:].lstrip("\n")
        if clean_text:
            await channel.send(clean_text)
        await channel.send("*A new round begins.* Submit your actions!")

    # ------------------------------------------------------------------
    # RP action commands (queued during non-combat)
    # ------------------------------------------------------------------

    @commands.command(name="action")
    async def action(self, ctx: commands.Context, *, description: str = None):
        """Describe what your character does. Queued until all players act.

        Usage: !action I search the room for hidden doors
        """
        if not description:
            await ctx.send(
                "Please describe your action.\n"
                "**Usage:** `!action <description>`\n"
                "**Example:** `!action I search the room for traps`"
            )
            return
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign. The DM needs to `!startcampaign` first.")
            return
        await self._queue_action(ctx, campaign, f"[ACTION] {description}")

    @commands.command(name="ic")
    async def in_character(self, ctx: commands.Context, *, dialogue: str = None):
        """Speak in character. Queued until all players act.

        Usage: !ic "Halt! Who goes there?"
        """
        if not dialogue:
            await ctx.send(
                "Please provide dialogue.\n"
                '**Usage:** `!ic <dialogue>`\n'
                '**Example:** `!ic "Does anyone else hear that?"`'
            )
            return
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_name = char.name if char else ctx.author.display_name
        await self._queue_action(ctx, campaign, f'[IN CHARACTER] {char_name} says: "{dialogue}"')

    @commands.command(name="emote")
    async def emote(self, ctx: commands.Context, *, description: str = None):
        """Describe your character's actions or expressions. Queued until all players act.

        Usage: !emote leans against the wall and crosses her arms
        """
        if not description:
            await ctx.send(
                "Please describe an emote.\n"
                "**Usage:** `!emote <action>`\n"
                "**Example:** `!emote leans against the wall and crosses her arms`"
            )
            return
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_name = char.name if char else ctx.author.display_name
        await self._queue_action(ctx, campaign, f"[EMOTE] *{char_name} {description}*")

    @commands.command(name="look")
    async def look(self, ctx: commands.Context):
        """Ask the DM to describe the current scene. Queued until all players act.

        Usage: !look
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        await self._queue_action(ctx, campaign,
                                 "[LOOK] Describe the current scene and surroundings in detail.")

    @commands.command(name="inspect")
    async def inspect(self, ctx: commands.Context, *, target: str = None):
        """Examine something in the scene. Queued until all players act.

        Usage: !inspect the old chest
        """
        if not target:
            await ctx.send(
                "Please specify what to examine.\n"
                "**Usage:** `!inspect <target>`\n"
                "**Example:** `!inspect the old chest`"
            )
            return
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        await self._queue_action(ctx, campaign,
                                 f"[INSPECT] I examine {target} closely. What do I notice?")

    @commands.command(name="talk")
    async def talk(self, ctx: commands.Context, *, target: str = None):
        """Talk to an NPC. The DM roleplays them. Queued until all players act.

        Usage: !talk the bartender
        """
        if not target:
            await ctx.send(
                "Please specify which NPC you want to talk to.\n"
                "**Usage:** `!talk <NPC name>`\n"
                "**Example:** `!talk Innkeeper`\n"
                "Use `!npcs` to see known NPCs."
            )
            return
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        char = campaign.get_character(str(ctx.author.id))
        char_name = char.name if char else ctx.author.display_name
        await self._queue_action(ctx, campaign,
                                 f"[TALK] {char_name} approaches and speaks to {target}. "
                                 "Roleplay this NPC and their response.")

    @commands.command(name="pass")
    async def pass_turn(self, ctx: commands.Context):
        """Pass your turn — do nothing this round (works in RP and combat).

        Usage: !pass
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_name = char.name if char else ctx.author.display_name

        # Combat pass is handled by the combat cog
        if campaign.combat.active:
            # Delegate to combat cog's pass
            combat_cog = self.bot.get_cog("Combat")
            if combat_cog:
                await combat_cog.pass_turn(ctx)
            return

        # If player is holding, passing means they forfeit their held action
        if player_id in campaign.held_players:
            campaign.held_players.remove(player_id)
            save_campaign(campaign)
            await self._send_status(ctx, f"**{char_name}** lets their held action pass.")
            # If more held players remain, prompt the next one
            if campaign.held_players:
                await self._prompt_next_held(ctx, campaign)
            else:
                await self._send_status(ctx, "*A new round begins.* Submit your actions!")
            return

        # RP pass
        if player_id not in campaign.passed_players:
            campaign.passed_players.append(player_id)
        save_campaign(campaign)

        waiting = campaign.get_waiting_player_ids()
        if waiting:
            waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
            await self._send_status(
                ctx,
                f"**{char_name}** passes (does nothing this round).\n"
                f"Waiting on: {waiting_mentions}"
            )
        if campaign.all_players_acted():
            await self._resolve_round(ctx, campaign)

    @commands.command(name="afk")
    async def mark_afk(self, ctx: commands.Context):
        """Mark yourself as AFK — auto-pass all future rounds until you return.

        Use !action, !ic, or any gameplay command to remove AFK status.
        Usage: !afk
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_name = char.name if char else ctx.author.display_name

        # Auto-pass for this round if they haven't acted
        if player_id not in campaign.pending_actions and player_id not in campaign.passed_players:
            campaign.passed_players.append(player_id)
            save_campaign(campaign)

        await self._send_status(
            ctx,
            f"**{char_name}** is AFK. They will auto-pass until they submit an action.\n"
            f"Use any gameplay command (`!action`, `!ic`, etc.) to return."
        )

        if campaign.all_players_acted():
            await self._resolve_round(ctx, campaign)

    @commands.command(name="hold")
    async def hold_action(self, ctx: commands.Context):
        """Hold your action — wait to see what happens before acting.

        **In RP:** The round resolves for everyone else first. Then the DM
        describes the scene and you get to act solo based on what happened.

        **In combat:** Tells the DM you're holding your action (standard D&D
        held action rules — declare a trigger and the DM handles it).

        Usage: !hold
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        if not char:
            await ctx.send("You don't have a character.")
            return
        char_name = char.name

        # Combat: send as immediate action for the DM to handle
        if campaign.combat.active:
            await self._dm_respond_immediate(
                ctx, campaign,
                f"[HELD ACTION] {char_name} holds their action, waiting for the right moment. "
                f"Apply standard D&D 5e Ready Action rules — ask the player for their trigger "
                f"and held action if they haven't specified.",
            )
            return

        # RP: already acted or passed this round?
        if player_id in campaign.pending_actions:
            await ctx.send(f"**{char_name}** already submitted an action. Use `!undo` first to change it.")
            return
        if player_id in campaign.passed_players:
            await ctx.send(f"**{char_name}** already passed. Use `!undo` first to change it.")
            return
        if player_id in campaign.held_players:
            await ctx.send(f"**{char_name}** is already holding.")
            return

        campaign.held_players.append(player_id)
        campaign.last_action_time = time.time()
        save_campaign(campaign)

        waiting = campaign.get_waiting_player_ids()
        if waiting:
            waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
            await self._send_status(
                ctx,
                f"**{char_name}** holds their action — they'll act after the scene resolves.\n"
                f"Waiting on: {waiting_mentions}"
            )
        else:
            await self._send_status(
                ctx,
                f"**{char_name}** holds their action — they'll act after the scene resolves."
            )

        if campaign.all_players_acted():
            await self._resolve_round(ctx, campaign)

    @commands.command(name="remind")
    async def remind_players(self, ctx: commands.Context):
        """Ping idle players who haven't acted this round. Anyone can use this.

        Has a 1-hour cooldown per channel to prevent spam.
        Usage: !remind
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        if campaign.combat.active:
            await ctx.send("Combat is active — turns are handled by initiative order.")
            return

        waiting = campaign.get_waiting_player_ids()
        if not waiting:
            await ctx.send("Everyone has already acted this round!")
            return

        # Check cooldown
        channel_id = str(ctx.channel.id)
        now = time.time()
        last_use = self._remind_cooldowns.get(channel_id, 0.0)
        remaining = REMIND_COOLDOWN_SECONDS - (now - last_use)
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            await ctx.send(f"Remind is on cooldown. Try again in **{mins}m {secs}s**.")
            return

        self._remind_cooldowns[channel_id] = now

        waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
        await ctx.send(
            f"**Reminder** — The party is waiting on: {waiting_mentions}\n"
            f"Submit your action (`!action`, `!ic`, `!pass`, etc.) to keep the adventure moving!"
        )

    @commands.command(name="undo")
    async def undo_action(self, ctx: commands.Context):
        """Cancel your pending action before the round resolves.

        Only works during RP queue phase (not in combat).
        Usage: !undo
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        # Combat check
        if campaign.combat.active:
            await ctx.send("You cannot undo actions during combat. Actions are resolved immediately on your turn.")
            return

        player_id = str(ctx.author.id)

        # Check pending actions
        if player_id in campaign.pending_actions:
            del campaign.pending_actions[player_id]
            save_campaign(campaign)
            await self._send_status(
                ctx,
                "Your action has been cancelled.\n"
                "You can now submit a new action with `!action`, `!ic`, `!emote`, or `!pass`."
            )
            return

        # Check passed players
        if player_id in campaign.passed_players:
            campaign.passed_players.remove(player_id)
            save_campaign(campaign)
            await self._send_status(
                ctx,
                "Your pass has been cancelled.\n"
                "You can now submit an action with `!action`, `!ic`, `!emote`, or `!pass`."
            )
            return

        # Check held players (only before the round resolves, not during follow-up)
        if player_id in campaign.held_players:
            campaign.held_players.remove(player_id)
            save_campaign(campaign)
            await self._send_status(
                ctx,
                "Your hold has been cancelled.\n"
                "You can now submit an action with `!action`, `!ic`, `!emote`, or `!pass`."
            )
            return

        await self._send_status(ctx, "You don't have a pending action to undo.")

    @commands.command(name="rewind")
    async def rewind_scene(self, ctx: commands.Context, *, new_prompt: str = ""):
        """DM-only: Undo the last DM response and optionally re-prompt.

        Removes the last assistant+user exchange from conversation history.
        If a new prompt is provided, generates a replacement scene.

        Usage: !rewind
        Usage: !rewind Actually, the NPC survives and runs away
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        if campaign.dm_id != str(ctx.author.id):
            await ctx.send("Only the DM can rewind the scene.")
            return

        if len(campaign.message_history) < 2:
            await ctx.send("No recent scene to rewind.")
            return

        # Remove last assistant response and the user message that prompted it
        if campaign.message_history[-1]["role"] == "assistant":
            campaign.message_history.pop()
        if campaign.message_history and campaign.message_history[-1]["role"] == "user":
            campaign.message_history.pop()

        # Also remove last session log entry
        if campaign.session_log:
            campaign.session_log.pop()

        save_campaign(campaign)

        if new_prompt:
            await ctx.send("**Rewound last scene.** Generating replacement...")
            async with ctx.typing():
                raw_response = await self.bot.dm_engine.get_dm_narration(campaign, new_prompt)

            campaign.add_session_log(f"DM rewind: {new_prompt[:80]}")
            clean_response = await self._process_dm_response(ctx, campaign, raw_response)
            save_campaign(campaign)
            await self._send_long(ctx, clean_response)
        else:
            await ctx.send(
                "**Rewound last scene.** The previous DM response has been erased from history.\n"
                "Continue gameplay normally, or use `!dm <prompt>` to narrate a new scene."
            )

    @commands.command(name="resolve")
    async def resolve(self, ctx: commands.Context):
        """DM forces the round to resolve now, even if not all players have acted.

        Usage: !resolve
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        if campaign.dm_id != str(ctx.author.id):
            await ctx.send("Only the DM can force-resolve a round.")
            return
        if campaign.combat.active:
            await ctx.send("Combat is active — use `!next` to advance turns instead.")
            return
        if not campaign.pending_actions and not campaign.passed_players:
            await ctx.send("No pending actions to resolve.")
            return

        await self._resolve_round(ctx, campaign)

    @commands.command(name="pending")
    async def pending(self, ctx: commands.Context):
        """Show who hasn't acted yet this round.

        Usage: !pending
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        if campaign.combat.active:
            await ctx.send("Combat is active — use `!turnorder` to see turns.")
            return

        waiting = campaign.get_waiting_player_ids()
        acted = list(campaign.pending_actions.keys())
        passed = campaign.passed_players

        lines = ["**Round Status:**"]
        for pid in campaign.get_active_player_ids():
            char = campaign.get_character(pid)
            name = char.name if char else f"<@{pid}>"
            if pid in acted:
                lines.append(f"  **{name}** — Action submitted")
            elif pid in passed:
                lines.append(f"  **{name}** — Passed")
            else:
                lines.append(f"  **{name}** — Waiting...")

        if not waiting:
            lines.append("\nAll players have acted! Resolving...")
        else:
            lines.append(f"\nWaiting on {len(waiting)} player(s). DM can use `!resolve` to force it.")

        await self._send_status(ctx, "\n".join(lines))

    # ------------------------------------------------------------------
    # DM-initiated commands
    # ------------------------------------------------------------------

    @commands.command(name="dm")
    async def dm_narrate(self, ctx: commands.Context, *, prompt: str):
        """DM-only: Prompt Claude to narrate a scene or event without player action.

        Usage: !dm A dragon lands in front of the party
        Usage: !dm Time passes — it is now nightfall
        Usage: !dm The merchant approaches the party with a worried look
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return
        if campaign.dm_id != str(ctx.author.id):
            await ctx.send("Only the DM can use `!dm`.")
            return

        async with ctx.typing():
            raw_response = await self.bot.dm_engine.get_dm_narration(campaign, prompt)

        campaign.add_session_log(f"DM directive: {prompt[:80]}")

        # Process action tags
        clean_response = await self._process_dm_response(ctx, campaign, raw_response)
        save_campaign(campaign)

        await self._send_long(ctx, clean_response)

    @commands.command(name="dm-whisper", aliases=["dmw", "secret"])
    async def dm_whisper(self, ctx: commands.Context, target: discord.Member, *, message: str):
        """DM-only: Send a private message to a specific player via Discord DM.

        Usage: !dm-whisper @Player Your passive Perception notices a hidden door
        Usage: !dmw @Player You recognize the symbol on the wall
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if campaign.dm_id != str(ctx.author.id):
            await ctx.send("Only the DM can send whispers.")
            return

        char = campaign.get_character(str(target.id))
        char_name = char.name if char else target.display_name

        try:
            await target.send(f"**DM whispers to {char_name}:**\n{message}")
            await ctx.message.add_reaction("\u2709\ufe0f")  # envelope
        except discord.Forbidden:
            await ctx.send(f"Cannot send DM to {target.display_name} — they may have DMs disabled.")

    # ------------------------------------------------------------------
    # Non-queued commands (these don't advance story / are immediate)
    # ------------------------------------------------------------------

    @commands.command(name="cleanup")
    async def cleanup_chat(self, ctx: commands.Context, limit: int = 100):
        """Delete bot status/clutter messages from chat, keeping narrative and player content.

        Scans recent messages and removes transient bot messages like
        "locked in", "waiting on", round status, reminders, etc.
        Claude's narrative and player actions/rolls stay.

        Usage: !cleanup
        Usage: !cleanup 200  (scan last 200 messages instead of 100)
        """
        limit = max(10, min(limit, 500))

        # Patterns that identify transient status messages to delete
        status_patterns = [
            "locked in",
            "Waiting on:",
            "A new round begins",
            "auto-passed",
            "AFK Timeout",
            "Everyone passes",
            "passes (does nothing",
            "Round Status:",
            "Reminder —",
            "acts on their held action",
            "holds their action",
            "lets their held action pass",
            "is AFK",
            "has been cancelled",
            "don't have a pending action",
            "Remind is on cooldown",
            "Command help sent to your DMs",
            "No active campaign",
            "Submit your action",
            "the scene has played out",
            "Submit actions when ready",
        ]

        def is_clutter(msg: discord.Message) -> bool:
            # Only delete the bot's own messages
            if msg.author != self.bot.user:
                return False
            # Don't delete the cleanup command response itself
            if msg == status_msg:
                return False
            content = msg.content
            for pattern in status_patterns:
                if pattern in content:
                    return True
            return False

        status_msg = await ctx.send("Cleaning up chat...")

        try:
            deleted = await ctx.channel.purge(limit=limit, check=is_clutter)
            count = len(deleted)
            await status_msg.edit(
                content=f"Cleaned up **{count}** status message{'s' if count != 1 else ''}.",
                delete_after=10,
            )
        except discord.Forbidden:
            await status_msg.edit(
                content="I need **Manage Messages** permission to clean up chat.",
                delete_after=10,
            )
        except discord.HTTPException:
            await status_msg.edit(
                content="Something went wrong during cleanup.",
                delete_after=10,
            )

    @commands.command(name="ooc")
    async def out_of_character(self, ctx: commands.Context, *, message: str):
        """Out-of-character chat. Does NOT count as an action.

        Usage: !ooc brb getting snacks
        """
        await ctx.send(f"**[OOC] {ctx.author.display_name}:** {message}")

    @commands.command(name="introll")
    async def initiative_roll(self, ctx: commands.Context, *, args: str = ""):
        """Roll initiative and report it to the DM immediately (not queued).

        Use this during RP when combat is about to start. Claude sees
        the initiative roll right away and can set up the encounter.

        Usage: !introll
        Usage: !introll adv
        Usage: !introll dis
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        if not char:
            await ctx.send("You don't have a character.")
            return

        _, advantage, disadvantage = parse_adv_dis(args) if args else ("", False, False)

        dex_mod = char.get_modifier("DEX")
        result = roll_initiative(dex_mod, advantage=advantage, disadvantage=disadvantage)
        char_name = char.name
        char_summary = char.short_summary()

        # Show the roll in chat (permanent)
        await ctx.send(f"**{char_name}** rolls initiative: {result['breakdown']}")

        # Send to Claude immediately so the DM knows initiative was rolled
        roll_report = (
            f"[INITIATIVE ROLL] {char_name} rolled initiative: {result['total']} "
            f"(d20{'+' + str(dex_mod) if dex_mod >= 0 else dex_mod}). "
            f"This player is rolling for combat initiative. Note their result for turn order."
        )

        async with ctx.typing():
            raw_response = await self.bot.dm_engine.get_dm_response(
                campaign, roll_report, ctx.author.display_name, char_summary,
            )

        campaign.add_session_log(f"Initiative: {char_name} — {result['total']}")
        clean_response = await self._process_dm_response(ctx, campaign, raw_response)
        save_campaign(campaign)
        await self._send_long(ctx, clean_response)

    @commands.command(name="rollresults", aliases=["rr"])
    async def roll_results(self, ctx: commands.Context, *, args: str = ""):
        """Report a dice roll result to the DM so Claude can react to it.

        This is separate from RP actions — use it when the DM asks you to
        roll a check, save, initiative, or any other roll. Claude sees the
        roll immediately and responds.

        Usage: !rollresults Perception check 14
        Usage: !rollresults Initiative 18
        Usage: !rollresults Dexterity saving throw 7
        Usage: !rr Stealth check nat 20 (total 24)
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign):
            await ctx.send("No active campaign.")
            return

        if not args.strip():
            await self._send_status(ctx,
                "**Usage:** `!rollresults <reason> <result>`\n"
                "Example: `!rollresults Perception check 14`\n"
                "Example: `!rollresults Initiative 18`\n"
                "Alias: `!rr`"
            )
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_name = char.name if char else ctx.author.display_name
        char_summary = char.short_summary() if char else ""

        # Format the roll report for Claude
        roll_report = (
            f"[DICE ROLL RESULT] {char_name} rolled: {args.strip()}\n"
            f"React to this roll result appropriately. If it was a check or save, "
            f"describe whether it succeeds or fails based on the DC. If it was initiative, "
            f"note it for combat order. If it was an attack or damage roll, apply the result."
        )

        # Send as permanent message so the roll is visible in chat
        await ctx.send(f"**{char_name}** rolls: {args.strip()}")

        # Send to Claude immediately (not queued)
        async with ctx.typing():
            raw_response = await self.bot.dm_engine.get_dm_response(
                campaign, roll_report, ctx.author.display_name, char_summary,
            )

        campaign.add_session_log(f"Roll: {char_name} — {args.strip()[:80]}")
        clean_response = await self._process_dm_response(ctx, campaign, raw_response)
        save_campaign(campaign)
        await self._send_long(ctx, clean_response)

    @commands.command(name="ask")
    async def ask_dm(self, ctx: commands.Context, *, question: str):
        """Ask the DM a rules or meta question WITHOUT advancing the story.

        Uses a separate API call that does NOT write to conversation history,
        so rules Q&A never pollutes the story context.

        Usage: !ask Can I use sneak attack with a longbow?
        Usage: !ask What level do paladins get Extra Attack?
        Usage: !ask How does grappling work?
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        player_id = str(ctx.author.id)
        char = campaign.get_character(player_id)
        char_summary = char.short_summary() if char else ""

        async with ctx.typing():
            response = await self.bot.dm_engine.get_rules_response(
                campaign, question, ctx.author.display_name, char_summary,
            )

        await self._send_long(ctx, f"**DM (Rules Q&A):**\n{response}")

    # ------------------------------------------------------------------
    # Dice commands (immediate, never queued)
    # ------------------------------------------------------------------

    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context, *, notation: str):
        """Roll dice using standard notation, with optional advantage/disadvantage.

        Usage: !roll d20
        Usage: !roll 2d6+3
        Usage: !roll d20 adv
        Usage: !roll 1d20+5 dis
        """
        notation, advantage, disadvantage = parse_adv_dis(notation)
        if not notation:
            await ctx.send("Please provide dice notation.\n**Usage:** `!roll <dice>` — e.g. `!roll d20`, `!roll 2d6+3 adv`")
            return

        result = parse_and_roll(notation, advantage=advantage, disadvantage=disadvantage)
        if "error" in result:
            await ctx.send(result["error"])
            return

        await ctx.send(f"**{ctx.author.display_name}** rolls {notation}: {result['breakdown']}")

    @commands.command(name="check")
    async def ability_check(self, ctx: commands.Context, *, ability: str):
        """Make an ability check using your character's modifier.

        Usage: !check perception
        Usage: !check athletics adv
        Usage: !check STR dis
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character. Use `!createchar` first.")
            return

        # Parse advantage/disadvantage
        ability, advantage, disadvantage = parse_adv_dis(ability)
        ability = ability.strip()

        if not ability:
            await ctx.send(
                "Please specify a skill or ability.\n"
                "**Usage:** `!check <skill or ability> [adv|dis]`\n"
                "**Example:** `!check perception` or `!check STR adv`"
            )
            return

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
                                char.proficiency_bonus if skill_match in char.skill_proficiencies else 0,
                                advantage=advantage, disadvantage=disadvantage)
            label = f"{skill_match} check{prof}"
        elif ab_match:
            mod = char.get_modifier(ab_match)
            result = roll_check(mod, advantage=advantage, disadvantage=disadvantage)
            label = f"{ABILITY_FULL_NAMES[ab_match]} check"
        else:
            await ctx.send(suggest_skill(ability))
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
        Usage: !save wisdom adv
        Usage: !save CON dis
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        # Parse advantage/disadvantage
        ability, advantage, disadvantage = parse_adv_dis(ability)
        ability = ability.strip()

        if not ability:
            await ctx.send(
                "Please specify an ability.\n"
                "**Usage:** `!save <ability> [adv|dis]`\n"
                "**Example:** `!save DEX` or `!save wisdom dis`"
            )
            return

        ab_match = None
        for ab in ABILITY_NAMES:
            if ab.lower() == ability.lower() or ABILITY_FULL_NAMES[ab].lower() == ability.lower():
                ab_match = ab
                break
            if ABILITY_FULL_NAMES[ab].lower().startswith(ability.lower()):
                ab_match = ab
                break

        if not ab_match:
            await ctx.send(suggest_ability(ability))
            return

        mod = char.get_modifier(ab_match)
        prof = char.proficiency_bonus if ab_match in char.saving_throw_proficiencies else 0
        result = roll_check(mod, prof, advantage=advantage, disadvantage=disadvantage)
        prof_mark = " (proficient)" if prof else ""

        nat = ""
        if result["natural_20"]:
            nat = " **NAT 20!**"
        elif result["natural_1"]:
            nat = " *Nat 1...*"

        await ctx.send(f"**{char.name}** — {ABILITY_FULL_NAMES[ab_match]} saving throw{prof_mark}: {result['breakdown']}{nat}")

    @commands.command(name="attack")
    async def attack(self, ctx: commands.Context, *, args: str = ""):
        """Make an attack roll with a weapon, including damage.

        Usage: !attack <weapon> (auto-calc from your weapons list)
        Usage: !attack <weapon> <attack_dice> <damage_dice> (manual rolls)
        Usage: !attack <weapon> adv/dis (with advantage/disadvantage)
        Usage: !attack (uses best ability mod, no specific weapon)

        Examples:
          !attack greatsword
          !attack longbow adv
          !attack greatsword 1d20+4 2d6+2
          !attack handaxe 1d20+5 1d6+3 adv
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        if not args.strip():
            await ctx.send(
                "**Usage:** `!attack <weapon> [adv|dis]`\n"
                "**Manual:** `!attack <weapon> <attack_dice> <damage_dice> [adv|dis]`\n"
                "**Examples:**\n"
                "  `!attack greatsword`\n"
                "  `!attack longbow adv`\n"
                "  `!attack greatsword 1d20+4 2d6+2`\n\n"
                "Your weapons: " + (", ".join(w['name'] for w in char.weapons) if char.weapons else "*none — add with character creation*")
            )
            return

        # Parse advantage/disadvantage from the end
        args, advantage, disadvantage = parse_adv_dis(args)
        parts = args.strip().split()

        if not parts:
            # Only adv/dis was provided, no weapon — fall back to generic attack
            return await self._generic_attack(ctx, char, advantage, disadvantage)

        # Check for manual dice notation: <weapon> <attack_dice> <damage_dice>
        # Dice notation matches patterns like 1d20+4, 2d6+2, d8, etc.
        import re
        dice_pattern = r'^\d*d\d+([+-]\d+)?$'
        manual_attack = None
        manual_damage = None

        # Try to identify which parts are dice vs weapon name
        # Work backwards: last two parts might be dice
        if len(parts) >= 3:
            p_last = parts[-1].lower()
            p_second = parts[-2].lower()
            if re.match(dice_pattern, p_last) and re.match(dice_pattern, p_second):
                manual_attack = p_second
                manual_damage = p_last
                parts = parts[:-2]
        elif len(parts) >= 2:
            p_last = parts[-1].lower()
            p_second = parts[-2].lower()
            if re.match(dice_pattern, p_last) and re.match(dice_pattern, p_second):
                manual_attack = p_second
                manual_damage = p_last
                parts = parts[:-2]

        weapon_name = " ".join(parts).strip() if parts else ""

        # If we have manual dice, roll them directly
        if manual_attack and manual_damage:
            atk_result = parse_and_roll(manual_attack, advantage=advantage, disadvantage=disadvantage)
            dmg_result = parse_and_roll(manual_damage)

            if "error" in atk_result:
                await ctx.send(f"Attack dice error: {atk_result['error']}")
                return
            if "error" in dmg_result:
                await ctx.send(f"Damage dice error: {dmg_result['error']}")
                return

            nat = ""
            if atk_result.get("total") and atk_result.get("sides") == 20:
                # Check for nat 20/1 on the chosen roll
                rolls = atk_result.get("rolls", [])
                if advantage or disadvantage:
                    rolls2 = atk_result.get("rolls2", [])
                    all_d20 = [rolls[0], rolls2[0]] if rolls2 else [rolls[0]]
                    chosen = max(all_d20) if advantage else min(all_d20)
                    if chosen == 20:
                        nat = " **CRITICAL HIT!**"
                    elif chosen == 1:
                        nat = " *Critical miss!*"
                else:
                    if rolls and rolls[0] == 20:
                        nat = " **CRITICAL HIT!**"
                    elif rolls and rolls[0] == 1:
                        nat = " *Critical miss!*"

            label = f"**{weapon_name}**" if weapon_name else "Attack"
            await ctx.send(
                f"**{char.name}** attacks with {label}!\n"
                f"  Attack: {atk_result['breakdown']}{nat}\n"
                f"  Damage: {dmg_result['breakdown']}"
            )
            return

        # Auto-calculate from character's weapon list
        if weapon_name and char.weapons:
            # Find the weapon (fuzzy match)
            matched_weapon = None
            weapon_lower = weapon_name.lower()
            for w in char.weapons:
                if w['name'].lower() == weapon_lower:
                    matched_weapon = w
                    break
            if not matched_weapon:
                for w in char.weapons:
                    if weapon_lower in w['name'].lower() or w['name'].lower() in weapon_lower:
                        matched_weapon = w
                        break

            if matched_weapon:
                return await self._weapon_attack(ctx, char, matched_weapon, advantage, disadvantage)
            else:
                weapon_list = ", ".join(f"`{w['name']}`" for w in char.weapons)
                await ctx.send(
                    f"Unknown weapon: `{weapon_name}`\n"
                    f"Your weapons: {weapon_list}\n"
                    f"Or use manual dice: `!attack {weapon_name} 1d20+4 1d8+2`"
                )
                return
        elif weapon_name and not char.weapons:
            # No weapons on sheet but they typed a name — prompt for manual dice
            await ctx.send(
                f"You don't have any weapons on your character sheet.\n"
                f"Use manual dice: `!attack {weapon_name} 1d20+4 1d8+2`\n"
                f"Or add weapons during character creation."
            )
            return

        # No weapon name at all — generic attack with best mod
        await self._generic_attack(ctx, char, advantage, disadvantage)

    async def _weapon_attack(self, ctx, char, weapon: dict, advantage: bool, disadvantage: bool):
        """Roll attack and damage for a specific weapon from the character sheet."""
        is_finesse = weapon.get('finesse', False)
        is_ranged = weapon.get('category') == 'ranged'

        if is_finesse or is_ranged:
            ab_mod = char.get_modifier("DEX")
            ab_used = "DEX"
        else:
            ab_mod = char.get_modifier("STR")
            ab_used = "STR"

        # For finesse weapons, use higher of STR/DEX
        if is_finesse:
            str_mod = char.get_modifier("STR")
            dex_mod = char.get_modifier("DEX")
            if str_mod > dex_mod:
                ab_mod = str_mod
                ab_used = "STR"

        # Attack roll: d20 + ability mod + proficiency
        atk_total_mod = ab_mod + char.proficiency_bonus
        result = roll_check(ab_mod, char.proficiency_bonus,
                            advantage=advantage, disadvantage=disadvantage)

        nat = ""
        is_crit = False
        if result["natural_20"]:
            nat = " **CRITICAL HIT!**"
            is_crit = True
        elif result["natural_1"]:
            nat = " *Critical miss!*"

        # Damage roll from weapon data
        damage_notation = weapon.get('damage', '1d4')
        # Add ability modifier to damage
        if ab_mod >= 0:
            damage_dice = f"{damage_notation}+{ab_mod}"
        elif ab_mod < 0:
            damage_dice = f"{damage_notation}{ab_mod}"

        dmg_result = parse_and_roll(damage_dice)

        if "error" in dmg_result:
            # Fallback: just show attack without damage
            await ctx.send(
                f"**{char.name}** attacks with **{weapon['name']}** ({ab_used})!\n"
                f"  Attack: {result['breakdown']}{nat}"
            )
            return

        # On crit, roll damage dice twice
        crit_text = ""
        if is_crit:
            crit_dmg = parse_and_roll(damage_notation)
            if "error" not in crit_dmg:
                crit_extra = crit_dmg["total"]
                crit_total = dmg_result["total"] + crit_extra
                crit_text = f"\n  Crit bonus: +{crit_extra} = **{crit_total}** total damage"

        props = f" ({', '.join(weapon['properties'])})" if weapon.get('properties') else ""
        dmg_type = weapon.get('damage_type', '')

        await ctx.send(
            f"**{char.name}** attacks with **{weapon['name']}** ({ab_used})!{props}\n"
            f"  Attack: {result['breakdown']}{nat}\n"
            f"  Damage: {dmg_result['breakdown']} {dmg_type}{crit_text}"
        )

    async def _generic_attack(self, ctx, char, advantage: bool, disadvantage: bool):
        """Fall back: generic attack roll with best ability mod."""
        str_mod = char.get_modifier("STR")
        dex_mod = char.get_modifier("DEX")
        if char.char_class in ("Rogue", "Monk", "Ranger") or dex_mod > str_mod:
            attack_mod = dex_mod
            ab_used = "DEX"
        else:
            attack_mod = str_mod
            ab_used = "STR"

        result = roll_check(attack_mod, char.proficiency_bonus,
                            advantage=advantage, disadvantage=disadvantage)

        nat = ""
        if result["natural_20"]:
            nat = " **CRITICAL HIT!**"
        elif result["natural_1"]:
            nat = " *Critical miss!*"

        weapon_hint = ""
        if char.weapons:
            weapon_list = ", ".join(f"`{w['name']}`" for w in char.weapons)
            weapon_hint = f"\nTip: `!attack <weapon>` for attack + damage — your weapons: {weapon_list}"

        await ctx.send(
            f"**{char.name}** — Attack roll ({ab_used}): {result['breakdown']}{nat}{weapon_hint}"
        )

    @commands.command(name="spellattack", aliases=["sa", "spellatk"])
    async def spell_attack(self, ctx: commands.Context, *, args: str = ""):
        """Roll a spell attack and/or spell damage.

        Usage: !spellattack <spell> <damage_dice> (auto spell attack + your damage)
        Usage: !spellattack <spell> <attack_dice> <damage_dice> (manual rolls)
        Usage: !spellattack <spell> (spell attack roll only, no damage)
        Usage: !spellattack <spell> ... adv/dis (with advantage/disadvantage)

        Examples:
          !spellattack Fire Bolt 1d10
          !spellattack Guiding Bolt 4d6
          !spellattack Eldritch Blast 1d20+5 1d10+3
          !spellattack Scorching Ray 1d20+5 2d6 adv
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        if not args.strip():
            spell_atk_str = ""
            if char.spellcasting_ability:
                spell_mod = char.get_modifier(char.spellcasting_ability)
                spell_atk = char.proficiency_bonus + spell_mod
                spell_save = 8 + char.proficiency_bonus + spell_mod
                atk_str = f"+{spell_atk}" if spell_atk >= 0 else str(spell_atk)
                spell_atk_str = f"\nYour spell attack: **{atk_str}** | Spell Save DC: **{spell_save}**"

            await ctx.send(
                "**Usage:** `!spellattack <spell> <damage_dice> [adv|dis]`\n"
                "**Manual:** `!spellattack <spell> <attack_dice> <damage_dice> [adv|dis]`\n"
                "**Examples:**\n"
                "  `!spellattack Fire Bolt 1d10`\n"
                "  `!spellattack Guiding Bolt 4d6 adv`\n"
                "  `!spellattack Eldritch Blast 1d20+5 1d10+3`"
                f"{spell_atk_str}"
            )
            return

        # Parse advantage/disadvantage
        args, advantage, disadvantage = parse_adv_dis(args)
        parts = args.strip().split()

        if not parts:
            await ctx.send("Please specify a spell name.")
            return

        import re
        dice_pattern = r'^\d*d\d+([+-]\d+)?$'

        # Find dice from the end of parts
        dice_parts = []
        name_parts = list(parts)
        while name_parts and re.match(dice_pattern, name_parts[-1].lower()):
            dice_parts.insert(0, name_parts.pop())

        spell_name = " ".join(name_parts).strip() if name_parts else "Spell"

        # Calculate spell attack modifier
        if char.spellcasting_ability:
            spell_mod = char.get_modifier(char.spellcasting_ability)
            spell_atk_mod = char.proficiency_bonus + spell_mod
            ab_used = char.spellcasting_ability
        else:
            spell_atk_mod = 0
            ab_used = "none"

        if len(dice_parts) == 0:
            # Just spell attack roll, no damage
            result = roll_check(spell_mod if char.spellcasting_ability else 0,
                                char.proficiency_bonus if char.spellcasting_ability else 0,
                                advantage=advantage, disadvantage=disadvantage)

            nat = ""
            if result["natural_20"]:
                nat = " **CRITICAL HIT!**"
            elif result["natural_1"]:
                nat = " *Critical miss!*"

            await ctx.send(
                f"**{char.name}** casts **{spell_name}**!\n"
                f"  Spell Attack ({ab_used}): {result['breakdown']}{nat}"
            )

        elif len(dice_parts) == 1:
            # One dice = damage; auto-calc spell attack
            damage_dice = dice_parts[0]

            result = roll_check(spell_mod if char.spellcasting_ability else 0,
                                char.proficiency_bonus if char.spellcasting_ability else 0,
                                advantage=advantage, disadvantage=disadvantage)

            nat = ""
            is_crit = False
            if result["natural_20"]:
                nat = " **CRITICAL HIT!**"
                is_crit = True
            elif result["natural_1"]:
                nat = " *Critical miss!*"

            dmg_result = parse_and_roll(damage_dice)
            if "error" in dmg_result:
                await ctx.send(f"Damage dice error: {dmg_result['error']}")
                return

            crit_text = ""
            if is_crit:
                crit_extra = parse_and_roll(damage_dice)
                if "error" not in crit_extra:
                    crit_total = dmg_result["total"] + crit_extra["total"]
                    crit_text = f"\n  Crit bonus: +{crit_extra['total']} = **{crit_total}** total damage"

            await ctx.send(
                f"**{char.name}** casts **{spell_name}**!\n"
                f"  Spell Attack ({ab_used}): {result['breakdown']}{nat}\n"
                f"  Damage: {dmg_result['breakdown']}{crit_text}"
            )

        elif len(dice_parts) >= 2:
            # Two dice = manual attack + damage
            attack_dice = dice_parts[0]
            damage_dice = dice_parts[1]

            atk_result = parse_and_roll(attack_dice, advantage=advantage, disadvantage=disadvantage)
            dmg_result = parse_and_roll(damage_dice)

            if "error" in atk_result:
                await ctx.send(f"Attack dice error: {atk_result['error']}")
                return
            if "error" in dmg_result:
                await ctx.send(f"Damage dice error: {dmg_result['error']}")
                return

            nat = ""
            if atk_result.get("sides") == 20:
                rolls = atk_result.get("rolls", [])
                if advantage or disadvantage:
                    rolls2 = atk_result.get("rolls2", [])
                    all_d20 = [rolls[0], rolls2[0]] if rolls2 else [rolls[0]]
                    chosen = max(all_d20) if advantage else min(all_d20)
                    if chosen == 20:
                        nat = " **CRITICAL HIT!**"
                    elif chosen == 1:
                        nat = " *Critical miss!*"
                else:
                    if rolls and rolls[0] == 20:
                        nat = " **CRITICAL HIT!**"
                    elif rolls and rolls[0] == 1:
                        nat = " *Critical miss!*"

            await ctx.send(
                f"**{char.name}** casts **{spell_name}**!\n"
                f"  Spell Attack: {atk_result['breakdown']}{nat}\n"
                f"  Damage: {dmg_result['breakdown']}"
            )


    # ------------------------------------------------------------------
    # WoD-specific commands
    # ------------------------------------------------------------------

    @commands.command(name="pool", aliases=["dicepool", "dp"])
    async def wod_pool(self, ctx: commands.Context, *, args: str = ""):
        """Roll a World of Darkness dice pool (d10s, 8+ = success).

        Usage: !pool 6           (roll 6 dice)
        Usage: !pool 4 9again    (roll 4 dice with 9-again)
        Usage: !pool 3 rote      (rote action — reroll failures)
        Usage: !pool 0           (chance die)

        Successes on 8, 9, 10. Tens explode (10-again by default).
        5+ successes = Exceptional Success.
        """
        if not args:
            await ctx.send(
                "**Usage:** `!pool <number of dice> [9again|8again|noagain] [rote]`\n"
                "Example: `!pool 6`, `!pool 4 9again`, `!pool 0` (chance die)"
            )
            return

        args, again, rote = parse_pool_args(args)

        try:
            pool_size = int(args.strip())
        except ValueError:
            await ctx.send("Provide a number of dice to roll. Example: `!pool 6`")
            return

        result = roll_pool(pool_size, again=again, rote=rote)
        await ctx.send(f"**{ctx.author.display_name}** — {result['breakdown']}")

    @commands.command(name="wodroll", aliases=["wr"])
    async def wod_roll(self, ctx: commands.Context, *, args: str = ""):
        """Roll Attribute + Skill as a WoD dice pool using your character.

        Usage: !wodroll Strength + Brawl
        Usage: !wodroll Wits + Investigation
        Usage: !wodroll Dexterity + Firearms 9again

        The bot calculates your dice pool from your character sheet.
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.game_system != GameSystem.WOD:
            await ctx.send("This command is for World of Darkness campaigns.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        args, again, rote = parse_pool_args(args)

        # Parse "Attribute + Skill" or "Attribute + Skill + modifier"
        parts = [p.strip() for p in args.replace("+", " + ").split("+")]
        parts = [p.strip() for p in parts if p.strip()]

        pool_size = 0
        labels = []

        from bot.models.wod_character import WOD_ALL_ATTRIBUTES, WOD_ALL_SKILLS

        for part in parts:
            # Try as number modifier
            try:
                mod = int(part)
                pool_size += mod
                labels.append(str(mod))
                continue
            except ValueError:
                pass

            # Try as attribute
            matched = False
            for attr in WOD_ALL_ATTRIBUTES:
                if attr.lower() == part.lower() or attr.lower().startswith(part.lower()):
                    pool_size += char.attributes.get(attr, 1)
                    labels.append(f"{attr} ({char.attributes.get(attr, 1)})")
                    matched = True
                    break

            if matched:
                continue

            # Try as skill
            for skill in WOD_ALL_SKILLS:
                if skill.lower() == part.lower() or skill.lower().startswith(part.lower()) or part.lower() in skill.lower():
                    pool_size += char.skills.get(skill, 0)
                    labels.append(f"{skill} ({char.skills.get(skill, 0)})")
                    matched = True
                    break

            if not matched:
                await ctx.send(f"Unknown attribute/skill: **{part}**")
                return

        label_str = " + ".join(labels)
        result = roll_pool(pool_size, again=again, rote=rote)
        await ctx.send(f"**{char.name}** — {label_str} = {pool_size} dice\n{result['breakdown']}")

    @commands.command(name="wodintroll", aliases=["wir"])
    async def wod_initiative_roll(self, ctx: commands.Context, *, args: str = ""):
        """Roll WoD initiative (Dexterity + Composure + d10) during RP.

        Reports the roll to Claude immediately (not queued).

        Usage: !wodintroll
        Usage: !wodintroll +2 (with modifier)
        """
        campaign = self._get_campaign(ctx)
        if not self._require_active(campaign) or campaign.game_system != GameSystem.WOD:
            await ctx.send("This command is for active World of Darkness campaigns.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        # Parse optional modifier
        modifier = 0
        if args.strip():
            try:
                modifier = int(args.strip().replace("+", ""))
            except ValueError:
                pass

        dex = char.attributes.get("Dexterity", 1)
        composure = char.attributes.get("Composure", 1)
        result = roll_initiative_wod(dex, composure, modifier)

        await ctx.send(
            f"**{char.name}** rolls initiative!\n"
            f"  {result['breakdown']}"
        )

        # Report to Claude immediately
        init_context = (
            f"[INITIATIVE ROLL] {char.name} rolled initiative: {result['total']} "
            f"(Dex {dex} + Composure {composure} + d10={result['roll']})"
        )
        async with ctx.typing():
            dm_response = await self.bot.dm_engine.get_dm_response(
                campaign, init_context, char.name, char.short_summary(),
                extra_context="This is an initiative roll for upcoming combat."
            )

        clean_text, log_entries, combat_events = parse_action_tags(dm_response, campaign)
        clean_text, whispers = extract_whispers(clean_text)
        save_campaign(campaign)

        if clean_text:
            await self._send_long(ctx, clean_text)

        for target_name, message in whispers:
            player_id = campaign.get_player_id_by_char_name(target_name)
            if player_id:
                try:
                    user = await self.bot.fetch_user(int(player_id))
                    await user.send(f"*[DM whispers to {target_name}]*\n{message}")
                except Exception:
                    pass

        if combat_events:
            await self._handle_combat_events(ctx, campaign, combat_events)


async def setup(bot: commands.Bot):
    await bot.add_cog(GameplayCog(bot))

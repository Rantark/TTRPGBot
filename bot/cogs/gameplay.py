"""Gameplay commands: action, IC, emote, OOC, look, inspect, talk, ask, roll, check, save, attack.

RP scene coordination: During non-combat RP, player actions are queued.
Once every active player has submitted an action (or used !pass), all
actions are bundled and sent to Claude as a single prompt so the DM can
respond to everyone at once without overlapping storylines.
"""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.data.rules import ABILITY_NAMES, ABILITY_FULL_NAMES, SKILLS, modifier_str
from bot.dice import parse_and_roll, roll_check, parse_adv_dis
from bot.dm_engine import parse_action_tags, extract_whispers
from bot.storage import load_campaign, save_campaign
from bot.utils.fuzzy_match import suggest_skill, suggest_ability


class GameplayCog(commands.Cog, name="Gameplay"):
    """In-game commands for playing D&D."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        # Queue the action
        campaign.pending_actions[player_id] = action_text
        save_campaign(campaign)

        # Tell the channel this player has acted
        waiting = campaign.get_waiting_player_ids()
        if waiting:
            waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
            await ctx.send(
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
            await ctx.send("*Everyone passes. The scene continues...*\nSubmit actions when ready.")
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
        await ctx.send("*A new round begins.* Submit your actions!")

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
        # Parse and execute action tags (DAMAGE, CONDITION, NPC_DEFEAT, SPELL_SLOT)
        clean_text, log_entries = parse_action_tags(raw_response, campaign)

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

        # Save if anything changed
        if log_entries or whispers:
            save_campaign(campaign)

        return clean_text

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

        # RP pass
        if player_id not in campaign.passed_players:
            campaign.passed_players.append(player_id)
        save_campaign(campaign)

        waiting = campaign.get_waiting_player_ids()
        if waiting:
            waiting_mentions = ", ".join(f"<@{pid}>" for pid in waiting)
            await ctx.send(
                f"**{char_name}** passes (does nothing this round).\n"
                f"Waiting on: {waiting_mentions}"
            )
        if campaign.all_players_acted():
            await self._resolve_round(ctx, campaign)

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
            await ctx.send(
                "Your action has been cancelled.\n"
                "You can now submit a new action with `!action`, `!ic`, `!emote`, or `!pass`."
            )
            return

        # Check passed players
        if player_id in campaign.passed_players:
            campaign.passed_players.remove(player_id)
            save_campaign(campaign)
            await ctx.send(
                "Your pass has been cancelled.\n"
                "You can now submit an action with `!action`, `!ic`, `!emote`, or `!pass`."
            )
            return

        await ctx.send("You don't have a pending action to undo.")

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

        await ctx.send("\n".join(lines))

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

    @commands.command(name="ooc")
    async def out_of_character(self, ctx: commands.Context, *, message: str):
        """Out-of-character chat. Does NOT count as an action.

        Usage: !ooc brb getting snacks
        """
        await ctx.send(f"**[OOC] {ctx.author.display_name}:** {message}")

    @commands.command(name="ask")
    async def ask_dm(self, ctx: commands.Context, *, question: str):
        """Ask the DM a rules or meta question WITHOUT advancing the story.

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
            response = await self.bot.dm_engine.get_dm_response(
                campaign,
                f"[OUT-OF-CHARACTER QUESTION — Do NOT advance the story, do NOT narrate anything. "
                f"Just answer this rules/meta question clearly.]\n{question}",
                ctx.author.display_name,
                char_summary,
                "This is a rules question, not an in-game action. Answer it helpfully "
                "without progressing the narrative or describing any in-game events.",
            )

        # Don't log to session log — this isn't story progression
        save_campaign(campaign)

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


async def setup(bot: commands.Bot):
    await bot.add_cog(GameplayCog(bot))

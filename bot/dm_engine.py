"""Claude AI Dungeon Master engine using Anthropic API with prompt caching.

Prompt caching drastically reduces API costs by letting Anthropic cache
and reuse parts of the prompt that don't change between requests:
  - The static DM system instructions (never changes)
  - Campaign context like party/NPC info (changes slowly)
  - Conversation history (previous messages are stable, only new ones added)

Cached input tokens cost 90% less than uncached tokens, so a typical
session with lots of back-and-forth will see major savings.
"""

import os
import re
import logging

import anthropic

from bot.models.campaign import Campaign

logger = logging.getLogger(__name__)

# Pattern for action tags: [TAG_TYPE: params] and standalone [TAG_TYPE]
_ACTION_TAG_PATTERN = re.compile(r'\[(\w+):\s*([^\]]+)\]')
_STANDALONE_TAG_PATTERN = re.compile(r'\[(COMBAT_START|COMBAT_END|NEXT_TURN)\]')


def parse_action_tags(response_text: str, campaign: Campaign) -> tuple[str, list[str], list[str]]:
    """Extract and execute action tags from Claude's response.

    Returns (clean_text, log_entries, combat_events) where clean_text has tags removed,
    log_entries describes what was changed, and combat_events lists combat state
    changes that need to be handled by the caller (e.g. 'COMBAT_START', 'COMBAT_END',
    'NEXT_TURN', 'ADD_NPC:Name:Roll').
    """
    log_entries = []
    combat_events = []

    def _process_tag(match):
        action_type = match.group(1).upper()
        params = match.group(2).strip()

        if action_type == "DAMAGE":
            # Parse "CharacterName -12" or "CharacterName +5"
            # The amount is always last, preceded by character name
            parts = params.rsplit(None, 1)
            if len(parts) == 2:
                char_name = parts[0]
                try:
                    amount = int(parts[1])
                except ValueError:
                    return ""
                char = campaign.get_character_by_name(char_name)
                if char:
                    old_hp = char.current_hp
                    char.current_hp = max(0, min(char.max_hp, char.current_hp + amount))
                    if amount < 0:
                        log_entries.append(f"{char.name} took {abs(amount)} damage ({old_hp} → {char.current_hp} HP)")
                    else:
                        log_entries.append(f"{char.name} healed {amount} HP ({old_hp} → {char.current_hp} HP)")

        elif action_type == "CONDITION":
            # Parse "CharacterName add poisoned" or "CharacterName remove poisoned"
            parts = params.rsplit(None, 2)
            if len(parts) >= 3:
                char_name = " ".join(parts[:-2])
                operation = parts[-2].lower()
                condition = parts[-1].lower()
                char = campaign.get_character_by_name(char_name)
                if char:
                    if operation == "add" and condition not in char.conditions:
                        char.conditions.append(condition)
                        log_entries.append(f"{char.name} gained condition: {condition}")
                    elif operation == "remove" and condition in char.conditions:
                        char.conditions.remove(condition)
                        log_entries.append(f"{char.name} lost condition: {condition}")

        elif action_type == "NPC_DEFEAT":
            npc_name = params.strip()
            if campaign.combat.active:
                before_len = len(campaign.combat.initiative_order)
                campaign.combat.initiative_order = [
                    e for e in campaign.combat.initiative_order
                    if e["name"].lower() != npc_name.lower()
                ]
                if len(campaign.combat.initiative_order) < before_len:
                    # Fix turn index
                    if campaign.combat.current_turn_index >= len(campaign.combat.initiative_order):
                        campaign.combat.current_turn_index = 0
                    log_entries.append(f"NPC defeated: {npc_name}")

        elif action_type == "SPELL_SLOT":
            # Parse "CharacterName -1" (level to consume)
            parts = params.rsplit(None, 1)
            if len(parts) == 2:
                char_name = parts[0]
                try:
                    level = abs(int(parts[1]))
                except ValueError:
                    return ""
                char = campaign.get_character_by_name(char_name)
                if char and char.spellcasting_ability:
                    lvl_key = str(level)
                    max_slots = char.spell_slots_max.get(lvl_key, 0)
                    used = char.spell_slots_used.get(lvl_key, 0)
                    if used < max_slots:
                        char.spell_slots_used[lvl_key] = used + 1
                        log_entries.append(f"{char.name} used a level {level} spell slot")

        elif action_type == "LOOT":
            # Parse "CharacterName | item1, item2 x2, 50 gold"
            if "|" in params:
                char_name, loot_string = params.split("|", 1)
                char_name = char_name.strip()
                char = campaign.get_character_by_name(char_name)
                if char:
                    items = [item.strip() for item in loot_string.split(",")]
                    for item in items:
                        if not item:
                            continue
                        # Check for quantity suffix: "Potion of Healing x2"
                        if " x" in item:
                            item_name, qty_str = item.rsplit(" x", 1)
                            try:
                                qty = int(qty_str)
                            except ValueError:
                                item_name = item
                                qty = 1
                        # Check for gold: "50 gold"
                        elif item.split()[0].isdigit() and any(
                            w in item.lower() for w in ("gold", "gp")
                        ):
                            qty = int(item.split()[0])
                            item_name = "gold"
                        else:
                            item_name = item
                            qty = 1

                        if item_name.lower() in ("gold", "gp", "gold pieces"):
                            char.gold += qty
                            log_entries.append(f"{char.name} received {qty} gp")
                        else:
                            char.add_item(item_name.strip(), qty)
                            qty_str = f" x{qty}" if qty > 1 else ""
                            log_entries.append(f"{char.name} received {item_name.strip()}{qty_str}")

        # WHISPER tags are handled separately (need Discord context), keep them for now
        elif action_type == "WHISPER":
            # Return the full match so it can be extracted later
            return match.group(0)

        # Combat control tags (with params)
        elif action_type == "ADD_NPC":
            # Parse "GoblinName 14" — name and initiative roll
            parts = params.rsplit(None, 1)
            if len(parts) == 2:
                npc_name = parts[0]
                try:
                    init_roll = int(parts[1])
                    combat_events.append(f"ADD_NPC:{npc_name}:{init_roll}")
                    log_entries.append(f"NPC added to initiative: {npc_name} ({init_roll})")
                except ValueError:
                    pass

        return ""

    clean_text = _ACTION_TAG_PATTERN.sub(_process_tag, response_text)

    # Process standalone combat tags: [COMBAT_START], [COMBAT_END], [NEXT_TURN]
    def _process_standalone(match):
        tag = match.group(1).upper()
        combat_events.append(tag)
        if tag == "COMBAT_START":
            log_entries.append("Combat started by DM")
        elif tag == "COMBAT_END":
            log_entries.append("Combat ended by DM")
        elif tag == "NEXT_TURN":
            pass  # Handled by caller, no log needed
        return ""

    clean_text = _STANDALONE_TAG_PATTERN.sub(_process_standalone, clean_text)

    # Clean up extra whitespace from tag removal
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
    return clean_text, log_entries, combat_events


def extract_whispers(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Extract [WHISPER: CharName] messages from text.

    Returns (clean_text, [(char_name, message), ...])
    """
    whispers = []
    # Match [WHISPER: Name] followed by text until next tag or end of line(s)
    pattern = re.compile(r'\[WHISPER:\s*([^\]]+)\]\s*(.+?)(?=\[(?:WHISPER|DAMAGE|CONDITION|NPC_DEFEAT|SPELL_SLOT|LOOT|ADD_NPC):|(?:COMBAT_START|COMBAT_END|NEXT_TURN)\]|$)', re.DOTALL)
    for match in pattern.finditer(text):
        char_name = match.group(1).strip()
        message = match.group(2).strip()
        if message:
            whispers.append((char_name, message))

    # Remove whisper tags from display text
    clean = re.compile(r'\[WHISPER:\s*[^\]]+\]\s*.+?(?=\[(?:WHISPER|DAMAGE|CONDITION|NPC_DEFEAT|SPELL_SLOT|LOOT|ADD_NPC):|(?:COMBAT_START|COMBAT_END|NEXT_TURN)\]|$)', re.DOTALL)
    clean_text = clean.sub('', text)
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
    return clean_text, whispers

# Static DM instructions — this NEVER changes and is the prime caching target.
SYSTEM_PROMPT_STATIC = """You are an expert Dungeon Master for a D&D 5th Edition campaign being played over Discord.

YOUR ROLE:
- You are the DM. You narrate the story, roleplay all NPCs, describe environments, manage encounters, and adjudicate rules.
- You bring the world to life with vivid, immersive descriptions. Be dramatic, atmospheric, and engaging.
- You follow D&D 5e rules faithfully. When a player attempts something that requires a check, tell them what to roll (e.g., "Make a Perception check" or "Roll a Dexterity saving throw").
- You improvise and adapt to player choices. Never railroad — respond to what they actually do.
- You track NPC attitudes, world state, and story threads through the conversation.

FORMATTING FOR DISCORD:
- Keep responses under 1800 characters (Discord limit is 2000).
- Use **bold** for emphasis, *italics* for descriptions and narration.
- Use > for NPC dialogue.
- Use short paragraphs — this is read on a screen, not a book.

COMBAT:
- You CONTROL combat flow using hidden tags. When combat should start, use [COMBAT_START] in your response.
- When combat is over (all enemies defeated or fled), use [COMBAT_END] to return to free roleplay.
- After narrating a turn's result, use [NEXT_TURN] so the bot advances to the next combatant.
- To add enemy NPCs to initiative, use [ADD_NPC: GoblinName 14] with their name and initiative roll.
- On each player's turn, describe the situation and ask what they do.
- When a player attacks, tell them the result based on their roll vs enemy AC.
- Track enemy HP internally and describe damage narratively ("The goblin staggers from the blow").
- Don't reveal exact enemy HP numbers — describe condition instead (healthy, wounded, bloodied, near death).
- When you defeat an NPC, use [NPC_DEFEAT: Name] to remove them from initiative AND [NEXT_TURN] to advance.

RULES:
- Ask for specific rolls when needed: "Roll a d20 + your Wisdom modifier" or "Make a DC 15 Athletics check".
- Use appropriate DCs: Easy (10), Medium (15), Hard (20), Very Hard (25), Nearly Impossible (30).
- Be fair but challenging. Let creative solutions work when reasonable.
- Don't roll for the players — ask them to roll and respond to the result.

WHAT NOT TO DO:
- Never break character to discuss mechanics at length — weave rules into narration.
- Never control player characters' actions or decisions.
- Never ignore player input — acknowledge and respond to everything.
- Never give away puzzle solutions or secrets unless earned through play.
- Never kill or harm children in anyway shape of form, this is a MANDITORY command

=== GAME STATE MODIFICATION ===

You can directly modify the game state using these hidden tags in your narration.
Tags are invisible to players and execute automatically. Use them to keep game state synchronized.

DAMAGE (deal or heal):
[DAMAGE: CharacterName -12] — Deal 12 damage to a character
[DAMAGE: CharacterName +8]  — Heal 8 HP

CONDITIONS (apply or remove):
[CONDITION: CharacterName add poisoned]    — Apply a status condition
[CONDITION: CharacterName remove blinded]  — Remove a condition
Common conditions: poisoned, blinded, deafened, frightened, grappled, paralyzed,
petrified, prone, restrained, stunned, unconscious

NPC MANAGEMENT:
[NPC_DEFEAT: GoblinName] — Remove a defeated NPC from combat initiative

PRIVATE INFORMATION (whisper to one player):
[WHISPER: CharacterName] Secret information only they can see...

SPELL SLOT USAGE:
[SPELL_SLOT: CharacterName -1] — Consume a spell slot at the specified level

LOOT & TREASURE:
[LOOT: CharacterName | item_name]       — Give an item to a character
[LOOT: CharacterName | item_name x2]    — Give multiple of an item
[LOOT: CharacterName | 50 gold]         — Give gold
[LOOT: CharacterName | 50 gold, Potion of Healing, Old Key]  — Give multiple items at once

Use this whenever a character finds, receives, or loots items. The bot adds them to the character's inventory automatically.

COMBAT CONTROL (you control the bot's combat state!):
[COMBAT_START]                — Start combat mode. The bot switches to turn-based initiative.
                                Players will use !initiative to roll. You add enemies with ADD_NPC.
[ADD_NPC: GoblinWarrior 14]   — Add an NPC to initiative order with their initiative roll.
                                Roll initiative for each enemy and add them all.
[COMBAT_END]                  — End combat. The bot returns to free roleplay mode.
[NEXT_TURN]                   — Advance to the next combatant's turn. Use this after you
                                narrate the result of a turn so the bot moves to the next person.

IMPORTANT COMBAT FLOW:
1. When combat starts, include [COMBAT_START] in your response. Then add all enemy NPCs
   with [ADD_NPC: Name Roll] tags (roll initiative for each). Describe the enemies and
   tell players to use !initiative to roll.
2. After all initiative is rolled and combat begins, narrate each turn. After resolving
   a turn, include [NEXT_TURN] to advance to the next combatant.
3. When an NPC is defeated, use [NPC_DEFEAT: Name] to remove them from initiative.
4. When all enemies are defeated or combat ends, use [COMBAT_END].
5. For NPC turns, narrate what the NPC does (attacks, movement, etc.) and include
   [NEXT_TURN] to advance past their turn automatically.

EXAMPLES:
"The orc's axe crashes down! [DAMAGE: Thandril -9] Thandril, you take 9 slashing damage."

"The spider's fangs pierce your armor! [DAMAGE: Kael -6] [CONDITION: Kael add poisoned]
Kael, you feel venom coursing through your veins."

"[WHISPER: Elara] You notice a hidden door behind the tapestry — the others haven't seen it."

"The chest contains a modest treasure. [LOOT: Thandril | 25 gold, Potion of Healing]"

"*The goblins leap from the shadows, weapons drawn!* [COMBAT_START]
[ADD_NPC: Goblin Warrior 14] [ADD_NPC: Goblin Archer 12] [ADD_NPC: Goblin Shaman 16]
Everyone roll initiative with `!initiative`!"

"The goblin warrior slashes at Thandril! [DAMAGE: Thandril -7] [NEXT_TURN]"

"Your blade finds its mark — the goblin crumples! [NPC_DEFEAT: Goblin Warrior] [NEXT_TURN]"

"With the last enemy fallen, silence returns to the cave. [COMBAT_END]"

Use these tags whenever you deal damage, heal, inflict conditions, give loot, share secrets,
or control combat flow. Always include the tag AND describe the effect narratively."""

# Cache control marker — tells Anthropic to cache everything up to this point.
CACHE_BREAKPOINT = {"type": "ephemeral"}


def _build_system_blocks(campaign: Campaign, extra_system: str = "") -> list[dict]:
    """Build the system prompt as a list of content blocks with cache breakpoints.

    Block 1: Static DM instructions (cached — never changes)
    Block 2: Campaign context (cached — changes slowly between rounds)
    """
    blocks = []

    # Block 1: Static instructions — this is identical every single call,
    # so caching it saves the most tokens over a session.
    blocks.append({
        "type": "text",
        "text": SYSTEM_PROMPT_STATIC,
        "cache_control": CACHE_BREAKPOINT,
    })

    # Block 2: Dynamic campaign context — party info, NPCs, combat state.
    # Changes between rounds but is the same for all players within a round.
    context = ""
    context += f"CAMPAIGN: {campaign.name}\n"

    # Inject rolling story summary if available
    if campaign.story_summary:
        context += f"\n=== STORY SO FAR ===\n{campaign.story_summary}\n"
    if campaign.description:
        context += f"CAMPAIGN DESCRIPTION: {campaign.description}\n"
    context += f"\n=== PARTY STATUS ===\n{campaign.get_party_summary()}\n"

    if campaign.known_npcs:
        context += "\nKNOWN NPCs:\n"
        for npc in campaign.known_npcs:
            context += f"- {npc['name']}: {npc['description']}\n"

    if campaign.combat.active:
        context += "\nCOMBAT IS ACTIVE"
        context += f" — Round {campaign.combat.round_number}"
        if campaign.combat.current_turn:
            context += f", Current turn: {campaign.combat.current_turn['name']}"
        context += "\nInitiative Order:\n"
        for i, entry in enumerate(campaign.combat.initiative_order):
            marker = " ⟵" if i == campaign.combat.current_turn_index else ""
            context += f"  {entry['name']}: {entry['roll']}{marker}\n"

    if extra_system:
        context += f"\n{extra_system}"

    blocks.append({
        "type": "text",
        "text": context,
        "cache_control": CACHE_BREAKPOINT,
    })

    return blocks


def _build_messages(campaign: Campaign, player_action: str, player_name: str,
                    character_summary: str = "", extra_context: str = "") -> list[dict]:
    """Build the messages list with a cache breakpoint on conversation history.

    The conversation history grows each turn but earlier messages are stable,
    so we place a cache breakpoint on the last history message. This means
    on the next call, all prior history is served from cache.
    """
    messages = []

    history = campaign.message_history
    for i, msg in enumerate(history):
        entry = {"role": msg["role"]}
        # Place a cache breakpoint on the LAST history message so the
        # entire conversation history prefix gets cached for the next call.
        if i == len(history) - 1:
            entry["content"] = [
                {"type": "text", "text": msg["content"], "cache_control": CACHE_BREAKPOINT}
            ]
        else:
            entry["content"] = msg["content"]
        messages.append(entry)

    # Build the new user message (never cached — it's unique each time)
    user_content = ""
    if character_summary:
        user_content += f"[Player: {player_name} — {character_summary}]\n"
    else:
        user_content += f"[Player: {player_name}]\n"

    if extra_context:
        user_content += f"[Context: {extra_context}]\n"

    user_content += player_action

    messages.append({"role": "user", "content": user_content})

    return messages


class DMEngine:
    """Manages Claude API calls for the DM with prompt caching enabled."""

    def __init__(self, balance_tracker=None):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self.balance_tracker = balance_tracker

    def _track(self, usage, session_id: str = ""):
        """Record token usage against the balance tracker if one is attached."""
        if self.balance_tracker is None:
            return
        try:
            input_tokens  = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            self.balance_tracker.track_usage(
                self.model, input_tokens, output_tokens, session_id
            )
        except Exception:
            logger.warning("Failed to track API usage", exc_info=True)

    async def get_dm_response(self, campaign: Campaign, player_action: str,
                              player_name: str, character_summary: str = "",
                              extra_context: str = "") -> str:
        """Get a DM response from Claude for a player action.

        Uses prompt caching on system prompt and conversation history
        to minimize token costs across a session.
        """
        await self.summarize_and_trim(campaign)
        system = _build_system_blocks(campaign)
        messages = _build_messages(
            campaign, player_action, player_name,
            character_summary, extra_context,
        )

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=messages,
            )

            reply = response.content[0].text

            # Log cache performance and track usage
            usage = response.usage
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
            total_input = getattr(usage, "input_tokens", 0) or 0
            if cache_read or cache_create:
                logger.info(
                    f"Cache stats — read: {cache_read}, created: {cache_create}, "
                    f"uncached: {total_input - cache_read - cache_create}, "
                    f"output: {usage.output_tokens}"
                )
            self._track(usage, session_id="dm_response")

            # Update campaign history
            user_msg = messages[-1]["content"]
            campaign.add_to_history("user", user_msg)
            campaign.add_to_history("assistant", reply)

            return reply

        except anthropic.APIError as e:
            logger.exception("Anthropic API error")
            return f"*The DM's crystal ball flickers...* (API error: {e.message})"
        except Exception as e:
            logger.exception("Unexpected error calling Claude")
            return f"*The DM's crystal ball goes dark...* (Error: {type(e).__name__})"

    async def get_dm_narration(self, campaign: Campaign, dm_directive: str) -> str:
        """Generate narration from a DM directive (no player action involved).

        Used for scene transitions, events, time passing, etc.
        """
        await self.summarize_and_trim(campaign)
        system = _build_system_blocks(campaign)
        messages = []

        # Include conversation history
        history = campaign.message_history
        for i, msg in enumerate(history):
            entry = {"role": msg["role"]}
            if i == len(history) - 1:
                entry["content"] = [
                    {"type": "text", "text": msg["content"], "cache_control": CACHE_BREAKPOINT}
                ]
            else:
                entry["content"] = msg["content"]
            messages.append(entry)

        # The DM directive as a user message
        user_content = (
            f"[DM DIRECTIVE — The human DM wants to advance the story]\n"
            f"{dm_directive}\n\n"
            f"Narrate this development engagingly. Consider the party's current status and location. "
            f"You may introduce NPCs, change the scene, trigger events, or advance time as appropriate."
        )
        messages.append({"role": "user", "content": user_content})

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1500,
                system=system,
                messages=messages,
            )

            reply = response.content[0].text

            # Log cache performance and track usage
            usage = response.usage
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
            total_input = getattr(usage, "input_tokens", 0) or 0
            if cache_read or cache_create:
                logger.info(
                    f"Cache stats — read: {cache_read}, created: {cache_create}, "
                    f"uncached: {total_input - cache_read - cache_create}, "
                    f"output: {usage.output_tokens}"
                )
            self._track(usage, session_id="dm_narration")

            # Update campaign history
            campaign.add_to_history("user", f"[DM Directive: {dm_directive}]")
            campaign.add_to_history("assistant", reply)

            return reply

        except anthropic.APIError as e:
            logger.exception("Anthropic API error")
            return f"*The DM's crystal ball flickers...* (API error: {e.message})"
        except Exception as e:
            logger.exception("Unexpected error calling Claude")
            return f"*The DM's crystal ball goes dark...* (Error: {type(e).__name__})"

    async def get_recap(self, campaign: Campaign) -> str:
        """Generate a recap of recent events."""
        system = [
            {"type": "text", "text": SYSTEM_PROMPT_STATIC, "cache_control": CACHE_BREAKPOINT},
            {"type": "text", "text": (
                "Generate a brief, dramatic recap of recent events in this campaign.\n"
                f"CAMPAIGN: {campaign.name}"
            )},
        ]

        log_text = "\n".join(campaign.session_log[-30:]) if campaign.session_log else "No events logged yet."
        messages = [{"role": "user", "content": f"Please give a recap of recent events:\n{log_text}"}]

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            self._track(response.usage, session_id="recap")
            return response.content[0].text
        except Exception as e:
            logger.exception("Error generating recap")
            return f"*The chronicler's quill falters...* (Error: {type(e).__name__})"

    async def generate_simple_response(self, prompt: str) -> str:
        """Generate a simple response from Claude without campaign context.

        Used for campaign suggestions, rules questions outside campaigns, etc.
        """
        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            self._track(response.usage, session_id="simple_response")
            return response.content[0].text
        except Exception as e:
            logger.exception("Error generating simple response")
            return f"*The DM's crystal ball flickers...* (Error: {type(e).__name__})"

    async def summarize_and_trim(self, campaign: Campaign):
        """Summarize old messages before trimming history to preserve story context.

        When history exceeds 80 messages, summarize the oldest 20 and keep 60.
        The summary is appended to campaign.story_summary for the system prompt.
        """
        THRESHOLD = 80
        KEEP = 60

        if len(campaign.message_history) <= THRESHOLD:
            return

        to_summarize = campaign.message_history[:THRESHOLD - KEEP]
        campaign.message_history = campaign.message_history[THRESHOLD - KEEP:]
        campaign.total_messages_processed += len(to_summarize)

        # Build text from messages to summarize
        summary_text = ""
        for msg in to_summarize:
            role = msg["role"].upper()
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            summary_text += f"{role}: {content[:300]}\n"

        existing = f"Previous summary:\n{campaign.story_summary}\n\n" if campaign.story_summary else ""

        prompt = (
            f"{existing}"
            f"Summarize the following D&D session transcript into a concise narrative summary "
            f"(3-5 paragraphs). Capture: key plot events, NPC interactions, combat outcomes, "
            f"decisions made, items found, and current situation. Write in past tense.\n\n"
            f"{summary_text}"
        )

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            self._track(response.usage, session_id="summarize")
            campaign.story_summary = response.content[0].text
            logger.info(
                f"Summarized {len(to_summarize)} messages, "
                f"history now {len(campaign.message_history)} messages"
            )
        except Exception:
            logger.exception("Failed to summarize history, keeping trimmed history without summary update")

    async def get_rules_response(self, campaign: Campaign, question: str,
                                  player_name: str, character_summary: str = "") -> str:
        """Answer a rules/meta question WITHOUT writing to campaign history.

        Reads the last 10 history messages for context but does not append
        the question or answer to message_history.
        """
        system = _build_system_blocks(campaign)

        # Build messages from last 10 history entries for context
        messages = []
        recent = campaign.message_history[-10:] if campaign.message_history else []
        for i, msg in enumerate(recent):
            entry = {"role": msg["role"]}
            if i == len(recent) - 1:
                entry["content"] = [
                    {"type": "text", "text": msg["content"], "cache_control": CACHE_BREAKPOINT}
                ]
            else:
                entry["content"] = msg["content"]
            messages.append(entry)

        # Add the question
        user_content = f"[Player: {player_name}"
        if character_summary:
            user_content += f" — {character_summary}"
        user_content += (
            f"]\n[OUT-OF-CHARACTER QUESTION — Do NOT advance the story, "
            f"do NOT narrate anything. Just answer this rules/meta question clearly.]\n"
            f"{question}"
        )
        messages.append({"role": "user", "content": user_content})

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            self._track(response.usage, session_id="rules_response")
            return response.content[0].text
        except anthropic.APIError as e:
            logger.exception("Anthropic API error")
            return f"*The DM's crystal ball flickers...* (API error: {e.message})"
        except Exception as e:
            logger.exception("Unexpected error calling Claude")
            return f"*The DM's crystal ball goes dark...* (Error: {type(e).__name__})"

    async def narrate_start(self, campaign: Campaign) -> str:
        """Generate the opening narration for a campaign."""
        system = _build_system_blocks(
            campaign,
            extra_system=f"DESCRIPTION: {campaign.description}",
        )

        messages = [{
            "role": "user",
            "content": (
                "The DM has started the campaign. Generate an epic opening narration that sets the scene, "
                "introduces the setting, and gives the party their first hook. Address the characters by name. "
                "End with a clear prompt for what the party sees/can do next."
            ),
        }]

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1500,
                system=system,
                messages=messages,
            )
            self._track(response.usage, session_id="narrate_start")
            reply = response.content[0].text
            campaign.add_to_history("user", "[Campaign begins]")
            campaign.add_to_history("assistant", reply)
            campaign.add_session_log("Campaign started with opening narration.")
            return reply
        except Exception as e:
            logger.exception("Error generating opening narration")
            return f"*The story awaits, but the magic falters...* (Error: {type(e).__name__})"

    async def generate_campaign_story(self, campaign: Campaign) -> str:
        """Generate a polished narrative retelling of the entire campaign.

        Combines story_summary, session_log, message_history, and character info
        into source material, then asks Claude to write a well-structured story.
        Returns the full story text.
        """
        # Build source material from everything we have
        source_parts = []

        source_parts.append(f"CAMPAIGN: {campaign.name or 'Untitled Campaign'}")
        if campaign.description:
            source_parts.append(f"PREMISE: {campaign.description}")

        # Characters
        if campaign.characters:
            source_parts.append("\nCHARACTERS:")
            for char in campaign.characters.values():
                if char.creation_complete:
                    source_parts.append(
                        f"- {char.name}, {char.race} {char.char_class} (Level {char.level}) "
                        f"— played by {char.owner_name}"
                    )
                    if char.backstory:
                        source_parts.append(f"  Backstory: {char.backstory[:300]}")

        # Story summary (accumulated from summarize_and_trim)
        if campaign.story_summary:
            source_parts.append(f"\nSTORY SUMMARY (from earlier sessions):\n{campaign.story_summary}")

        # Session log (key events)
        if campaign.session_log:
            source_parts.append("\nSESSION LOG (key events in order):")
            for entry in campaign.session_log:
                source_parts.append(f"- {entry}")

        # Recent message history (the actual dialogue/narration)
        if campaign.message_history:
            source_parts.append("\nRECENT DIALOGUE/NARRATION (most recent exchanges):")
            for msg in campaign.message_history[-40:]:
                role = "DM" if msg["role"] == "assistant" else "Player"
                content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
                source_parts.append(f"[{role}]: {content[:500]}")

        source_text = "\n".join(source_parts)

        prompt = (
            "You are a fantasy author commissioned to write the tale of a D&D campaign. "
            "Using the source material below, write a polished, engaging narrative retelling "
            "of the entire campaign story.\n\n"
            "GUIDELINES:\n"
            "- Write in third person, past tense, like a fantasy novel\n"
            "- Include all major plot events, battles, discoveries, and character moments\n"
            "- Give each player character their voice and personality\n"
            "- Include NPC interactions and memorable dialogue\n"
            "- Describe combat encounters dramatically but concisely\n"
            "- Structure with clear sections or chapters if the story is long\n"
            "- Open with a title and the party roster\n"
            "- End with where the story left off or how it concluded\n"
            "- Write as much as needed to capture the full story — do not cut short\n\n"
            f"SOURCE MATERIAL:\n{source_text}"
        )

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            self._track(response.usage, session_id="campaign_story")
            return response.content[0].text
        except Exception as e:
            logger.exception("Error generating campaign story")
            return f"Failed to generate story: {type(e).__name__}: {e}"

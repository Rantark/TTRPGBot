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

# Pattern for action tags: [TAG_TYPE: params]
_ACTION_TAG_PATTERN = re.compile(r'\[(\w+):\s*([^\]]+)\]')


def parse_action_tags(response_text: str, campaign: Campaign) -> tuple[str, list[str]]:
    """Extract and execute action tags from Claude's response.

    Returns (clean_text, log_entries) where clean_text has tags removed
    and log_entries describes what was changed.
    """
    log_entries = []

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

        return ""

    clean_text = _ACTION_TAG_PATTERN.sub(_process_tag, response_text)
    # Clean up extra whitespace from tag removal
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
    return clean_text, log_entries


def extract_whispers(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Extract [WHISPER: CharName] messages from text.

    Returns (clean_text, [(char_name, message), ...])
    """
    whispers = []
    # Match [WHISPER: Name] followed by text until next tag or end of line(s)
    pattern = re.compile(r'\[WHISPER:\s*([^\]]+)\]\s*(.+?)(?=\[(?:WHISPER|DAMAGE|CONDITION|NPC_DEFEAT|SPELL_SLOT|LOOT):|$)', re.DOTALL)
    for match in pattern.finditer(text):
        char_name = match.group(1).strip()
        message = match.group(2).strip()
        if message:
            whispers.append((char_name, message))

    # Remove whisper tags from display text
    clean = re.compile(r'\[WHISPER:\s*[^\]]+\]\s*.+?(?=\[(?:WHISPER|DAMAGE|CONDITION|NPC_DEFEAT|SPELL_SLOT|LOOT):|$)', re.DOTALL)
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
- When combat starts, describe the scene and enemies clearly.
- Tell players to roll initiative.
- On each player's turn, describe the situation and ask what they do.
- When a player attacks, tell them the result based on their roll vs enemy AC.
- Track enemy HP internally and describe damage narratively ("The goblin staggers from the blow").
- Don't reveal exact enemy HP numbers — describe condition instead (healthy, wounded, bloodied, near death).

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

EXAMPLES:
"The orc's axe crashes down! [DAMAGE: Thandril -9] Thandril, you take 9 slashing damage."

"The spider's fangs pierce your armor! [DAMAGE: Kael -6] [CONDITION: Kael add poisoned]
Kael, you feel venom coursing through your veins."

"[WHISPER: Elara] You notice a hidden door behind the tapestry — the others haven't seen it."

"The chest contains a modest treasure. [LOOT: Thandril | 25 gold, Potion of Healing]"

Use these tags whenever you deal damage, heal, inflict conditions, give loot, or share secrets.
Always include the tag AND describe the effect narratively."""

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

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    async def get_dm_response(self, campaign: Campaign, player_action: str,
                              player_name: str, character_summary: str = "",
                              extra_context: str = "") -> str:
        """Get a DM response from Claude for a player action.

        Uses prompt caching on system prompt and conversation history
        to minimize token costs across a session.
        """
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

            # Log cache performance
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

            # Log cache performance
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
            return response.content[0].text
        except Exception as e:
            logger.exception("Error generating recap")
            return f"*The chronicler's quill falters...* (Error: {type(e).__name__})"

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
            reply = response.content[0].text
            campaign.add_to_history("user", "[Campaign begins]")
            campaign.add_to_history("assistant", reply)
            campaign.add_session_log("Campaign started with opening narration.")
            return reply
        except Exception as e:
            logger.exception("Error generating opening narration")
            return f"*The story awaits, but the magic falters...* (Error: {type(e).__name__})"

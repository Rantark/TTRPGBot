"""Claude AI Dungeon Master engine using Anthropic API."""

import os
import logging

import anthropic

from bot.models.campaign import Campaign

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Dungeon Master for a D&D 5th Edition campaign being played over Discord.

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
- Never give away puzzle solutions or secrets unless earned through play."""


def build_dm_context(campaign: Campaign, player_action: str, player_name: str,
                     character_summary: str = "", extra_context: str = "") -> list[dict]:
    """Build the messages list for a Claude API call.

    Incorporates campaign history and current player action.
    """
    messages = []

    # Include relevant conversation history
    for msg in campaign.message_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Build the current user message with context
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
    """Manages Claude API calls for the DM."""

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

        Returns the response text, and updates campaign history.
        """
        # Build system prompt with campaign context
        system = SYSTEM_PROMPT + "\n\n"
        system += f"CAMPAIGN: {campaign.name}\n"
        if campaign.description:
            system += f"CAMPAIGN DESCRIPTION: {campaign.description}\n"
        system += f"\nPARTY:\n{campaign.get_party_summary()}\n"

        if campaign.known_npcs:
            system += "\nKNOWN NPCs:\n"
            for npc in campaign.known_npcs:
                system += f"- {npc['name']}: {npc['description']}\n"

        if campaign.combat.active:
            system += "\nCOMBAT IS ACTIVE"
            system += f" — Round {campaign.combat.round_number}"
            if campaign.combat.current_turn:
                system += f", Current turn: {campaign.combat.current_turn['name']}"
            system += "\nInitiative Order:\n"
            for i, entry in enumerate(campaign.combat.initiative_order):
                marker = " ⟵" if i == campaign.combat.current_turn_index else ""
                system += f"  {entry['name']}: {entry['roll']}{marker}\n"

        messages = build_dm_context(
            campaign, player_action, player_name,
            character_summary, extra_context,
        )

        try:
            # Use synchronous client in thread to avoid blocking
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=messages,
            )

            reply = response.content[0].text

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

    async def get_recap(self, campaign: Campaign) -> str:
        """Generate a recap of recent events."""
        system = SYSTEM_PROMPT + "\n\nGenerate a brief, dramatic recap of recent events in this campaign."
        system += f"\nCAMPAIGN: {campaign.name}"

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
        system = SYSTEM_PROMPT
        system += f"\n\nCAMPAIGN: {campaign.name}"
        system += f"\nDESCRIPTION: {campaign.description}"
        system += f"\nPARTY:\n{campaign.get_party_summary()}"

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

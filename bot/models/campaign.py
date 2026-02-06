"""Campaign model for managing game state."""

from enum import Enum
from bot.models.character import Character


class CampaignPhase(str, Enum):
    NONE = "none"            # No campaign yet
    PITCHING = "pitching"    # Proposing/voting on campaign concepts
    SETUP = "setup"          # Players creating characters
    ACTIVE = "active"        # Campaign in progress


class CombatState:
    """Tracks combat encounter state."""

    def __init__(self):
        self.active = False
        self.initiative_order = []  # List of {"name": str, "roll": int, "player_id": str|None}
        self.current_turn_index = 0
        self.round_number = 1

    @property
    def current_turn(self):
        if not self.initiative_order:
            return None
        return self.initiative_order[self.current_turn_index]

    def advance_turn(self):
        self.current_turn_index += 1
        if self.current_turn_index >= len(self.initiative_order):
            self.current_turn_index = 0
            self.round_number += 1

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "initiative_order": self.initiative_order,
            "current_turn_index": self.current_turn_index,
            "round_number": self.round_number,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CombatState":
        cs = cls()
        cs.active = data.get("active", False)
        cs.initiative_order = data.get("initiative_order", [])
        cs.current_turn_index = data.get("current_turn_index", 0)
        cs.round_number = data.get("round_number", 1)
        return cs


class Campaign:
    """Represents a campaign in a Discord channel."""

    def __init__(self, channel_id: str, guild_id: str):
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.phase = CampaignPhase.NONE
        self.dm_id = None  # Discord user ID of the person who runs commands
        self.name = ""
        self.description = ""
        self.characters: dict[str, Character] = {}  # player_id -> Character
        self.combat = CombatState()
        self.pitches: list[dict] = []  # [{"author_id": str, "title": str, "description": str, "votes": [str]}]
        self.message_history: list[dict] = []  # For Claude context: [{"role": str, "content": str}]
        self.known_npcs: list[dict] = []  # [{"name": str, "description": str}]
        self.clues: list[str] = []
        self.session_log: list[str] = []  # Brief event log for recaps

    def get_character(self, player_id: str) -> Character | None:
        return self.characters.get(player_id)

    def add_character(self, player_id: str, char: Character):
        self.characters[player_id] = char

    def remove_character(self, player_id: str):
        self.characters.pop(player_id, None)

    def get_party_summary(self) -> str:
        """Get a summary of all characters for DM context."""
        if not self.characters:
            return "No characters created yet."
        lines = []
        for char in self.characters.values():
            lines.append(f"- {char.short_summary()}")
        return "\n".join(lines)

    def add_to_history(self, role: str, content: str):
        """Add a message to the Claude conversation history, keeping it bounded."""
        self.message_history.append({"role": role, "content": content})
        # Keep last 80 messages to stay within context limits
        if len(self.message_history) > 80:
            self.message_history = self.message_history[-80:]

    def add_session_log(self, entry: str):
        self.session_log.append(entry)
        if len(self.session_log) > 200:
            self.session_log = self.session_log[-200:]

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "phase": self.phase.value,
            "dm_id": self.dm_id,
            "name": self.name,
            "description": self.description,
            "characters": {pid: c.to_dict() for pid, c in self.characters.items()},
            "combat": self.combat.to_dict(),
            "pitches": self.pitches,
            "message_history": self.message_history,
            "known_npcs": self.known_npcs,
            "clues": self.clues,
            "session_log": self.session_log,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        c = cls(data["channel_id"], data["guild_id"])
        c.phase = CampaignPhase(data.get("phase", "none"))
        c.dm_id = data.get("dm_id")
        c.name = data.get("name", "")
        c.description = data.get("description", "")
        c.characters = {
            pid: Character.from_dict(cdata)
            for pid, cdata in data.get("characters", {}).items()
        }
        c.combat = CombatState.from_dict(data.get("combat", {}))
        c.pitches = data.get("pitches", [])
        c.message_history = data.get("message_history", [])
        c.known_npcs = data.get("known_npcs", [])
        c.clues = data.get("clues", [])
        c.session_log = data.get("session_log", [])
        return c

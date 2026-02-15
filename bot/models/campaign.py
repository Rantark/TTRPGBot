"""Campaign model for managing game state."""

from enum import Enum
from bot.models.character import Character


class CampaignPace(str, Enum):
    ASYNC = "async"  # No timeout — players take as long as they need
    LIVE = "live"    # 30-minute AFK timeout per round


class CampaignPhase(str, Enum):
    NONE = "none"            # No campaign yet
    PITCHING = "pitching"    # Proposing/voting on campaign concepts
    SETUP = "setup"          # Players creating characters
    ACTIVE = "active"        # Campaign in progress


class CombatMap:
    """Simple grid-based combat map for ASCII display."""

    DEFAULT_WIDTH = 12
    DEFAULT_HEIGHT = 10

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self.width = width
        self.height = height
        self.positions: dict[str, list[int]] = {}  # name -> [x, y]
        self.tokens: dict[str, str] = {}  # name -> display char (1-2 chars)
        self.terrain: dict[str, str] = {}  # "x,y" -> char (e.g. "#" for wall)

    def place(self, name: str, x: int, y: int, token: str = ""):
        """Place or move a token on the map."""
        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))
        self.positions[name] = [x, y]
        if token:
            self.tokens[name] = token[:2]
        elif name not in self.tokens:
            self.tokens[name] = name[:2].upper()

    def remove(self, name: str):
        self.positions.pop(name, None)
        self.tokens.pop(name, None)

    def move(self, name: str, dx: int, dy: int) -> bool:
        """Move a token by relative offset. Returns True if moved."""
        if name not in self.positions:
            return False
        pos = self.positions[name]
        new_x = max(0, min(pos[0] + dx, self.width - 1))
        new_y = max(0, min(pos[1] + dy, self.height - 1))
        self.positions[name] = [new_x, new_y]
        return True

    def render(self) -> str:
        """Render the map as ASCII art in a code block."""
        # Build position lookup: (x, y) -> token
        occupied: dict[tuple[int, int], str] = {}
        for name, pos in self.positions.items():
            key = (pos[0], pos[1])
            occupied[key] = self.tokens.get(name, name[:2].upper())

        # Column headers
        col_header = "   " + "".join(f"{i:3d}" for i in range(self.width))
        lines = [col_header]
        lines.append("   " + "┌" + "──┬" * (self.width - 1) + "──┐")

        for y in range(self.height):
            row = f"{y:2d} │"
            for x in range(self.width):
                terrain_key = f"{x},{y}"
                if (x, y) in occupied:
                    tk = occupied[(x, y)]
                    row += f"{tk:>2}│"
                elif terrain_key in self.terrain:
                    ch = self.terrain[terrain_key]
                    row += f"{ch:>2}│"
                else:
                    row += "  │"
            lines.append(row)
            if y < self.height - 1:
                lines.append("   " + "├" + "──┼" * (self.width - 1) + "──┤")

        lines.append("   " + "└" + "──┴" * (self.width - 1) + "──┘")

        # Legend
        if self.positions:
            lines.append("")
            legend_items = []
            for name in sorted(self.positions.keys()):
                tk = self.tokens.get(name, name[:2].upper())
                pos = self.positions[name]
                legend_items.append(f"{tk}={name} ({pos[0]},{pos[1]})")
            lines.append("Legend: " + "  ".join(legend_items))

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "positions": self.positions,
            "tokens": self.tokens,
            "terrain": self.terrain,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CombatMap":
        m = cls(data.get("width", cls.DEFAULT_WIDTH), data.get("height", cls.DEFAULT_HEIGHT))
        m.positions = data.get("positions", {})
        m.tokens = data.get("tokens", {})
        m.terrain = data.get("terrain", {})
        return m


class CombatState:
    """Tracks combat encounter state."""

    def __init__(self):
        self.active = False
        self.initiative_order = []  # List of {"name": str, "roll": int, "player_id": str|None}
        self.current_turn_index = 0
        self.round_number = 1
        self.combat_map = CombatMap()

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
            "combat_map": self.combat_map.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CombatState":
        cs = cls()
        cs.active = data.get("active", False)
        cs.initiative_order = data.get("initiative_order", [])
        cs.current_turn_index = data.get("current_turn_index", 0)
        cs.round_number = data.get("round_number", 1)
        if "combat_map" in data:
            cs.combat_map = CombatMap.from_dict(data["combat_map"])
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
        # Starting level for new characters (DM can set with !setlevel)
        self.starting_level: int = 1
        # Thread/forum-based campaign support
        self.thread_id: str | None = None       # Discord thread ID where gameplay happens
        self.parent_channel_id: str | None = None  # Original channel where campaign was created
        self.forum_post_id: str | None = None    # Discord forum post ID where campaign lives
        self.setup_channel_id: str | None = channel_id  # Channel where !newcampaign was run
        # RP scene coordination: queue actions until all players act or pass
        self.pending_actions: dict[str, str] = {}  # player_id -> action text
        self.passed_players: list[str] = []  # player_ids who passed this round
        # History summarization — rolling summary of trimmed messages
        self.story_summary: str = ""
        self.total_messages_processed: int = 0
        # Campaign pace and AFK tracking
        self.pace = CampaignPace.ASYNC
        self.last_action_time: float = 0.0  # time.time() of last player action
        self.last_reminder_time: float = 0.0  # time.time() of last 24h auto-reminder

    def get_character(self, player_id: str) -> Character | None:
        return self.characters.get(player_id)

    def get_character_by_name(self, name: str) -> Character | None:
        """Find a character by name (case-insensitive)."""
        name_lower = name.lower()
        for char in self.characters.values():
            if char.name.lower() == name_lower:
                return char
        return None

    def get_player_id_by_char_name(self, name: str) -> str | None:
        """Find a player ID by their character's name (case-insensitive)."""
        name_lower = name.lower()
        for pid, char in self.characters.items():
            if char.name.lower() == name_lower:
                return pid
        return None

    def add_character(self, player_id: str, char: Character):
        self.characters[player_id] = char

    def remove_character(self, player_id: str):
        self.characters.pop(player_id, None)

    def get_party_summary(self) -> str:
        """Get a detailed summary of all characters for DM context."""
        if not self.characters:
            return "No characters created yet."
        lines = []
        for char in self.characters.values():
            lines.append(char.dm_stat_block())
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

    def get_active_player_ids(self) -> list[str]:
        """Return player IDs of characters that are complete (active players)."""
        return [pid for pid, c in self.characters.items() if c.creation_complete]

    def all_players_acted(self) -> bool:
        """Check if every active player has submitted an action or passed."""
        active = set(self.get_active_player_ids())
        acted = set(self.pending_actions.keys()) | set(self.passed_players)
        return active.issubset(acted)

    def get_waiting_player_ids(self) -> list[str]:
        """Return player IDs who haven't acted or passed yet."""
        active = set(self.get_active_player_ids())
        acted = set(self.pending_actions.keys()) | set(self.passed_players)
        return [pid for pid in active if pid not in acted]

    def clear_pending(self):
        """Clear all pending actions and passes for the next round."""
        self.pending_actions = {}
        self.passed_players = []

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
            "starting_level": self.starting_level,
            "thread_id": self.thread_id,
            "parent_channel_id": self.parent_channel_id,
            "forum_post_id": self.forum_post_id,
            "setup_channel_id": self.setup_channel_id,
            "pending_actions": self.pending_actions,
            "passed_players": self.passed_players,
            "story_summary": self.story_summary,
            "total_messages_processed": self.total_messages_processed,
            "pace": self.pace.value,
            "last_action_time": self.last_action_time,
            "last_reminder_time": self.last_reminder_time,
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
        c.starting_level = data.get("starting_level", 1)
        c.thread_id = data.get("thread_id")
        c.parent_channel_id = data.get("parent_channel_id")
        c.forum_post_id = data.get("forum_post_id")
        c.setup_channel_id = data.get("setup_channel_id", data.get("channel_id"))
        c.pending_actions = data.get("pending_actions", {})
        c.passed_players = data.get("passed_players", [])
        c.story_summary = data.get("story_summary", "")
        c.total_messages_processed = data.get("total_messages_processed", 0)
        try:
            c.pace = CampaignPace(data.get("pace", "async"))
        except ValueError:
            c.pace = CampaignPace.ASYNC
        c.last_action_time = data.get("last_action_time", 0.0)
        c.last_reminder_time = data.get("last_reminder_time", 0.0)
        return c

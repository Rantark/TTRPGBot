"""Character model for World of Darkness / Chronicles of Darkness (Vampire the Requiem, etc.)."""


# WoD Attribute categories
WOD_MENTAL_ATTRIBUTES = ["Intelligence", "Wits", "Resolve"]
WOD_PHYSICAL_ATTRIBUTES = ["Strength", "Dexterity", "Stamina"]
WOD_SOCIAL_ATTRIBUTES = ["Presence", "Manipulation", "Composure"]
WOD_ALL_ATTRIBUTES = WOD_MENTAL_ATTRIBUTES + WOD_PHYSICAL_ATTRIBUTES + WOD_SOCIAL_ATTRIBUTES

# WoD Skill categories
WOD_MENTAL_SKILLS = [
    "Academics", "Computer", "Crafts", "Investigation", "Medicine",
    "Occult", "Politics", "Science",
]
WOD_PHYSICAL_SKILLS = [
    "Athletics", "Brawl", "Drive", "Firearms", "Larceny",
    "Stealth", "Survival", "Weaponry",
]
WOD_SOCIAL_SKILLS = [
    "Animal Ken", "Empathy", "Expression", "Intimidation", "Persuasion",
    "Socialize", "Streetwise", "Subterfuge",
]
WOD_ALL_SKILLS = WOD_MENTAL_SKILLS + WOD_PHYSICAL_SKILLS + WOD_SOCIAL_SKILLS


class WoDCharacter:
    """Represents a World of Darkness character (Vampire the Requiem focus)."""

    def __init__(self, owner_id: str, owner_name: str):
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.name = ""
        self.gender = ""
        self.concept = ""       # Character concept (one-line description)
        self.virtue = ""        # Primary virtue (e.g., "Justice", "Hope")
        self.vice = ""          # Primary vice (e.g., "Wrath", "Pride")

        # ── Supernatural Template ──
        self.creature_type = "Vampire"  # Vampire, Mortal, Ghoul, etc.
        self.clan = ""          # Daeva, Gangrel, Mekhet, Nosferatu, Ventrue
        self.covenant = ""      # Carthian Movement, Circle of the Crone, Invictus, Lancea et Sanctum, Ordo Dracul
        self.bloodline = ""     # Optional bloodline

        # ── Attributes (1-5 dots, default 1) ──
        self.attributes = {attr: 1 for attr in WOD_ALL_ATTRIBUTES}

        # ── Skills (0-5 dots, default 0) ──
        self.skills = {skill: 0 for skill in WOD_ALL_SKILLS}

        # ── Skill Specialties ──
        self.specialties: dict[str, list[str]] = {}  # skill -> [specialty1, specialty2, ...]

        # ── Disciplines (vampire powers, 0-5 dots) ──
        self.disciplines: dict[str, int] = {}  # discipline_name -> dots

        # ── Merits (0-5 dots each) ──
        self.merits: dict[str, int] = {}  # merit_name -> dots

        # ── Vampire-specific ──
        self.blood_potency = 1      # 1-10 (starting vampires usually 1)
        self.vitae = 0              # Current Vitae (blood points)
        self.vitae_max = 0          # Max Vitae (based on Blood Potency)
        self.vitae_per_turn = 1     # How much Vitae can be spent per turn
        self.humanity = 7           # 0-10 (7 is default for new vampires)

        # ── Derived Stats ──
        self.health_max = 0         # Stamina + Size (Size = 5 for humans)
        self.health_current = 0
        self.health_track = []      # List of damage types: [], "B" (bashing), "L" (lethal), "A" (aggravated)
        self.willpower_max = 0      # Resolve + Composure
        self.willpower_current = 0
        self.defense = 0            # Lower of Dexterity or Wits + Athletics
        self.initiative_mod = 0     # Dexterity + Composure
        self.speed = 0              # Strength + Dexterity + 5
        self.size = 5               # 5 for humans/vampires
        self.armor = 0              # From equipment

        # ── Equipment & Inventory ──
        self.weapons = []           # List of weapon dicts
        self.inventory = []         # List of item names or dicts
        self.notes = ""

        # ── Backstory ──
        self.backstory = ""
        self.requiem_history = ""   # How they became a vampire

        # ── Creation state tracking ──
        self.creation_complete = False

        # ── Experience ──
        self.xp = 0
        self.xp_spent = 0
        self.beats = 0              # 5 beats = 1 XP

    # ------------------------------------------------------------------
    # Inventory helpers (mirror D&D character)
    # ------------------------------------------------------------------

    def add_item(self, item_name: str, quantity: int = 1):
        for i, entry in enumerate(self.inventory):
            if isinstance(entry, dict) and entry["name"].lower() == item_name.lower():
                entry["quantity"] = entry.get("quantity", 1) + quantity
                return
            elif isinstance(entry, str) and entry.lower() == item_name.lower():
                self.inventory[i] = {"name": entry, "quantity": 1 + quantity}
                return
        if quantity > 1:
            self.inventory.append({"name": item_name, "quantity": quantity})
        else:
            self.inventory.append(item_name)

    def remove_item(self, item_name: str, quantity: int = 1) -> bool:
        for i, entry in enumerate(self.inventory):
            name = entry["name"] if isinstance(entry, dict) else entry
            if name.lower() == item_name.lower():
                if isinstance(entry, dict):
                    current = entry.get("quantity", 1)
                    if current < quantity:
                        return False
                    entry["quantity"] = current - quantity
                    if entry["quantity"] <= 0:
                        self.inventory.pop(i)
                else:
                    if quantity > 1:
                        return False
                    self.inventory.pop(i)
                return True
        return False

    def has_item(self, item_name: str, quantity: int = 1) -> bool:
        for entry in self.inventory:
            name = entry["name"] if isinstance(entry, dict) else entry
            if name.lower() == item_name.lower():
                current = entry.get("quantity", 1) if isinstance(entry, dict) else 1
                return current >= quantity
        return False

    def get_item_count(self, item_name: str) -> int:
        for entry in self.inventory:
            name = entry["name"] if isinstance(entry, dict) else entry
            if name.lower() == item_name.lower():
                return entry.get("quantity", 1) if isinstance(entry, dict) else 1
        return 0

    # ------------------------------------------------------------------
    # Derived stat calculations
    # ------------------------------------------------------------------

    def calc_derived(self):
        """Calculate all derived stats from attributes."""
        # Health = Stamina + Size
        self.health_max = self.attributes["Stamina"] + self.size
        self.health_current = self.health_max
        self.health_track = [""] * self.health_max

        # Willpower = Resolve + Composure
        self.willpower_max = self.attributes["Resolve"] + self.attributes["Composure"]
        self.willpower_current = self.willpower_max

        # Defense = lower of Dexterity or Wits + Athletics
        self.defense = min(
            self.attributes["Dexterity"],
            self.attributes["Wits"]
        ) + self.skills.get("Athletics", 0)

        # Initiative = Dexterity + Composure
        self.initiative_mod = self.attributes["Dexterity"] + self.attributes["Composure"]

        # Speed = Strength + Dexterity + 5
        self.speed = self.attributes["Strength"] + self.attributes["Dexterity"] + 5

        # Vitae (based on Blood Potency)
        bp_vitae_max = {
            0: 0, 1: 10, 2: 11, 3: 12, 4: 13, 5: 15,
            6: 20, 7: 25, 8: 30, 9: 50, 10: 100,
        }
        bp_vitae_per_turn = {
            0: 0, 1: 1, 2: 1, 3: 1, 4: 2, 5: 2,
            6: 3, 7: 5, 8: 7, 9: 10, 10: 15,
        }
        self.vitae_max = bp_vitae_max.get(self.blood_potency, 10)
        self.vitae_per_turn = bp_vitae_per_turn.get(self.blood_potency, 1)
        if self.vitae == 0:
            self.vitae = self.vitae_max

    def finalize(self, **kwargs):
        """Finalize character after creation — calculate derived stats."""
        self.calc_derived()
        self.creation_complete = True

    def _health_bar(self, width: int = 0) -> str:
        """Generate a visual health track. WoD uses damage types, not HP bars."""
        if not self.health_track:
            return "[ ]" * self.health_max
        symbols = {"": "[ ]", "B": "[/]", "L": "[X]", "A": "[*]"}
        return " ".join(symbols.get(d, "[ ]") for d in self.health_track)

    def _format_inv_item(self, entry) -> str:
        if isinstance(entry, dict):
            name = entry["name"]
            qty = entry.get("quantity", 1)
            return f"{name} x{qty}" if qty > 1 else name
        return str(entry)

    def format_sheet(self) -> str:
        """Format a full character sheet for display in Discord."""
        gender_str = f" | {self.gender}" if self.gender else ""

        lines = [
            f"{'=' * 44}",
            f"  **{self.name}**",
            f"  {self.creature_type} — Clan {self.clan}{gender_str}",
        ]
        if self.covenant:
            lines.append(f"  Covenant: {self.covenant}")
        if self.concept:
            lines.append(f"  *{self.concept}*")
        lines.append(f"{'=' * 44}")

        # Virtue / Vice
        if self.virtue or self.vice:
            parts = []
            if self.virtue:
                parts.append(f"Virtue: {self.virtue}")
            if self.vice:
                parts.append(f"Vice: {self.vice}")
            lines.append(f"  {' | '.join(parts)}")

        # ── Vampire Stats ──
        if self.creature_type == "Vampire":
            lines.append(f"  Blood Potency: **{self.blood_potency}** | Humanity: **{self.humanity}**")
            vitae_pips = "O" * self.vitae + "." * (self.vitae_max - self.vitae)
            lines.append(f"  Vitae: {self.vitae}/{self.vitae_max} ({self.vitae_per_turn}/turn)")

        # ── Health & Willpower ──
        lines.append(f"  Health: {self._health_bar()}")
        wp_pips = "O" * self.willpower_current + "." * (self.willpower_max - self.willpower_current)
        lines.append(f"  Willpower: [{wp_pips}] ({self.willpower_current}/{self.willpower_max})")

        # ── Derived ──
        lines.append(f"  Defense: {self.defense} | Initiative: +{self.initiative_mod} | Speed: {self.speed}")
        if self.armor:
            lines.append(f"  Armor: {self.armor}")

        # ── Attributes ──
        lines.append(f"{'=' * 44}")
        lines.append("  **Attributes**")
        lines.append("```")
        # Print side-by-side: Mental | Physical | Social
        headers = f"{'Mental':<18s}{'Physical':<18s}{'Social':<18s}"
        lines.append(f"  {headers}")
        for i in range(3):
            m_attr = WOD_MENTAL_ATTRIBUTES[i]
            p_attr = WOD_PHYSICAL_ATTRIBUTES[i]
            s_attr = WOD_SOCIAL_ATTRIBUTES[i]
            m_dots = "O" * self.attributes[m_attr] + "." * (5 - self.attributes[m_attr])
            p_dots = "O" * self.attributes[p_attr] + "." * (5 - self.attributes[p_attr])
            s_dots = "O" * self.attributes[s_attr] + "." * (5 - self.attributes[s_attr])
            lines.append(
                f"  {m_attr:<13s}{m_dots}  {p_attr:<13s}{p_dots}  {s_attr:<13s}{s_dots}"
            )
        lines.append("```")

        # ── Skills ──
        lines.append("  **Skills**")
        lines.append("```")
        headers = f"{'Mental':<22s}{'Physical':<22s}{'Social':<22s}"
        lines.append(f"  {headers}")
        max_len = max(len(WOD_MENTAL_SKILLS), len(WOD_PHYSICAL_SKILLS), len(WOD_SOCIAL_SKILLS))
        for i in range(max_len):
            parts = []
            for skill_list in [WOD_MENTAL_SKILLS, WOD_PHYSICAL_SKILLS, WOD_SOCIAL_SKILLS]:
                if i < len(skill_list):
                    sk = skill_list[i]
                    dots_val = self.skills.get(sk, 0)
                    dots = "O" * dots_val + "." * (5 - dots_val) if dots_val > 0 else "....."
                    parts.append(f"{sk:<15s}{dots}")
                else:
                    parts.append(" " * 20)
            lines.append(f"  {'  '.join(parts)}")
        lines.append("```")

        # ── Specialties ──
        if self.specialties:
            lines.append("  **Specialties**")
            for skill, specs in self.specialties.items():
                lines.append(f"  {skill}: {', '.join(specs)}")

        # ── Disciplines ──
        if self.disciplines:
            lines.append(f"{'=' * 44}")
            lines.append("  **Disciplines**")
            for disc, dots in sorted(self.disciplines.items()):
                dot_str = "O" * dots + "." * (5 - dots)
                lines.append(f"  {disc}: {dot_str}")

        # ── Merits ──
        if self.merits:
            lines.append("  **Merits**")
            for merit, dots in sorted(self.merits.items()):
                dot_str = "O" * dots + "." * (5 - dots)
                lines.append(f"  {merit}: {dot_str}")

        # ── Weapons ──
        if self.weapons:
            lines.append(f"{'=' * 44}")
            lines.append("  **Weapons**")
            for w in self.weapons:
                damage = w.get("damage", 0)
                lines.append(f"  {w['name']} (Damage +{damage}, {w.get('type', 'B')})")

        # ── Inventory ──
        if self.inventory:
            lines.append("  **Equipment**")
            items = [self._format_inv_item(e) for e in self.inventory[:10]]
            lines.append(f"  {', '.join(items)}")

        lines.append(f"{'=' * 44}")
        return "\n".join(lines)

    def short_summary(self) -> str:
        """One-line character summary for DM context."""
        gender_str = f", {self.gender}" if self.gender else ""
        cov_str = f", {self.covenant}" if self.covenant else ""
        health_dmg = sum(1 for d in self.health_track if d)
        health_str = f"Health {self.health_max - health_dmg}/{self.health_max}"
        return (
            f"{self.name} ({self.creature_type}, Clan {self.clan}{cov_str}{gender_str}, "
            f"{health_str}, Vitae {self.vitae}/{self.vitae_max}, "
            f"Humanity {self.humanity}, BP {self.blood_potency})"
        )

    def full_context(self) -> str:
        """Full character context for the DM."""
        lines = [self.short_summary()]
        if self.backstory:
            lines.append(f"  Backstory: {self.backstory}")
        if self.requiem_history:
            lines.append(f"  Requiem: {self.requiem_history}")
        if self.disciplines:
            disc_strs = [f"{d} {v}" for d, v in self.disciplines.items()]
            lines.append(f"  Disciplines: {', '.join(disc_strs)}")
        return "\n".join(lines)

    def dm_stat_block(self) -> str:
        """Detailed stat block for DM context — gives Claude full visibility."""
        if not self.creation_complete:
            return f"- {self.owner_name} -- *Creating character...*"

        gender_str = f", {self.gender}" if self.gender else ""
        cov_str = f", {self.covenant}" if self.covenant else ""

        lines = [f"- {self.name} ({self.creature_type}, Clan {self.clan}{cov_str}{gender_str})"]

        # Health/Vitae/Willpower
        health_dmg = sum(1 for d in self.health_track if d)
        bashing = sum(1 for d in self.health_track if d == "B")
        lethal = sum(1 for d in self.health_track if d == "L")
        aggravated = sum(1 for d in self.health_track if d == "A")
        dmg_parts = []
        if bashing:
            dmg_parts.append(f"{bashing}B")
        if lethal:
            dmg_parts.append(f"{lethal}L")
        if aggravated:
            dmg_parts.append(f"{aggravated}A")
        dmg_str = f" [{', '.join(dmg_parts)}]" if dmg_parts else ""
        lines.append(
            f"  Health: {self.health_max - health_dmg}/{self.health_max}{dmg_str} | "
            f"Willpower: {self.willpower_current}/{self.willpower_max} | "
            f"Vitae: {self.vitae}/{self.vitae_max}"
        )
        lines.append(
            f"  BP: {self.blood_potency} | Humanity: {self.humanity} | "
            f"Defense: {self.defense} | Initiative: +{self.initiative_mod} | Speed: {self.speed}"
        )

        # Attributes
        attr_strs = [f"{a[:3]} {self.attributes[a]}" for a in WOD_ALL_ATTRIBUTES]
        lines.append(f"  {', '.join(attr_strs)}")

        # Key skills (non-zero)
        skill_strs = [f"{s} {v}" for s, v in self.skills.items() if v > 0]
        if skill_strs:
            lines.append(f"  Skills: {', '.join(skill_strs)}")

        # Disciplines
        if self.disciplines:
            disc_strs = [f"{d} {v}" for d, v in self.disciplines.items()]
            lines.append(f"  Disciplines: {', '.join(disc_strs)}")

        # Equipment
        if self.inventory:
            items = [self._format_inv_item(e) for e in self.inventory[:5]]
            extra = f" (+{len(self.inventory) - 5} more)" if len(self.inventory) > 5 else ""
            lines.append(f"  Equipment: {', '.join(items)}{extra}")

        if self.backstory:
            lines.append(f"  Backstory: {self.backstory[:200]}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "name": self.name,
            "gender": self.gender,
            "concept": self.concept,
            "virtue": self.virtue,
            "vice": self.vice,
            "creature_type": self.creature_type,
            "clan": self.clan,
            "covenant": self.covenant,
            "bloodline": self.bloodline,
            "attributes": self.attributes,
            "skills": self.skills,
            "specialties": self.specialties,
            "disciplines": self.disciplines,
            "merits": self.merits,
            "blood_potency": self.blood_potency,
            "vitae": self.vitae,
            "vitae_max": self.vitae_max,
            "vitae_per_turn": self.vitae_per_turn,
            "humanity": self.humanity,
            "health_max": self.health_max,
            "health_current": self.health_current,
            "health_track": self.health_track,
            "willpower_max": self.willpower_max,
            "willpower_current": self.willpower_current,
            "defense": self.defense,
            "initiative_mod": self.initiative_mod,
            "speed": self.speed,
            "size": self.size,
            "armor": self.armor,
            "weapons": self.weapons,
            "inventory": self.inventory,
            "notes": self.notes,
            "backstory": self.backstory,
            "requiem_history": self.requiem_history,
            "creation_complete": self.creation_complete,
            "xp": self.xp,
            "xp_spent": self.xp_spent,
            "beats": self.beats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WoDCharacter":
        c = cls(data["owner_id"], data["owner_name"])
        for key, value in data.items():
            if hasattr(c, key):
                setattr(c, key, value)
        return c

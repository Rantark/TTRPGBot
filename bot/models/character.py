"""Character model for D&D 5e player characters."""

from bot.data.rules import (
    ABILITY_NAMES, ABILITY_FULL_NAMES, SKILLS,
    modifier, modifier_str, proficiency_bonus, xp_for_next_level, calc_ac_unarmored,
)
from bot.data.spells import get_spell_slots


class Character:
    """Represents a D&D 5e player character."""

    def __init__(self, owner_id: str, owner_name: str):
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.name = ""
        self.gender = ""
        self.race = ""
        self.subrace = None
        self.char_class = ""
        self.background = ""
        self.level = 1
        self.xp = 0
        self.abilities = {a: 10 for a in ABILITY_NAMES}
        self.racial_bonuses = {}
        self.max_hp = 0
        self.current_hp = 0
        self.temp_hp = 0
        self.hit_die = 8
        self.hit_dice_remaining = 1
        self.ac = 10
        self.speed = 30
        self.proficiency_bonus = 2
        self.saving_throw_proficiencies = []
        self.skill_proficiencies = []
        self.armor_proficiencies = []
        self.weapon_proficiencies = []
        self.tool_proficiencies = []
        self.languages = []
        self.traits = []
        self.features = []
        self.inventory = []
        self.inspiration = False
        self.death_saves = {"successes": 0, "failures": 0}
        self.conditions = []
        self.notes = ""
        # Dragonborn ancestry
        self.draconic_ancestry = None
        # Half-elf bonus ability choices
        self.half_elf_bonus_abilities = []
        # Spellcasting
        self.spellcasting_ability = ""   # "INT", "WIS", "CHA", or "" if non-caster
        self.spell_slots_max = {}        # {spell_level(int as str): count} — max slots per level
        self.spell_slots_used = {}       # {spell_level(int as str): count} — used slots per level
        self.known_spells = []           # List of spell names the character knows
        self.prepared_spells = []        # List of spell names currently prepared
        self.cantrips = []               # List of cantrip names
        # Creation state tracking
        self.creation_complete = False

    def get_modifier(self, ability: str) -> int:
        return modifier(self.abilities.get(ability, 10))

    def get_modifier_str(self, ability: str) -> str:
        return modifier_str(self.abilities.get(ability, 10))

    def get_skill_modifier(self, skill_name: str) -> int:
        ability = SKILLS.get(skill_name, "STR")
        mod = self.get_modifier(ability)
        if skill_name in self.skill_proficiencies:
            mod += self.proficiency_bonus
        return mod

    def get_save_modifier(self, ability: str) -> int:
        mod = self.get_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            mod += self.proficiency_bonus
        return mod

    def calc_hp(self):
        """Calculate max HP: hit_die at 1st level + CON mod * level."""
        con_mod = self.get_modifier("CON")
        self.max_hp = self.hit_die + con_mod
        # Hill Dwarf bonus
        if self.subrace and "Hill Dwarf" in self.subrace:
            self.max_hp += self.level
        self.current_hp = self.max_hp
        self.hit_dice_remaining = self.level

    def calc_ac(self):
        """Calculate base AC (unarmored)."""
        self.ac = calc_ac_unarmored(self.abilities["DEX"])
        # Barbarian unarmored defense
        if self.char_class == "Barbarian":
            self.ac = 10 + self.get_modifier("DEX") + self.get_modifier("CON")
        # Monk unarmored defense
        elif self.char_class == "Monk":
            self.ac = 10 + self.get_modifier("DEX") + self.get_modifier("WIS")

    def update_proficiency(self):
        self.proficiency_bonus = proficiency_bonus(self.level)

    def update_spell_slots(self):
        """Recalculate spell slots based on class and level."""
        if self.spellcasting_ability:
            slots = get_spell_slots(self.char_class, self.level)
            self.spell_slots_max = {str(k): v for k, v in slots.items()}

    def finalize(self):
        """Call after all creation steps to compute derived stats."""
        self.update_proficiency()
        self.calc_hp()
        self.calc_ac()
        self.update_spell_slots()
        self.creation_complete = True

    def format_sheet(self) -> str:
        """Format a full character sheet for display."""
        sep = "─" * 40
        race_display = self.subrace if self.subrace else self.race
        gender_str = f" ({self.gender})" if self.gender else ""
        lines = [
            f"**{self.name}**{gender_str} — Level {self.level} {race_display} {self.char_class}",
            f"*Background: {self.background}*",
            sep,
            "**Ability Scores**",
        ]
        for ab in ABILITY_NAMES:
            score = self.abilities[ab]
            mod = modifier_str(score)
            save_mod = self.get_save_modifier(ab)
            save_str = f"+{save_mod}" if save_mod >= 0 else str(save_mod)
            prof_mark = " ★" if ab in self.saving_throw_proficiencies else ""
            lines.append(f"  {ABILITY_FULL_NAMES[ab]:14s} {score:2d} ({mod})  Save: {save_str}{prof_mark}")

        lines.append(sep)
        lines.append(f"**HP:** {self.current_hp}/{self.max_hp}  |  **AC:** {self.ac}  |  **Speed:** {self.speed} ft")
        lines.append(f"**Hit Dice:** {self.hit_dice_remaining}d{self.hit_die}  |  **Prof. Bonus:** +{self.proficiency_bonus}")
        lines.append(f"**XP:** {self.xp}/{xp_for_next_level(self.level)}  |  **Inspiration:** {'Yes' if self.inspiration else 'No'}")

        if self.draconic_ancestry:
            lines.append(f"**Draconic Ancestry:** {self.draconic_ancestry}")

        lines.append(sep)
        lines.append("**Skills** (★ = proficient)")
        skill_lines = []
        for skill_name in sorted(SKILLS.keys()):
            mod = self.get_skill_modifier(skill_name)
            mod_s = f"+{mod}" if mod >= 0 else str(mod)
            mark = "★" if skill_name in self.skill_proficiencies else " "
            skill_lines.append(f"  {mark} {skill_name:18s} {mod_s}")
        lines.extend(skill_lines)

        lines.append(sep)
        if self.traits:
            lines.append("**Racial Traits:** " + ", ".join(self.traits))
        if self.features:
            lines.append("**Features:** " + ", ".join(self.features))
        if self.languages:
            lines.append("**Languages:** " + ", ".join(self.languages))

        # Spellcasting section
        if self.spellcasting_ability:
            lines.append(sep)
            spell_mod = self.get_modifier(self.spellcasting_ability)
            spell_save = 8 + self.proficiency_bonus + spell_mod
            spell_atk = self.proficiency_bonus + spell_mod
            spell_atk_str = f"+{spell_atk}" if spell_atk >= 0 else str(spell_atk)
            lines.append(
                f"**Spellcasting** ({self.spellcasting_ability})  |  "
                f"Save DC: {spell_save}  |  Attack: {spell_atk_str}"
            )
            if self.cantrips:
                lines.append(f"**Cantrips:** {', '.join(self.cantrips)}")
            if self.spell_slots_max:
                slot_parts = []
                for lvl in sorted(self.spell_slots_max, key=lambda x: int(x)):
                    used = self.spell_slots_used.get(lvl, 0)
                    total = self.spell_slots_max[lvl]
                    remaining = total - used
                    slot_parts.append(f"Lv{lvl}: {remaining}/{total}")
                lines.append("**Spell Slots:** " + "  ".join(slot_parts))
            if self.prepared_spells:
                lines.append(f"**Prepared:** {', '.join(self.prepared_spells)}")
            if self.known_spells:
                lines.append(f"**Known Spells:** {', '.join(self.known_spells)}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "name": self.name,
            "gender": self.gender,
            "race": self.race,
            "subrace": self.subrace,
            "char_class": self.char_class,
            "background": self.background,
            "level": self.level,
            "xp": self.xp,
            "abilities": self.abilities,
            "racial_bonuses": self.racial_bonuses,
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "temp_hp": self.temp_hp,
            "hit_die": self.hit_die,
            "hit_dice_remaining": self.hit_dice_remaining,
            "ac": self.ac,
            "speed": self.speed,
            "proficiency_bonus": self.proficiency_bonus,
            "saving_throw_proficiencies": self.saving_throw_proficiencies,
            "skill_proficiencies": self.skill_proficiencies,
            "armor_proficiencies": self.armor_proficiencies,
            "weapon_proficiencies": self.weapon_proficiencies,
            "tool_proficiencies": self.tool_proficiencies,
            "languages": self.languages,
            "traits": self.traits,
            "features": self.features,
            "inventory": self.inventory,
            "inspiration": self.inspiration,
            "death_saves": self.death_saves,
            "conditions": self.conditions,
            "notes": self.notes,
            "draconic_ancestry": self.draconic_ancestry,
            "half_elf_bonus_abilities": self.half_elf_bonus_abilities,
            "spellcasting_ability": self.spellcasting_ability,
            "spell_slots_max": self.spell_slots_max,
            "spell_slots_used": self.spell_slots_used,
            "known_spells": self.known_spells,
            "prepared_spells": self.prepared_spells,
            "cantrips": self.cantrips,
            "creation_complete": self.creation_complete,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        c = cls(data["owner_id"], data["owner_name"])
        for key, value in data.items():
            if hasattr(c, key):
                setattr(c, key, value)
        return c

    def short_summary(self) -> str:
        """One-line character summary for DM context."""
        race_display = self.subrace if self.subrace else self.race
        gender_str = f", {self.gender}" if self.gender else ""
        return (f"{self.name} (Level {self.level} {race_display} {self.char_class}{gender_str}, "
                f"HP {self.current_hp}/{self.max_hp}, AC {self.ac})")

"""Character model for D&D 5e player characters."""

import random

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
        self.feats = []               # List of feat names
        self.backstory = ""           # Short character backstory
        self.conditions = []
        self.modifiers = {}           # Named bonuses: {"Shield +2": {"ac": 2}, "Gauntlets of Ogre Power": {"STR": 19}}
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
        # Weapons
        self.weapons = []                # List of weapon dicts from weapons database
        # Creation state tracking
        self.creation_complete = False

    def get_stat_bonus(self, stat: str) -> int:
        """Sum all modifier bonuses for a given stat key (ac, hp, speed, STR, Perception, etc.)."""
        total = 0
        for bonuses in self.modifiers.values():
            total += bonuses.get(stat, 0)
        return total

    def get_effective_ability(self, ability: str) -> int:
        """Get ability score after modifiers are applied."""
        base = self.abilities.get(ability, 10)
        return base + self.get_stat_bonus(ability)

    def get_modifier(self, ability: str) -> int:
        return modifier(self.get_effective_ability(ability))

    def get_modifier_str(self, ability: str) -> str:
        return modifier_str(self.get_effective_ability(ability))

    def get_skill_modifier(self, skill_name: str) -> int:
        ability = SKILLS.get(skill_name, "STR")
        mod = self.get_modifier(ability)
        if skill_name in self.skill_proficiencies:
            mod += self.proficiency_bonus
        # Add direct skill bonuses (e.g., Cloak of Elvenkind +5 to Stealth)
        mod += self.get_stat_bonus(skill_name)
        return mod

    def get_save_modifier(self, ability: str) -> int:
        mod = self.get_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            mod += self.proficiency_bonus
        return mod

    def calc_hp(self):
        """Calculate max HP for current level.

        Level 1: max hit die + CON mod
        Level 2+: roll hit die (min 1) + CON mod per additional level
        """
        con_mod = self.get_modifier("CON")
        # Level 1: max hit die
        self.max_hp = self.hit_die + con_mod
        # Levels 2+: roll hit die for each
        for _ in range(2, self.level + 1):
            hp_roll = random.randint(1, self.hit_die)
            hp_gain = max(hp_roll + con_mod, 1)
            self.max_hp += hp_gain
        # Hill Dwarf bonus (+1 per level)
        if self.subrace and "Hill Dwarf" in self.subrace:
            self.max_hp += self.level
        self.current_hp = self.max_hp
        self.hit_dice_remaining = self.level

    def calc_ac(self):
        """Calculate base AC (unarmored) plus modifier bonuses."""
        self.ac = calc_ac_unarmored(self.get_effective_ability("DEX"))
        # Barbarian unarmored defense
        if self.char_class == "Barbarian":
            self.ac = 10 + self.get_modifier("DEX") + self.get_modifier("CON")
        # Monk unarmored defense
        elif self.char_class == "Monk":
            self.ac = 10 + self.get_modifier("DEX") + self.get_modifier("WIS")
        # Apply AC modifiers (shields, magic items, etc.)
        self.ac += self.get_stat_bonus("ac")

    def update_proficiency(self):
        self.proficiency_bonus = proficiency_bonus(self.level)

    def update_spell_slots(self):
        """Recalculate spell slots based on class and level."""
        if self.spellcasting_ability:
            slots = get_spell_slots(self.char_class, self.level)
            self.spell_slots_max = {str(k): v for k, v in slots.items()}

    def finalize(self, starting_level: int = 1):
        """Call after all creation steps to compute derived stats.

        Args:
            starting_level: The level to create the character at (default 1).
        """
        if starting_level > 1:
            self.level = starting_level
        self.update_proficiency()
        self.calc_hp()
        self.calc_ac()
        self.update_spell_slots()
        self.creation_complete = True

    def _hp_bar(self, width: int = 20) -> str:
        """Generate a visual HP bar."""
        if self.max_hp <= 0:
            return "░" * width
        ratio = max(0, min(self.current_hp / self.max_hp, 1.0))
        filled = round(ratio * width)
        return "█" * filled + "░" * (width - filled)

    def format_sheet(self) -> str:
        """Format a full character sheet for display in Discord."""
        race_display = self.subrace if self.subrace else self.race
        gender_str = f" | {self.gender}" if self.gender else ""
        insp_icon = " ✦ Inspired" if self.inspiration else ""

        # ── Header ──
        lines = [
            f"╔{'═' * 42}╗",
            f"  **⚔ {self.name}**{insp_icon}",
            f"  Level {self.level} {race_display} {self.char_class}{gender_str}",
            f"  *{self.background}*",
            f"╠{'═' * 42}╣",
        ]

        # ── Core Stats Bar ──
        hp_bar = self._hp_bar(16)
        lines.append(f"  ❤ **HP** {self.current_hp}/{self.max_hp}  `{hp_bar}`")
        lines.append(f"  🛡 **AC** {self.ac}   ⚡ **Speed** {self.speed} ft   🎲 **Prof** +{self.proficiency_bonus}")
        lines.append(f"  🎯 **Hit Dice** {self.hit_dice_remaining}d{self.hit_die}   ✨ **XP** {self.xp}/{xp_for_next_level(self.level)}")

        if self.draconic_ancestry:
            lines.append(f"  🐉 **Draconic Ancestry:** {self.draconic_ancestry}")

        # ── Ability Scores (code block for alignment) ──
        lines.append(f"╠{'═' * 42}╣")
        lines.append("  **Ability Scores**  *(★ = save proficiency)*")
        lines.append("```")
        for ab in ABILITY_NAMES:
            score = self.abilities[ab]
            mod = modifier_str(score)
            save_mod = self.get_save_modifier(ab)
            save_str = f"+{save_mod}" if save_mod >= 0 else str(save_mod)
            prof_mark = " ★" if ab in self.saving_throw_proficiencies else "  "
            lines.append(f"  {ABILITY_FULL_NAMES[ab]:<14s} {score:2d} ({mod:>3s})  Save {save_str:>3s}{prof_mark}")
        lines.append("```")

        # ── Skills (two columns in code block) ──
        lines.append(f"╠{'═' * 42}╣")
        lines.append("  **Skills**  *(★ = proficient)*")
        lines.append("```")
        sorted_skills = sorted(SKILLS.keys())
        mid = (len(sorted_skills) + 1) // 2
        col1 = sorted_skills[:mid]
        col2 = sorted_skills[mid:]
        for i in range(mid):
            sk1 = col1[i]
            mod1 = self.get_skill_modifier(sk1)
            m1 = f"+{mod1}" if mod1 >= 0 else str(mod1)
            mark1 = "★" if sk1 in self.skill_proficiencies else " "
            left = f"{mark1} {sk1:<16s}{m1:>3s}"
            if i < len(col2):
                sk2 = col2[i]
                mod2 = self.get_skill_modifier(sk2)
                m2 = f"+{mod2}" if mod2 >= 0 else str(mod2)
                mark2 = "★" if sk2 in self.skill_proficiencies else " "
                right = f"{mark2} {sk2:<16s}{m2:>3s}"
            else:
                right = ""
            lines.append(f" {left}  {right}")
        lines.append("```")

        # ── Traits, Features, Feats & Modifiers ──
        if self.traits or self.features or self.feats or self.languages or self.modifiers:
            lines.append(f"╠{'═' * 42}╣")
            if self.traits:
                lines.append(f"  📜 **Traits:** {', '.join(self.traits)}")
            if self.features:
                lines.append(f"  ⭐ **Features:** {', '.join(self.features)}")
            if self.feats:
                lines.append(f"  🏅 **Feats:** {', '.join(self.feats)}")
            if self.languages:
                lines.append(f"  💬 **Languages:** {', '.join(self.languages)}")
            if self.modifiers:
                mod_strs = []
                for source, bonuses in self.modifiers.items():
                    parts = []
                    for stat, val in bonuses.items():
                        sign = "+" if val >= 0 else ""
                        parts.append(f"{stat} {sign}{val}")
                    mod_strs.append(f"{source} ({', '.join(parts)})")
                lines.append(f"  🔧 **Modifiers:** {', '.join(mod_strs)}")

        # ── Weapons ──
        if self.weapons:
            lines.append(f"╠{'═' * 42}╣")
            lines.append("  **Weapons**")
            for w in self.weapons:
                is_finesse = w.get('finesse', False)
                is_ranged = w.get('category') == 'ranged'
                if is_finesse or is_ranged:
                    ab_mod = self.get_modifier("DEX")
                else:
                    ab_mod = self.get_modifier("STR")
                atk_bonus = ab_mod + self.proficiency_bonus
                atk_str = f"+{atk_bonus}" if atk_bonus >= 0 else str(atk_bonus)
                dmg_str = f"+{ab_mod}" if ab_mod >= 0 else str(ab_mod)
                props = f" ({', '.join(w['properties'])})" if w.get('properties') else ""
                lines.append(f"  • **{w['name']}** Atk {atk_str} | {w['damage']}{dmg_str} {w['damage_type']}{props}")

        # ── Spellcasting ──
        if self.spellcasting_ability:
            lines.append(f"╠{'═' * 42}╣")
            spell_mod = self.get_modifier(self.spellcasting_ability)
            spell_save = 8 + self.proficiency_bonus + spell_mod
            spell_atk = self.proficiency_bonus + spell_mod
            atk_str = f"+{spell_atk}" if spell_atk >= 0 else str(spell_atk)
            lines.append(
                f"  🔮 **Spellcasting** ({self.spellcasting_ability})"
                f"  |  DC **{spell_save}**  |  Atk **{atk_str}**"
            )
            if self.cantrips:
                lines.append(f"  **Cantrips:** {', '.join(self.cantrips)}")
            if self.spell_slots_max:
                for lvl in sorted(self.spell_slots_max, key=lambda x: int(x)):
                    used = self.spell_slots_used.get(lvl, 0)
                    total = self.spell_slots_max[lvl]
                    remaining = total - used
                    pips = "◆" * remaining + "◇" * used
                    lines.append(f"  **Lv{lvl}:** {pips}")
            if self.prepared_spells:
                lines.append(f"  📖 **Prepared:** {', '.join(self.prepared_spells)}")
            if self.known_spells:
                lines.append(f"  📚 **Known:** {', '.join(self.known_spells)}")

        # ── Footer ──
        lines.append(f"╚{'═' * 42}╝")

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
            "feats": self.feats,
            "modifiers": self.modifiers,
            "backstory": self.backstory,
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
            "weapons": self.weapons,
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
        summary = (f"{self.name} (Level {self.level} {race_display} {self.char_class}{gender_str}, "
                   f"HP {self.current_hp}/{self.max_hp}, AC {self.ac})")
        if self.inventory:
            summary += f" Equipment: {', '.join(self.inventory[:8])}"
            if len(self.inventory) > 8:
                summary += f" (+{len(self.inventory) - 8} more)"
        return summary

    def full_context(self) -> str:
        """Full character context for the DM, including backstory and equipment."""
        lines = [self.short_summary()]
        if self.backstory:
            lines.append(f"  Backstory: {self.backstory}")
        if self.feats:
            lines.append(f"  Feats: {', '.join(self.feats)}")
        if self.known_spells:
            lines.append(f"  Known Spells: {', '.join(self.known_spells)}")
        return "\n".join(lines)

    def dm_stat_block(self) -> str:
        """Detailed stat block for DM context — gives Claude full visibility."""
        if not self.creation_complete:
            return f"- {self.owner_name} — *Creating character...*"

        race_display = self.subrace if self.subrace else self.race
        gender_str = f", {self.gender}" if self.gender else ""

        lines = [f"- {self.name} ({race_display} {self.char_class} {self.level}{gender_str})"]
        lines.append(f"  HP: {self.current_hp}/{self.max_hp} | AC: {self.ac} | Prof: +{self.proficiency_bonus}")

        # Ability modifiers
        ab_strs = []
        for ab in ABILITY_NAMES:
            ab_strs.append(f"{ab} {modifier_str(self.abilities[ab])}")
        lines.append(f"  {', '.join(ab_strs)}")

        # Key skill modifiers
        key_skills = ["Perception", "Investigation", "Stealth", "Insight", "Athletics", "Arcana"]
        skill_strs = []
        for sk in key_skills:
            mod = self.get_skill_modifier(sk)
            prof = "★" if sk in self.skill_proficiencies else ""
            mod_s = f"+{mod}" if mod >= 0 else str(mod)
            skill_strs.append(f"{sk} {mod_s}{prof}")
        lines.append(f"  {', '.join(skill_strs)}")

        # Passive scores
        passive_perc = 10 + self.get_skill_modifier("Perception")
        passive_inv = 10 + self.get_skill_modifier("Investigation")
        lines.append(f"  Passive Perception: {passive_perc}, Passive Investigation: {passive_inv}")

        # Conditions
        if self.conditions:
            lines.append(f"  Conditions: {', '.join(self.conditions)}")

        # Spellcasting summary
        if self.spellcasting_ability:
            spell_mod = self.get_modifier(self.spellcasting_ability)
            spell_dc = 8 + self.proficiency_bonus + spell_mod
            spell_atk = self.proficiency_bonus + spell_mod
            atk_str = f"+{spell_atk}" if spell_atk >= 0 else str(spell_atk)
            lines.append(f"  Spellcasting ({self.spellcasting_ability}): DC {spell_dc}, Atk {atk_str}")
            if self.prepared_spells:
                lines.append(f"  Prepared: {', '.join(self.prepared_spells)}")

        # Active modifiers
        if self.modifiers:
            mod_strs = []
            for source, bonuses in self.modifiers.items():
                parts = [f"{s} {'+' if v >= 0 else ''}{v}" for s, v in bonuses.items()]
                mod_strs.append(f"{source} ({', '.join(parts)})")
            lines.append(f"  Modifiers: {', '.join(mod_strs)}")

        # Equipment highlights (first 5)
        if self.inventory:
            equip = ', '.join(self.inventory[:5])
            extra = f" (+{len(self.inventory) - 5} more)" if len(self.inventory) > 5 else ""
            lines.append(f"  Equipment: {equip}{extra}")

        # Backstory
        if self.backstory:
            lines.append(f"  Backstory: {self.backstory}")

        return "\n".join(lines)

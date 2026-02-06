"""D&D 5e rules constants and helper calculations."""

ABILITY_NAMES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
ABILITY_FULL_NAMES = {
    "STR": "Strength", "DEX": "Dexterity", "CON": "Constitution",
    "INT": "Intelligence", "WIS": "Wisdom", "CHA": "Charisma",
}

SKILLS = {
    "Acrobatics": "DEX", "Animal Handling": "WIS", "Arcana": "INT",
    "Athletics": "STR", "Deception": "CHA", "History": "INT",
    "Insight": "WIS", "Intimidation": "CHA", "Investigation": "INT",
    "Medicine": "WIS", "Nature": "INT", "Perception": "WIS",
    "Performance": "CHA", "Persuasion": "CHA", "Religion": "INT",
    "Sleight of Hand": "DEX", "Stealth": "DEX", "Survival": "WIS",
}

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27

# Proficiency bonus by level
PROFICIENCY_BONUS = {
    1: 2, 2: 2, 3: 2, 4: 2,
    5: 3, 6: 3, 7: 3, 8: 3,
    9: 4, 10: 4, 11: 4, 12: 4,
    13: 5, 14: 5, 15: 5, 16: 5,
    17: 6, 18: 6, 19: 6, 20: 6,
}

# XP thresholds per level
XP_THRESHOLDS = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
    11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
    16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}


def modifier(score: int) -> int:
    return (score - 10) // 2


def modifier_str(score: int) -> str:
    mod = modifier(score)
    return f"+{mod}" if mod >= 0 else str(mod)


def proficiency_bonus(level: int) -> int:
    return PROFICIENCY_BONUS.get(level, 2)


def xp_for_next_level(current_level: int) -> int:
    next_lvl = current_level + 1
    if next_lvl > 20:
        return 0
    return XP_THRESHOLDS.get(next_lvl, 0)


def calc_ac_unarmored(dex_score: int) -> int:
    return 10 + modifier(dex_score)

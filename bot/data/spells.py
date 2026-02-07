"""D&D 5e spell slot tables and spellcasting rules.

Covers full casters (Bard, Cleric, Druid, Sorcerer, Wizard),
half casters (Paladin, Ranger), and pact magic (Warlock).
"""

# Full caster spell slots by level (Bard, Cleric, Druid, Sorcerer, Wizard)
# Format: {class_level: {spell_level: num_slots}}
FULL_CASTER_SLOTS = {
    1:  {1: 2},
    2:  {1: 3},
    3:  {1: 4, 2: 2},
    4:  {1: 4, 2: 3},
    5:  {1: 4, 2: 3, 3: 2},
    6:  {1: 4, 2: 3, 3: 3},
    7:  {1: 4, 2: 3, 3: 3, 4: 1},
    8:  {1: 4, 2: 3, 3: 3, 4: 2},
    9:  {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}

# Half caster spell slots by level (Paladin, Ranger)
# They get slots starting at level 2
HALF_CASTER_SLOTS = {
    1:  {},
    2:  {1: 2},
    3:  {1: 3},
    4:  {1: 3},
    5:  {1: 4, 2: 2},
    6:  {1: 4, 2: 2},
    7:  {1: 4, 2: 3},
    8:  {1: 4, 2: 3},
    9:  {1: 4, 2: 3, 3: 2},
    10: {1: 4, 2: 3, 3: 2},
    11: {1: 4, 2: 3, 3: 3},
    12: {1: 4, 2: 3, 3: 3},
    13: {1: 4, 2: 3, 3: 3, 4: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 2},
    16: {1: 4, 2: 3, 3: 3, 4: 2},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

# Warlock pact magic — different system: fewer slots, all same level, recover on short rest
# Format: {class_level: {"slots": num, "slot_level": level}}
WARLOCK_PACT_SLOTS = {
    1:  {"slots": 1, "slot_level": 1},
    2:  {"slots": 2, "slot_level": 1},
    3:  {"slots": 2, "slot_level": 2},
    4:  {"slots": 2, "slot_level": 2},
    5:  {"slots": 2, "slot_level": 3},
    6:  {"slots": 2, "slot_level": 3},
    7:  {"slots": 2, "slot_level": 4},
    8:  {"slots": 2, "slot_level": 4},
    9:  {"slots": 2, "slot_level": 5},
    10: {"slots": 2, "slot_level": 5},
    11: {"slots": 3, "slot_level": 5},
    12: {"slots": 3, "slot_level": 5},
    13: {"slots": 3, "slot_level": 5},
    14: {"slots": 3, "slot_level": 5},
    15: {"slots": 3, "slot_level": 5},
    16: {"slots": 3, "slot_level": 5},
    17: {"slots": 4, "slot_level": 5},
    18: {"slots": 4, "slot_level": 5},
    19: {"slots": 4, "slot_level": 5},
    20: {"slots": 4, "slot_level": 5},
}

# Cantrips known by class and level
CANTRIPS_KNOWN = {
    "Bard":     {1: 2, 4: 3, 10: 4},
    "Cleric":   {1: 3, 4: 4, 10: 5},
    "Druid":    {1: 2, 4: 3, 10: 4},
    "Sorcerer": {1: 4, 4: 5, 10: 6},
    "Warlock":  {1: 2, 4: 3, 10: 4},
    "Wizard":   {1: 3, 4: 4, 10: 5},
}

# Which classes use which slot table
FULL_CASTERS = {"Bard", "Cleric", "Druid", "Sorcerer", "Wizard"}
HALF_CASTERS = {"Paladin", "Ranger"}
PACT_CASTERS = {"Warlock"}
NON_CASTERS = {"Barbarian", "Fighter", "Monk", "Rogue"}

SPELL_LEVEL_NAMES = {
    0: "Cantrip", 1: "1st", 2: "2nd", 3: "3rd",
    4: "4th", 5: "5th", 6: "6th", 7: "7th", 8: "8th", 9: "9th",
}


def get_spell_slots(char_class: str, level: int) -> dict[int, int]:
    """Return {spell_level: num_slots} for the given class and level."""
    if char_class in FULL_CASTERS:
        return dict(FULL_CASTER_SLOTS.get(level, {}))
    elif char_class in HALF_CASTERS:
        return dict(HALF_CASTER_SLOTS.get(level, {}))
    elif char_class in PACT_CASTERS:
        pact = WARLOCK_PACT_SLOTS.get(level, {"slots": 0, "slot_level": 1})
        if pact["slots"] > 0:
            return {pact["slot_level"]: pact["slots"]}
        return {}
    return {}


def get_max_spell_level(char_class: str, level: int) -> int:
    """Return the highest spell level available for this class/level."""
    slots = get_spell_slots(char_class, level)
    if not slots:
        return 0
    return max(slots.keys())


def get_cantrips_known(char_class: str, level: int) -> int:
    """Return how many cantrips this class knows at this level."""
    table = CANTRIPS_KNOWN.get(char_class)
    if not table:
        return 0
    result = 0
    for threshold_level, count in sorted(table.items()):
        if level >= threshold_level:
            result = count
    return result


def is_spellcaster(char_class: str) -> bool:
    """Return True if this class has spellcasting."""
    return char_class not in NON_CASTERS


def is_pact_caster(char_class: str) -> bool:
    return char_class in PACT_CASTERS

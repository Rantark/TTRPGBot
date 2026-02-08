"""D&D 5e armor database for AC calculation."""

# Armor types: name -> {base_ac, type, stealth_disadvantage}
# type: "light", "medium", "heavy"
#   light: base + full DEX mod
#   medium: base + DEX mod (max +2)
#   heavy: base only (no DEX)

ARMOR = {
    # Light Armor
    "Padded": {"base_ac": 11, "type": "light", "stealth_disadvantage": True},
    "Leather": {"base_ac": 11, "type": "light", "stealth_disadvantage": False},
    "Studded Leather": {"base_ac": 12, "type": "light", "stealth_disadvantage": False},
    # Medium Armor
    "Hide": {"base_ac": 12, "type": "medium", "stealth_disadvantage": False},
    "Chain Shirt": {"base_ac": 13, "type": "medium", "stealth_disadvantage": False},
    "Scale Mail": {"base_ac": 14, "type": "medium", "stealth_disadvantage": True},
    "Breastplate": {"base_ac": 14, "type": "medium", "stealth_disadvantage": False},
    "Half Plate": {"base_ac": 15, "type": "medium", "stealth_disadvantage": True},
    # Heavy Armor
    "Ring Mail": {"base_ac": 14, "type": "heavy", "stealth_disadvantage": True},
    "Chain Mail": {"base_ac": 16, "type": "heavy", "stealth_disadvantage": True},
    "Splint": {"base_ac": 17, "type": "heavy", "stealth_disadvantage": True},
    "Plate": {"base_ac": 18, "type": "heavy", "stealth_disadvantage": True},
}

# Starting armor per class (what they get during character creation)
CLASS_STARTING_ARMOR = {
    "Barbarian": None,           # Unarmored Defense
    "Bard": "Leather",
    "Cleric": "Scale Mail",
    "Druid": "Leather",
    "Fighter": "Chain Mail",
    "Monk": None,                # Unarmored Defense
    "Paladin": "Chain Mail",
    "Ranger": "Scale Mail",
    "Rogue": "Leather",
    "Sorcerer": None,
    "Warlock": "Leather",
    "Wizard": None,
}

# Classes that start with a shield
CLASS_STARTING_SHIELD = {
    "Cleric": True,
    "Druid": True,
    "Fighter": True,
    "Paladin": True,
}


def get_armor(name: str) -> dict | None:
    """Look up armor by name (case-insensitive)."""
    for armor_name, data in ARMOR.items():
        if armor_name.lower() == name.lower():
            return {"name": armor_name, **data}
    return None


def calc_armor_ac(armor_name: str, dex_mod: int) -> int:
    """Calculate AC for a given armor and DEX modifier."""
    armor = get_armor(armor_name)
    if not armor:
        return 10 + dex_mod  # Unarmored
    if armor["type"] == "light":
        return armor["base_ac"] + dex_mod
    elif armor["type"] == "medium":
        return armor["base_ac"] + min(dex_mod, 2)
    else:  # heavy
        return armor["base_ac"]

"""D&D 5e consumables with automatic effects."""

CONSUMABLES = {
    "potion of healing": {
        "name": "Potion of Healing",
        "effect_type": "heal",
        "dice": "2d4",
        "bonus": 2,
        "description": "Heals 2d4+2 HP",
    },
    "potion of greater healing": {
        "name": "Potion of Greater Healing",
        "effect_type": "heal",
        "dice": "4d4",
        "bonus": 4,
        "description": "Heals 4d4+4 HP",
    },
    "potion of superior healing": {
        "name": "Potion of Superior Healing",
        "effect_type": "heal",
        "dice": "8d4",
        "bonus": 8,
        "description": "Heals 8d4+8 HP",
    },
    "potion of supreme healing": {
        "name": "Potion of Supreme Healing",
        "effect_type": "heal",
        "dice": "10d4",
        "bonus": 20,
        "description": "Heals 10d4+20 HP",
    },
    "antitoxin": {
        "name": "Antitoxin",
        "effect_type": "remove_condition",
        "condition": "poisoned",
        "description": "Removes the poisoned condition",
    },
}


def get_consumable(item_name: str) -> dict | None:
    """Look up a consumable by name (case-insensitive)."""
    return CONSUMABLES.get(item_name.lower())

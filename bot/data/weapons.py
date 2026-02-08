"""D&D 5e weapons database."""

WEAPONS = {
    # Simple Melee Weapons
    'club': {
        'name': 'Club', 'damage': '1d4', 'damage_type': 'bludgeoning',
        'properties': ['Light'], 'weapon_type': 'simple', 'category': 'melee',
        'finesse': False,
    },
    'dagger': {
        'name': 'Dagger', 'damage': '1d4', 'damage_type': 'piercing',
        'properties': ['Finesse', 'Light', 'Thrown (20/60)'],
        'weapon_type': 'simple', 'category': 'melee', 'finesse': True,
    },
    'greatclub': {
        'name': 'Greatclub', 'damage': '1d8', 'damage_type': 'bludgeoning',
        'properties': ['Two-handed'], 'weapon_type': 'simple', 'category': 'melee',
        'finesse': False,
    },
    'handaxe': {
        'name': 'Handaxe', 'damage': '1d6', 'damage_type': 'slashing',
        'properties': ['Light', 'Thrown (20/60)'],
        'weapon_type': 'simple', 'category': 'melee', 'finesse': False,
    },
    'javelin': {
        'name': 'Javelin', 'damage': '1d6', 'damage_type': 'piercing',
        'properties': ['Thrown (30/120)'],
        'weapon_type': 'simple', 'category': 'melee', 'finesse': False,
    },
    'light hammer': {
        'name': 'Light Hammer', 'damage': '1d4', 'damage_type': 'bludgeoning',
        'properties': ['Light', 'Thrown (20/60)'],
        'weapon_type': 'simple', 'category': 'melee', 'finesse': False,
    },
    'mace': {
        'name': 'Mace', 'damage': '1d6', 'damage_type': 'bludgeoning',
        'properties': [], 'weapon_type': 'simple', 'category': 'melee',
        'finesse': False,
    },
    'quarterstaff': {
        'name': 'Quarterstaff', 'damage': '1d6', 'damage_type': 'bludgeoning',
        'properties': ['Versatile (1d8)'],
        'weapon_type': 'simple', 'category': 'melee', 'finesse': False,
    },
    'sickle': {
        'name': 'Sickle', 'damage': '1d4', 'damage_type': 'slashing',
        'properties': ['Light'], 'weapon_type': 'simple', 'category': 'melee',
        'finesse': False,
    },
    'spear': {
        'name': 'Spear', 'damage': '1d6', 'damage_type': 'piercing',
        'properties': ['Thrown (20/60)', 'Versatile (1d8)'],
        'weapon_type': 'simple', 'category': 'melee', 'finesse': False,
    },
    # Simple Ranged Weapons
    'light crossbow': {
        'name': 'Light Crossbow', 'damage': '1d8', 'damage_type': 'piercing',
        'properties': ['Ammunition (80/320)', 'Loading', 'Two-handed'],
        'weapon_type': 'simple', 'category': 'ranged', 'finesse': False,
    },
    'dart': {
        'name': 'Dart', 'damage': '1d4', 'damage_type': 'piercing',
        'properties': ['Finesse', 'Thrown (20/60)'],
        'weapon_type': 'simple', 'category': 'ranged', 'finesse': True,
    },
    'shortbow': {
        'name': 'Shortbow', 'damage': '1d6', 'damage_type': 'piercing',
        'properties': ['Ammunition (80/320)', 'Two-handed'],
        'weapon_type': 'simple', 'category': 'ranged', 'finesse': False,
    },
    'sling': {
        'name': 'Sling', 'damage': '1d4', 'damage_type': 'bludgeoning',
        'properties': ['Ammunition (30/120)'],
        'weapon_type': 'simple', 'category': 'ranged', 'finesse': False,
    },
    # Martial Melee Weapons
    'battleaxe': {
        'name': 'Battleaxe', 'damage': '1d8', 'damage_type': 'slashing',
        'properties': ['Versatile (1d10)'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'flail': {
        'name': 'Flail', 'damage': '1d8', 'damage_type': 'bludgeoning',
        'properties': [], 'weapon_type': 'martial', 'category': 'melee',
        'finesse': False,
    },
    'glaive': {
        'name': 'Glaive', 'damage': '1d10', 'damage_type': 'slashing',
        'properties': ['Heavy', 'Reach', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'greataxe': {
        'name': 'Greataxe', 'damage': '1d12', 'damage_type': 'slashing',
        'properties': ['Heavy', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'greatsword': {
        'name': 'Greatsword', 'damage': '2d6', 'damage_type': 'slashing',
        'properties': ['Heavy', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'halberd': {
        'name': 'Halberd', 'damage': '1d10', 'damage_type': 'slashing',
        'properties': ['Heavy', 'Reach', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'lance': {
        'name': 'Lance', 'damage': '1d12', 'damage_type': 'piercing',
        'properties': ['Reach', 'Special'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'longsword': {
        'name': 'Longsword', 'damage': '1d8', 'damage_type': 'slashing',
        'properties': ['Versatile (1d10)'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'maul': {
        'name': 'Maul', 'damage': '2d6', 'damage_type': 'bludgeoning',
        'properties': ['Heavy', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'morningstar': {
        'name': 'Morningstar', 'damage': '1d8', 'damage_type': 'piercing',
        'properties': [], 'weapon_type': 'martial', 'category': 'melee',
        'finesse': False,
    },
    'pike': {
        'name': 'Pike', 'damage': '1d10', 'damage_type': 'piercing',
        'properties': ['Heavy', 'Reach', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'rapier': {
        'name': 'Rapier', 'damage': '1d8', 'damage_type': 'piercing',
        'properties': ['Finesse'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': True,
    },
    'scimitar': {
        'name': 'Scimitar', 'damage': '1d6', 'damage_type': 'slashing',
        'properties': ['Finesse', 'Light'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': True,
    },
    'shortsword': {
        'name': 'Shortsword', 'damage': '1d6', 'damage_type': 'piercing',
        'properties': ['Finesse', 'Light'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': True,
    },
    'trident': {
        'name': 'Trident', 'damage': '1d6', 'damage_type': 'piercing',
        'properties': ['Thrown (20/60)', 'Versatile (1d8)'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'war pick': {
        'name': 'War Pick', 'damage': '1d8', 'damage_type': 'piercing',
        'properties': [], 'weapon_type': 'martial', 'category': 'melee',
        'finesse': False,
    },
    'warhammer': {
        'name': 'Warhammer', 'damage': '1d8', 'damage_type': 'bludgeoning',
        'properties': ['Versatile (1d10)'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': False,
    },
    'whip': {
        'name': 'Whip', 'damage': '1d4', 'damage_type': 'slashing',
        'properties': ['Finesse', 'Reach'],
        'weapon_type': 'martial', 'category': 'melee', 'finesse': True,
    },
    # Martial Ranged Weapons
    'hand crossbow': {
        'name': 'Hand Crossbow', 'damage': '1d6', 'damage_type': 'piercing',
        'properties': ['Ammunition (30/120)', 'Light', 'Loading'],
        'weapon_type': 'martial', 'category': 'ranged', 'finesse': False,
    },
    'heavy crossbow': {
        'name': 'Heavy Crossbow', 'damage': '1d10', 'damage_type': 'piercing',
        'properties': ['Ammunition (100/400)', 'Heavy', 'Loading', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'ranged', 'finesse': False,
    },
    'longbow': {
        'name': 'Longbow', 'damage': '1d8', 'damage_type': 'piercing',
        'properties': ['Ammunition (150/600)', 'Heavy', 'Two-handed'],
        'weapon_type': 'martial', 'category': 'ranged', 'finesse': False,
    },
}


# Starting weapon choices per class — each class has a list of choice groups.
# Each choice group is a list of weapon keys the player picks one from.
CLASS_STARTING_WEAPONS = {
    "Barbarian": [
        {"label": "Primary weapon", "options": ["greataxe", "battleaxe", "longsword", "warhammer", "maul", "greatsword"]},
        {"label": "Secondary weapon", "options": ["handaxe", "javelin", "spear"]},
    ],
    "Bard": [
        {"label": "Weapon", "options": ["rapier", "longsword", "shortsword", "dagger"]},
    ],
    "Cleric": [
        {"label": "Weapon", "options": ["mace", "warhammer", "quarterstaff"]},
    ],
    "Druid": [
        {"label": "Weapon", "options": ["quarterstaff", "scimitar", "club", "dagger", "spear"]},
    ],
    "Fighter": [
        {"label": "Primary weapon", "options": ["longsword", "battleaxe", "warhammer", "greatsword", "greataxe", "rapier"]},
        {"label": "Ranged weapon", "options": ["light crossbow", "longbow", "handaxe", "javelin"]},
    ],
    "Monk": [
        {"label": "Weapon", "options": ["shortsword", "quarterstaff", "spear", "handaxe"]},
    ],
    "Paladin": [
        {"label": "Primary weapon", "options": ["longsword", "battleaxe", "warhammer", "greatsword", "greataxe", "rapier", "morningstar"]},
        {"label": "Secondary weapon", "options": ["javelin", "handaxe", "spear", "mace"]},
    ],
    "Ranger": [
        {"label": "Melee weapon", "options": ["shortsword", "scimitar", "handaxe", "dagger"]},
        {"label": "Ranged weapon", "options": ["longbow", "shortbow"]},
    ],
    "Rogue": [
        {"label": "Primary weapon", "options": ["rapier", "shortsword"]},
        {"label": "Ranged weapon", "options": ["shortbow", "hand crossbow"]},
    ],
    "Sorcerer": [
        {"label": "Weapon", "options": ["light crossbow", "quarterstaff", "dagger"]},
    ],
    "Warlock": [
        {"label": "Weapon", "options": ["light crossbow", "quarterstaff", "dagger", "spear"]},
    ],
    "Wizard": [
        {"label": "Weapon", "options": ["quarterstaff", "dagger"]},
    ],
}


def get_weapon(key: str) -> dict | None:
    """Get weapon data by key."""
    return WEAPONS.get(key.lower())


def get_weapons_by_type(weapon_type: str = None, category: str = None) -> list[str]:
    """Get weapon keys filtered by type and/or category."""
    results = []
    for key, w in WEAPONS.items():
        if weapon_type and w['weapon_type'] != weapon_type:
            continue
        if category and w['category'] != category:
            continue
        results.append(key)
    return results

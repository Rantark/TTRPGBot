"""D&D 5th Edition PHB races and subraces with ability score bonuses and traits."""

# Each race: { name, subraces (optional), ability_bonuses, speed, traits, languages }
# ability_bonuses: {ability: bonus}  -- subraces add on top of race bonuses.

RACES = {
    "Dwarf": {
        "ability_bonuses": {"CON": 2},
        "speed": 25,
        "traits": ["Darkvision (60 ft)", "Dwarven Resilience (advantage vs poison, resistance to poison damage)",
                    "Stonecunning (History checks on stonework)"],
        "languages": ["Common", "Dwarvish"],
        "subraces": {
            "Hill Dwarf": {
                "ability_bonuses": {"WIS": 1},
                "traits": ["Dwarven Toughness (+1 HP per level)"],
            },
            "Mountain Dwarf": {
                "ability_bonuses": {"STR": 2},
                "traits": ["Dwarven Armor Training (light & medium armor proficiency)"],
            },
        },
    },
    "Elf": {
        "ability_bonuses": {"DEX": 2},
        "speed": 30,
        "traits": ["Darkvision (60 ft)", "Keen Senses (Perception proficiency)",
                    "Fey Ancestry (advantage vs charm, immune to magical sleep)",
                    "Trance (4 hours instead of 8 hours sleep)"],
        "languages": ["Common", "Elvish"],
        "subraces": {
            "High Elf": {
                "ability_bonuses": {"INT": 1},
                "traits": ["Elf Weapon Training (longsword, shortsword, shortbow, longbow)",
                           "Cantrip (one wizard cantrip, INT-based)",
                           "Extra Language (one additional language)"],
            },
            "Wood Elf": {
                "ability_bonuses": {"WIS": 1},
                "traits": ["Elf Weapon Training (longsword, shortsword, shortbow, longbow)",
                           "Fleet of Foot (speed 35 ft)",
                           "Mask of the Wild (hide in light natural obscurement)"],
            },
            "Dark Elf (Drow)": {
                "ability_bonuses": {"CHA": 1},
                "traits": ["Superior Darkvision (120 ft)",
                           "Sunlight Sensitivity (disadvantage on attacks/perception in direct sunlight)",
                           "Drow Magic (dancing lights cantrip; faerie fire at 3rd, darkness at 5th)",
                           "Drow Weapon Training (rapiers, shortswords, hand crossbows)"],
            },
        },
    },
    "Halfling": {
        "ability_bonuses": {"DEX": 2},
        "speed": 25,
        "traits": ["Lucky (reroll natural 1s on attacks, checks, saves)",
                    "Brave (advantage vs frightened)",
                    "Halfling Nimbleness (move through larger creature spaces)"],
        "languages": ["Common", "Halfling"],
        "subraces": {
            "Lightfoot Halfling": {
                "ability_bonuses": {"CHA": 1},
                "traits": ["Naturally Stealthy (hide behind medium+ creatures)"],
            },
            "Stout Halfling": {
                "ability_bonuses": {"CON": 1},
                "traits": ["Stout Resilience (advantage vs poison, resistance to poison damage)"],
            },
        },
    },
    "Human": {
        "ability_bonuses": {"STR": 1, "DEX": 1, "CON": 1, "INT": 1, "WIS": 1, "CHA": 1},
        "speed": 30,
        "traits": ["Extra Language (one additional language)"],
        "languages": ["Common"],
        "subraces": {},
    },
    "Dragonborn": {
        "ability_bonuses": {"STR": 2, "CHA": 1},
        "speed": 30,
        "traits": ["Draconic Ancestry (choose dragon type for breath weapon & resistance)",
                    "Breath Weapon (damage based on ancestry)",
                    "Damage Resistance (based on ancestry)"],
        "languages": ["Common", "Draconic"],
        "subraces": {},
    },
    "Gnome": {
        "ability_bonuses": {"INT": 2},
        "speed": 25,
        "traits": ["Darkvision (60 ft)",
                    "Gnome Cunning (advantage on INT/WIS/CHA saves vs magic)"],
        "languages": ["Common", "Gnomish"],
        "subraces": {
            "Forest Gnome": {
                "ability_bonuses": {"DEX": 1},
                "traits": ["Natural Illusionist (minor illusion cantrip)",
                           "Speak with Small Beasts"],
            },
            "Rock Gnome": {
                "ability_bonuses": {"CON": 1},
                "traits": ["Artificer's Lore (double prof on History for magic/tech items)",
                           "Tinker (create tiny clockwork devices)"],
            },
        },
    },
    "Half-Elf": {
        "ability_bonuses": {"CHA": 2},  # +1 to two others chosen at creation
        "speed": 30,
        "traits": ["Darkvision (60 ft)",
                    "Fey Ancestry (advantage vs charm, immune to magical sleep)",
                    "Skill Versatility (two extra skill proficiencies)",
                    "+1 to two ability scores of your choice (other than CHA)"],
        "languages": ["Common", "Elvish"],
        "subraces": {},
    },
    "Half-Orc": {
        "ability_bonuses": {"STR": 2, "CON": 1},
        "speed": 30,
        "traits": ["Darkvision (60 ft)",
                    "Menacing (Intimidation proficiency)",
                    "Relentless Endurance (drop to 1 HP instead of 0, once per long rest)",
                    "Savage Attacks (extra damage die on melee crit)"],
        "languages": ["Common", "Orc"],
        "subraces": {},
    },
    "Tiefling": {
        "ability_bonuses": {"CHA": 2, "INT": 1},
        "speed": 30,
        "traits": ["Darkvision (60 ft)",
                    "Hellish Resistance (resistance to fire damage)",
                    "Infernal Legacy (thaumaturgy cantrip; hellish rebuke at 3rd, darkness at 5th)"],
        "languages": ["Common", "Infernal"],
        "subraces": {},
    },
}

DRACONIC_ANCESTRIES = {
    "Black": {"damage_type": "Acid", "breath": "5x30 ft line (DEX save)"},
    "Blue": {"damage_type": "Lightning", "breath": "5x30 ft line (DEX save)"},
    "Brass": {"damage_type": "Fire", "breath": "5x30 ft line (DEX save)"},
    "Bronze": {"damage_type": "Lightning", "breath": "5x30 ft line (DEX save)"},
    "Copper": {"damage_type": "Acid", "breath": "5x30 ft line (DEX save)"},
    "Gold": {"damage_type": "Fire", "breath": "15 ft cone (DEX save)"},
    "Green": {"damage_type": "Poison", "breath": "15 ft cone (CON save)"},
    "Red": {"damage_type": "Fire", "breath": "15 ft cone (DEX save)"},
    "Silver": {"damage_type": "Cold", "breath": "15 ft cone (CON save)"},
    "White": {"damage_type": "Cold", "breath": "15 ft cone (CON save)"},
}


def get_race_names():
    """Return a flat list of all playable race/subrace names."""
    names = []
    for race_name, race_data in RACES.items():
        if race_data.get("subraces"):
            for sub_name in race_data["subraces"]:
                names.append(sub_name)
        else:
            names.append(race_name)
    return sorted(names)


def resolve_race(choice: str):
    """Given a race/subrace name, return merged ability bonuses, speed, traits, languages."""
    choice_lower = choice.lower()

    for race_name, race_data in RACES.items():
        # Check if it's the base race (for races without subraces)
        if race_name.lower() == choice_lower and not race_data.get("subraces"):
            return {
                "race": race_name,
                "subrace": None,
                "ability_bonuses": dict(race_data["ability_bonuses"]),
                "speed": race_data["speed"],
                "traits": list(race_data["traits"]),
                "languages": list(race_data["languages"]),
            }
        # Check subraces
        for sub_name, sub_data in race_data.get("subraces", {}).items():
            if sub_name.lower() == choice_lower:
                bonuses = dict(race_data["ability_bonuses"])
                for ability, bonus in sub_data["ability_bonuses"].items():
                    bonuses[ability] = bonuses.get(ability, 0) + bonus
                traits = list(race_data["traits"]) + list(sub_data["traits"])
                speed = sub_data.get("speed", race_data["speed"])
                # Wood Elf has Fleet of Foot
                if "Fleet of Foot (speed 35 ft)" in sub_data.get("traits", []):
                    speed = 35
                return {
                    "race": race_name,
                    "subrace": sub_name,
                    "ability_bonuses": bonuses,
                    "speed": speed,
                    "traits": traits,
                    "languages": list(race_data["languages"]),
                }
    return None

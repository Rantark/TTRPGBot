"""D&D 5th Edition PHB backgrounds with skill proficiencies and features."""

BACKGROUNDS = {
    "Acolyte": {
        "skill_proficiencies": ["Insight", "Religion"],
        "languages": 2,
        "feature": "Shelter of the Faithful",
        "description": "You have spent your life in the service of a temple.",
    },
    "Charlatan": {
        "skill_proficiencies": ["Deception", "Sleight of Hand"],
        "tool_proficiencies": ["Disguise kit", "Forgery kit"],
        "feature": "False Identity",
        "description": "You have always had a way with people.",
    },
    "Criminal": {
        "skill_proficiencies": ["Deception", "Stealth"],
        "tool_proficiencies": ["Gaming set (one)", "Thieves' tools"],
        "feature": "Criminal Contact",
        "description": "You are an experienced criminal with a history of breaking the law.",
    },
    "Entertainer": {
        "skill_proficiencies": ["Acrobatics", "Performance"],
        "tool_proficiencies": ["Disguise kit", "Musical instrument (one)"],
        "feature": "By Popular Demand",
        "description": "You thrive in front of an audience.",
    },
    "Folk Hero": {
        "skill_proficiencies": ["Animal Handling", "Survival"],
        "tool_proficiencies": ["Artisan's tools (one)", "Vehicles (land)"],
        "feature": "Rustic Hospitality",
        "description": "You come from a humble social rank, but you are destined for much more.",
    },
    "Guild Artisan": {
        "skill_proficiencies": ["Insight", "Persuasion"],
        "tool_proficiencies": ["Artisan's tools (one)"],
        "languages": 1,
        "feature": "Guild Membership",
        "description": "You are a member of an artisan's guild, skilled in a particular field.",
    },
    "Hermit": {
        "skill_proficiencies": ["Medicine", "Religion"],
        "tool_proficiencies": ["Herbalism kit"],
        "languages": 1,
        "feature": "Discovery",
        "description": "You lived in seclusion for a formative part of your life.",
    },
    "Noble": {
        "skill_proficiencies": ["History", "Persuasion"],
        "tool_proficiencies": ["Gaming set (one)"],
        "languages": 1,
        "feature": "Position of Privilege",
        "description": "You were raised in a family among the social elite.",
    },
    "Outlander": {
        "skill_proficiencies": ["Athletics", "Survival"],
        "tool_proficiencies": ["Musical instrument (one)"],
        "languages": 1,
        "feature": "Wanderer",
        "description": "You grew up in the wilds, far from civilization.",
    },
    "Sage": {
        "skill_proficiencies": ["Arcana", "History"],
        "languages": 2,
        "feature": "Researcher",
        "description": "You spent years learning the lore of the multiverse.",
    },
    "Sailor": {
        "skill_proficiencies": ["Athletics", "Perception"],
        "tool_proficiencies": ["Navigator's tools", "Vehicles (water)"],
        "feature": "Ship's Passage",
        "description": "You sailed on a seagoing vessel for years.",
    },
    "Soldier": {
        "skill_proficiencies": ["Athletics", "Intimidation"],
        "tool_proficiencies": ["Gaming set (one)", "Vehicles (land)"],
        "feature": "Military Rank",
        "description": "You served in an army and know the rigors of military life.",
    },
    "Urchin": {
        "skill_proficiencies": ["Sleight of Hand", "Stealth"],
        "tool_proficiencies": ["Disguise kit", "Thieves' tools"],
        "feature": "City Secrets",
        "description": "You grew up on the streets alone, orphaned, and poor.",
    },
}


def get_background_names():
    return sorted(BACKGROUNDS.keys())


def get_background_data(name: str):
    for bg_name, bg_data in BACKGROUNDS.items():
        if bg_name.lower() == name.lower():
            return bg_name, bg_data
    return None, None

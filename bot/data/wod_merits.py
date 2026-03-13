"""World of Darkness — Merits for character creation."""

# Merits available during character creation.
# Each merit has a name, dot range, and description.
# Characters get 7 dots of merits at creation.

MERITS = {
    # ── Physical Merits ──
    "Ambidextrous": {
        "dots": [3],
        "category": "Physical",
        "description": "No off-hand penalty. Can use either hand equally.",
    },
    "Danger Sense": {
        "dots": [2],
        "category": "Physical",
        "description": "+2 to detect ambushes and surprise attacks.",
    },
    "Fast Reflexes": {
        "dots": [1, 2],
        "category": "Physical",
        "description": "+1 or +2 to Initiative.",
    },
    "Fleet of Foot": {
        "dots": [1, 2, 3],
        "category": "Physical",
        "description": "+1/+2/+3 to Speed.",
    },
    "Giant": {
        "dots": [4],
        "category": "Physical",
        "description": "Size 6 instead of 5. +1 Health.",
    },
    "Iron Stamina": {
        "dots": [1, 2, 3],
        "category": "Physical",
        "description": "Ignore 1/2/3 points of fatigue or wound penalties.",
    },
    "Quick Draw": {
        "dots": [1],
        "category": "Physical",
        "description": "Draw a weapon as a reflexive action.",
    },
    "Strong Back": {
        "dots": [1],
        "category": "Physical",
        "description": "+1 to lifting/carrying capacity.",
    },
    "Toxin Resistance": {
        "dots": [2],
        "category": "Physical",
        "description": "+2 to resist poisons and drugs.",
    },

    # ── Mental Merits ──
    "Common Sense": {
        "dots": [3],
        "category": "Mental",
        "description": "Once per session, the ST warns you if you're about to do something obviously stupid.",
    },
    "Eidetic Memory": {
        "dots": [2],
        "category": "Mental",
        "description": "Perfect recall. +2 to memory-related rolls.",
    },
    "Encyclopedic Knowledge": {
        "dots": [4],
        "category": "Mental",
        "description": "Make Intelligence + Wits rolls to know obscure facts.",
    },
    "Meditative Mind": {
        "dots": [1],
        "category": "Mental",
        "description": "No penalties to meditation rolls.",
    },
    "Multilingual": {
        "dots": [1, 2, 3],
        "category": "Mental",
        "description": "Speak 1/2/3 additional languages.",
    },

    # ── Social Merits ──
    "Allies": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Social",
        "description": "Mortal contacts who can help. Dots = influence level.",
    },
    "Contacts": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Social",
        "description": "Information networks. Each dot = one area of expertise.",
    },
    "Fame": {
        "dots": [1, 2, 3],
        "category": "Social",
        "description": "Public recognition. +1/+2/+3 to social rolls with those who know you.",
    },
    "Mentor": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Social",
        "description": "An older, wiser vampire who guides you. Dots = their power.",
    },
    "Resources": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Social",
        "description": "Wealth and income. 1=poor, 3=middle class, 5=millionaire.",
    },
    "Retainer": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Social",
        "description": "A loyal servant (ghoul, mortal employee). Dots = their competence.",
    },
    "Status": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Social",
        "description": "Standing in vampire society or a covenant. Dots = rank.",
    },
    "Striking Looks": {
        "dots": [2, 4],
        "category": "Social",
        "description": "Exceptionally attractive. +1/+2 to relevant social rolls.",
    },

    # ── Vampire-Specific Merits ──
    "Haven": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Vampire",
        "description": "A safe resting place. Dots = size and security.",
    },
    "Herd": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Vampire",
        "description": "Regular feeding sources. Dots = how many and how reliable.",
    },
    "Covenant Status": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Vampire",
        "description": "Rank within your covenant.",
    },
    "City Status": {
        "dots": [1, 2, 3, 4, 5],
        "category": "Vampire",
        "description": "Standing in the local vampire court.",
    },
}

MERIT_DOTS_AT_CREATION = 7


def get_merit_names() -> list[str]:
    return list(MERITS.keys())


def get_merit_data(name: str) -> dict | None:
    return MERITS.get(name)


def get_merits_by_category(category: str) -> dict:
    return {k: v for k, v in MERITS.items() if v["category"] == category}

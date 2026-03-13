"""World of Darkness — Vampire the Requiem clans, covenants, and related data."""

# ── The Five Clans of Vampire: The Requiem ──
CLANS = {
    "Daeva": {
        "nickname": "Succubi",
        "description": (
            "Sensual, seductive predators who revel in passion and desire. "
            "The Daeva are creatures of intense emotion and social grace, "
            "drawing mortals to them like moths to flame."
        ),
        "favored_attributes": ["Dexterity", "Manipulation"],
        "clan_disciplines": ["Celerity", "Majesty", "Vigor"],
        "clan_weakness": (
            "The Daeva find it difficult to resist indulgence. They suffer a penalty "
            "to resist temptation related to their Vice."
        ),
    },
    "Gangrel": {
        "nickname": "Savages",
        "description": (
            "Feral predators who embrace the Beast within. Gangrel are the most "
            "animalistic of vampires, at home in the wild and feared for their "
            "raw physical prowess and savage nature."
        ),
        "favored_attributes": ["Composure", "Stamina"],
        "clan_disciplines": ["Animalism", "Protean", "Resilience"],
        "clan_weakness": (
            "When a Gangrel frenzies, they gain an animalistic feature — a tail, "
            "claws, fur patches, or bestial eyes — that lingers for the night."
        ),
    },
    "Mekhet": {
        "nickname": "Shadows",
        "description": (
            "Secretive scholars of the dark. The Mekhet are creatures of shadow "
            "and secrets, gifted with preternatural senses and the ability to "
            "move unseen. They are information brokers and spies."
        ),
        "favored_attributes": ["Intelligence", "Wits"],
        "clan_disciplines": ["Auspex", "Celerity", "Obfuscate"],
        "clan_weakness": (
            "The Mekhet are more vulnerable to light and fire. They take additional "
            "damage from sunlight and fire sources."
        ),
    },
    "Nosferatu": {
        "nickname": "Haunts",
        "description": (
            "Monstrous outcasts who inspire dread. Nosferatu are cursed with an "
            "unsettling presence — some are hideously deformed, others simply radiate "
            "wrongness. They thrive in the shadows and sewers."
        ),
        "favored_attributes": ["Composure", "Strength"],
        "clan_disciplines": ["Nightmare", "Obfuscate", "Vigor"],
        "clan_weakness": (
            "All Nosferatu possess the Lonely Curse. They suffer penalties on social "
            "rolls involving positive social interaction (not Intimidation)."
        ),
    },
    "Ventrue": {
        "nickname": "Lords",
        "description": (
            "Regal rulers born to command. The Ventrue see themselves as the rightful "
            "lords of the night, blessed with an iron will and the ability to dominate "
            "lesser beings. They are politicians, generals, and CEOs."
        ),
        "favored_attributes": ["Presence", "Resolve"],
        "clan_disciplines": ["Animalism", "Dominate", "Resilience"],
        "clan_weakness": (
            "The Ventrue have a restricted feeding preference. Each Ventrue can only "
            "feed from a specific type of mortal (by emotion, blood type, background, etc.)."
        ),
    },
}

# ── The Five Major Covenants ──
COVENANTS = {
    "Carthian Movement": {
        "description": (
            "Democratic revolutionaries who apply mortal political philosophies to vampire society. "
            "They believe in representation, equality, and progress."
        ),
        "philosophy": "Modern governance and democratic principles for the Kindred.",
    },
    "Circle of the Crone": {
        "description": (
            "Pagan mystics who worship ancient gods and practice blood sorcery called Cruac. "
            "They see the vampiric condition as a dark blessing and spiritual test."
        ),
        "philosophy": "Spiritual growth through blood magic and ancient ritual.",
        "special": "Access to Cruac blood sorcery.",
    },
    "Invictus": {
        "description": (
            "The aristocratic elite — the oldest and most powerful covenant. "
            "They maintain feudal hierarchy and tradition, controlling vampire society "
            "through wealth, boons, and ancient influence."
        ),
        "philosophy": "Power through tradition, hierarchy, and noblesse oblige.",
    },
    "Lancea et Sanctum": {
        "description": (
            "The vampiric church that believes Kindred are God's instruments of judgment. "
            "They practice Theban Sorcery and see themselves as holy predators with a divine purpose."
        ),
        "philosophy": "Divine purpose — vampires exist as God's test for humanity.",
        "special": "Access to Theban Sorcery.",
    },
    "Ordo Dracul": {
        "description": (
            "Occult scientists founded by Dracula himself. They study the vampiric condition "
            "and seek to transcend its limitations through mystical Coils."
        ),
        "philosophy": "Transcendence — overcome the vampiric curse through the Coils of the Dragon.",
        "special": "Access to Coils of the Dragon.",
    },
}

# ── Virtues and Vices ──
VIRTUES = [
    "Charity", "Faith", "Fortitude", "Hope",
    "Justice", "Prudence", "Temperance",
]

VICES = [
    "Envy", "Gluttony", "Greed", "Lust",
    "Pride", "Sloth", "Wrath",
]


def get_clan_names() -> list[str]:
    return list(CLANS.keys())


def get_clan_data(name: str) -> dict | None:
    return CLANS.get(name)


def get_covenant_names() -> list[str]:
    return list(COVENANTS.keys())


def get_covenant_data(name: str) -> dict | None:
    return COVENANTS.get(name)

"""World of Darkness — Vampire the Requiem clans, covenants, and related data."""

# ── The Five Clans of Vampire: The Requiem ──
CLANS = {
    "Daeva": {
        "nickname": "Succubi",
        "emoji": "\U0001f525",  # 🔥
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
        "playstyle": "Social manipulation, seduction, and high-speed combat.",
    },
    "Gangrel": {
        "nickname": "Savages",
        "emoji": "\U0001f43a",  # 🐺
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
        "playstyle": "Shapeshifting, animal control, and rugged survivability.",
    },
    "Mekhet": {
        "nickname": "Shadows",
        "emoji": "\U0001f441\ufe0f",  # 👁️
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
        "playstyle": "Stealth, psychic perception, and information gathering.",
    },
    "Nosferatu": {
        "nickname": "Haunts",
        "emoji": "\U0001f480",  # 💀
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
        "playstyle": "Terror, stealth, and brute force from the shadows.",
    },
    "Ventrue": {
        "nickname": "Lords",
        "emoji": "\U0001f451",  # 👑
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
        "playstyle": "Leadership, mind control, and political domination.",
    },
}

# ── The Five Major Covenants ──
COVENANTS = {
    "Carthian Movement": {
        "emoji": "\u2696\ufe0f",  # ⚖️
        "description": (
            "Democratic revolutionaries who apply mortal political philosophies to vampire society. "
            "They believe in representation, equality, and progress."
        ),
        "philosophy": "Modern governance and democratic principles for the Kindred.",
    },
    "Circle of the Crone": {
        "emoji": "\U0001f319",  # 🌙
        "description": (
            "Pagan mystics who worship ancient gods and practice blood sorcery called Cruac. "
            "They see the vampiric condition as a dark blessing and spiritual test."
        ),
        "philosophy": "Spiritual growth through blood magic and ancient ritual.",
        "special": "Access to Cruac blood sorcery.",
    },
    "Invictus": {
        "emoji": "\U0001f3f0",  # 🏰
        "description": (
            "The aristocratic elite — the oldest and most powerful covenant. "
            "They maintain feudal hierarchy and tradition, controlling vampire society "
            "through wealth, boons, and ancient influence."
        ),
        "philosophy": "Power through tradition, hierarchy, and noblesse oblige.",
    },
    "Lancea et Sanctum": {
        "emoji": "\u271d\ufe0f",  # ✝️
        "description": (
            "The vampiric church that believes Kindred are God's instruments of judgment. "
            "They practice Theban Sorcery and see themselves as holy predators with a divine purpose."
        ),
        "philosophy": "Divine purpose — vampires exist as God's test for humanity.",
        "special": "Access to Theban Sorcery.",
    },
    "Ordo Dracul": {
        "emoji": "\U0001f409",  # 🐉
        "description": (
            "Occult scientists founded by Dracula himself. They study the vampiric condition "
            "and seek to transcend its limitations through mystical Coils."
        ),
        "philosophy": "Transcendence — overcome the vampiric curse through the Coils of the Dragon.",
        "special": "Access to Coils of the Dragon.",
    },
}

# ── Virtues and Vices (with emoji + short descriptions) ──
VIRTUES = [
    "Charity", "Faith", "Fortitude", "Hope",
    "Justice", "Prudence", "Temperance",
]

VIRTUE_DATA = {
    "Charity": {"emoji": "\U0001f49b", "description": "Selfless generosity — you put others before yourself."},
    "Faith": {"emoji": "\U0001f54a\ufe0f", "description": "Unwavering belief — your convictions guide you through darkness."},
    "Fortitude": {"emoji": "\U0001f6e1\ufe0f", "description": "Inner strength — you endure hardship without breaking."},
    "Hope": {"emoji": "\u2b50", "description": "Undying optimism — even in the darkest nights, you see the dawn."},
    "Justice": {"emoji": "\u2696\ufe0f", "description": "Fairness and truth — you uphold what's right, no matter the cost."},
    "Prudence": {"emoji": "\U0001f9e0", "description": "Careful wisdom — you think before you act, planning ahead."},
    "Temperance": {"emoji": "\U0001f9d8", "description": "Self-control — you resist excess and maintain balance."},
}

VICES = [
    "Envy", "Gluttony", "Greed", "Lust",
    "Pride", "Sloth", "Wrath",
]

VICE_DATA = {
    "Envy": {"emoji": "\U0001f7e2", "description": "You covet what others have — their power, their beauty, their lives."},
    "Gluttony": {"emoji": "\U0001f969", "description": "You can never get enough — blood, pleasure, sensation."},
    "Greed": {"emoji": "\U0001f4b0", "description": "You hoard wealth, power, and influence at any cost."},
    "Lust": {"emoji": "\U0001f48b", "description": "You crave intimacy and passion — desire controls you."},
    "Pride": {"emoji": "\U0001f981", "description": "You believe you're superior — and you need others to know it."},
    "Sloth": {"emoji": "\U0001f634", "description": "You take the easy path — why exert effort when you don't have to?"},
    "Wrath": {"emoji": "\U0001f4a2", "description": "Anger simmers beneath the surface — and it doesn't take much to ignite."},
}


def get_clan_names() -> list[str]:
    return list(CLANS.keys())


def get_clan_data(name: str) -> dict | None:
    return CLANS.get(name)


def get_covenant_names() -> list[str]:
    return list(COVENANTS.keys())


def get_covenant_data(name: str) -> dict | None:
    return COVENANTS.get(name)

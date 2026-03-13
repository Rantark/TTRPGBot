"""World of Darkness — Vampire the Requiem disciplines and powers."""

# ── Vampire Disciplines ──
# Each discipline has 5 dots with a power at each level.
DISCIPLINES = {
    "Animalism": {
        "description": "Command over animals and the Beast within.",
        "powers": {
            1: {"name": "Feral Whispers", "description": "Communicate with animals mentally."},
            2: {"name": "Obedience", "description": "Command an animal to perform a task."},
            3: {"name": "Call of the Wild", "description": "Summon animals from the surrounding area."},
            4: {"name": "Subsume", "description": "Possess an animal's body."},
            5: {"name": "Leashing the Beast", "description": "Project your frenzy into another or calm a frenzying vampire."},
        },
    },
    "Auspex": {
        "description": "Supernatural perception and psychic sensitivity.",
        "powers": {
            1: {"name": "Heightened Senses", "description": "Sharpen all senses to supernatural levels."},
            2: {"name": "Aura Perception", "description": "Read the emotional aura of a person."},
            3: {"name": "The Spirit's Touch", "description": "Read psychic impressions from objects."},
            4: {"name": "Telepathy", "description": "Read surface thoughts of a person."},
            5: {"name": "Twilight Projection", "description": "Project your consciousness into the spirit world."},
        },
    },
    "Celerity": {
        "description": "Supernatural speed and reflexes.",
        "powers": {
            1: {"name": "Tempest", "description": "Add Celerity dots to Defense."},
            2: {"name": "Alacrity", "description": "Gain extra actions in a turn."},
            3: {"name": "Rapid Reflexes", "description": "React before anyone else; preempt actions."},
            4: {"name": "Fleetness", "description": "Move at blur-like speed over short distances."},
            5: {"name": "Lightning Strike", "description": "Attack with such speed the target cannot defend."},
        },
    },
    "Dominate": {
        "description": "Mind control through eye contact and commands.",
        "powers": {
            1: {"name": "Command", "description": "Issue a one-word command that must be obeyed."},
            2: {"name": "Mesmerize", "description": "Implant a complex suggestion in a target's mind."},
            3: {"name": "The Forgetful Mind", "description": "Rewrite or erase memories."},
            4: {"name": "Conditioning", "description": "Make a subject permanently susceptible to your Dominate."},
            5: {"name": "Possession", "description": "Take complete control of a mortal's body."},
        },
    },
    "Majesty": {
        "description": "Supernatural charisma and emotional manipulation.",
        "powers": {
            1: {"name": "Awe", "description": "Become the center of attention; people are drawn to you."},
            2: {"name": "Revelation", "description": "Force a target to reveal their true feelings."},
            3: {"name": "Entrancement", "description": "Make a target devoted to you temporarily."},
            4: {"name": "Summoning", "description": "Call a person who has been affected by your Majesty."},
            5: {"name": "Sovereignty", "description": "Your presence becomes so commanding that none dare act against you."},
        },
    },
    "Nightmare": {
        "description": "Project fear and horror into others' minds.",
        "powers": {
            1: {"name": "Monstrous Countenance", "description": "Your face becomes terrifying; cause Lunacy-like fear."},
            2: {"name": "Dread Presence", "description": "Radiate an aura of supernatural dread."},
            3: {"name": "Eye of the Beast", "description": "Lock eyes with a target to paralyze them with terror."},
            4: {"name": "Shatter the Mind", "description": "Inflict a temporary derangement through sheer terror."},
            5: {"name": "Mortal Terror", "description": "Drive a target permanently insane with fear."},
        },
    },
    "Obfuscate": {
        "description": "Become invisible and undetectable.",
        "powers": {
            1: {"name": "Touch of Shadow", "description": "Fade from notice; people's eyes slide past you."},
            2: {"name": "Mask of Tranquility", "description": "Appear as an unremarkable mortal."},
            3: {"name": "Cloak of Night", "description": "Become completely invisible."},
            4: {"name": "The Familiar Stranger", "description": "Appear as a specific person."},
            5: {"name": "Cloak the Gathering", "description": "Extend invisibility to a group."},
        },
    },
    "Protean": {
        "description": "Shapeshifting and physical transformation.",
        "powers": {
            1: {"name": "Aspect of the Predator", "description": "Manifest claws or fangs as weapons."},
            2: {"name": "Haven of Soil", "description": "Meld into the earth for daytime rest."},
            3: {"name": "Unmarked Grave", "description": "Sink into any natural surface."},
            4: {"name": "Shape of the Beast", "description": "Transform into an animal (wolf or bat)."},
            5: {"name": "Body of Spirit", "description": "Become a cloud of mist or swarm of vermin."},
        },
    },
    "Resilience": {
        "description": "Supernatural toughness and damage resistance.",
        "powers": {
            1: {"name": "Toughness", "description": "Add Resilience dots to Stamina for health calculations."},
            2: {"name": "Endurance", "description": "Downgrade lethal damage to bashing."},
            3: {"name": "Unfeeling", "description": "Ignore wound penalties."},
            4: {"name": "Adamantine", "description": "Downgrade aggravated damage to lethal."},
            5: {"name": "Juggernaut", "description": "Become nearly indestructible for a scene."},
        },
    },
    "Vigor": {
        "description": "Supernatural physical strength.",
        "powers": {
            1: {"name": "Strength", "description": "Add Vigor dots to Strength."},
            2: {"name": "Might", "description": "Perform feats of incredible physical power."},
            3: {"name": "Prowess", "description": "Crush objects and break through barriers easily."},
            4: {"name": "Intensity", "description": "Grip attacks become devastating; throw objects great distances."},
            5: {"name": "Indomitable", "description": "Strength that rivals construction equipment."},
        },
    },
}

# Clan -> starting disciplines
CLAN_DISCIPLINES = {
    "Daeva": ["Celerity", "Majesty", "Vigor"],
    "Gangrel": ["Animalism", "Protean", "Resilience"],
    "Mekhet": ["Auspex", "Celerity", "Obfuscate"],
    "Nosferatu": ["Nightmare", "Obfuscate", "Vigor"],
    "Ventrue": ["Animalism", "Dominate", "Resilience"],
}


def get_discipline_names() -> list[str]:
    return list(DISCIPLINES.keys())


def get_clan_disciplines(clan: str) -> list[str]:
    return CLAN_DISCIPLINES.get(clan, [])


def get_discipline_data(name: str) -> dict | None:
    return DISCIPLINES.get(name)

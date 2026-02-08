"""Fuzzy matching utilities for helpful error messages."""

from difflib import get_close_matches

from bot.data.rules import SKILLS, ABILITY_NAMES

VALID_SKILLS = list(SKILLS.keys())

VALID_ABILITIES = [a.lower() for a in ABILITY_NAMES]

VALID_CONDITIONS = [
    'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
    'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
    'prone', 'restrained', 'stunned', 'unconscious',
]


def suggest_skill(invalid_skill: str) -> str:
    """Return a helpful error message for an invalid skill name."""
    matches = get_close_matches(invalid_skill.lower(),
                                [s.lower() for s in VALID_SKILLS], n=1, cutoff=0.6)
    if matches:
        # Find the properly-cased version
        for sk in VALID_SKILLS:
            if sk.lower() == matches[0]:
                return f"Unknown skill: `{invalid_skill}`. Did you mean **{sk}**?"
    return (
        f"Unknown skill: `{invalid_skill}`.\n"
        f"Use `!skills` to see your skill modifiers, or try one of these:\n"
        f"Perception, Investigation, Stealth, Athletics, Acrobatics, Insight, etc."
    )


def suggest_ability(invalid_ability: str) -> str:
    """Return a helpful error message for an invalid ability score."""
    matches = get_close_matches(invalid_ability.lower(), VALID_ABILITIES, n=1, cutoff=0.6)
    if matches:
        return f"Unknown ability: `{invalid_ability}`. Did you mean **{matches[0].upper()}**?"
    return f"Unknown ability: `{invalid_ability}`. Valid abilities: **STR, DEX, CON, INT, WIS, CHA**"


def suggest_condition(invalid_condition: str) -> str:
    """Return a helpful error message for an invalid condition."""
    matches = get_close_matches(invalid_condition.lower(), VALID_CONDITIONS, n=1, cutoff=0.6)
    if matches:
        return f"Unknown condition: `{invalid_condition}`. Did you mean **{matches[0]}**?"
    return (
        f"Unknown condition: `{invalid_condition}`.\n"
        f"Common conditions: poisoned, blinded, stunned, prone, frightened, grappled"
    )

"""Dice rolling engine supporting standard D&D notation."""

import random
import re


def roll_die(sides: int) -> int:
    return random.randint(1, sides)


def roll_dice(count: int, sides: int) -> list[int]:
    return [roll_die(sides) for _ in range(count)]


def roll_4d6_drop_lowest() -> tuple[int, list[int]]:
    """Roll 4d6, drop the lowest. Returns (total, all_four_rolls)."""
    rolls = roll_dice(4, 6)
    dropped = min(rolls)
    total = sum(rolls) - dropped
    return total, rolls


def roll_ability_scores() -> list[tuple[int, list[int]]]:
    """Roll a full set of 6 ability scores using 4d6 drop lowest."""
    return [roll_4d6_drop_lowest() for _ in range(6)]


def parse_and_roll(notation: str, advantage: bool = False, disadvantage: bool = False) -> dict:
    """Parse dice notation like '2d6+3', 'd20', '4d6-1', 'd20+5' and roll.

    Returns dict with keys: notation, rolls, modifier, total, breakdown.
    If advantage/disadvantage, rolls twice and takes higher/lower.
    """
    notation = notation.strip().lower().replace(" ", "")
    pattern = r"^(\d*)d(\d+)([+-]\d+)?$"
    match = re.match(pattern, notation)
    if not match:
        return {"error": f"Invalid dice notation: `{notation}`. Use format like `2d6+3`, `d20`, `1d20+5`."}

    count = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    mod = int(match.group(3)) if match.group(3) else 0

    if count < 1 or count > 100:
        return {"error": "Number of dice must be between 1 and 100."}
    if sides < 1 or sides > 1000:
        return {"error": "Die sides must be between 1 and 1000."}

    rolls = roll_dice(count, sides)
    total = sum(rolls) + mod

    if (advantage or disadvantage) and not (advantage and disadvantage):
        rolls2 = roll_dice(count, sides)
        total2 = sum(rolls2) + mod

        r1_str = " + ".join(str(r) for r in rolls)
        r2_str = " + ".join(str(r) for r in rolls2)
        r1_display = f"[{r1_str}]" if count > 1 else f"[{rolls[0]}]"
        r2_display = f"[{r2_str}]" if count > 1 else f"[{rolls2[0]}]"

        if advantage:
            chosen = max(total, total2)
            label = "Advantage"
        else:
            chosen = min(total, total2)
            label = "Disadvantage"

        mod_str = ""
        if mod > 0:
            mod_str = f" + {mod}"
        elif mod < 0:
            mod_str = f" - {abs(mod)}"

        breakdown = f"**{label}:** {r1_display}{mod_str} = {total}, {r2_display}{mod_str} = {total2} -> **{chosen}**"

        return {
            "notation": notation,
            "rolls": rolls,
            "rolls2": rolls2,
            "modifier": mod,
            "total": chosen,
            "breakdown": breakdown,
            "count": count,
            "sides": sides,
            "advantage": advantage,
            "disadvantage": disadvantage,
        }

    # Normal roll (no adv/dis)
    rolls_str = " + ".join(str(r) for r in rolls)
    if count > 1:
        breakdown = f"[{rolls_str}]"
    else:
        breakdown = f"[{rolls[0]}]"

    if mod > 0:
        breakdown += f" + {mod}"
    elif mod < 0:
        breakdown += f" - {abs(mod)}"

    breakdown += f" = **{total}**"

    return {
        "notation": notation,
        "rolls": rolls,
        "modifier": mod,
        "total": total,
        "breakdown": breakdown,
        "count": count,
        "sides": sides,
    }


def roll_initiative(dex_modifier: int, advantage: bool = False, disadvantage: bool = False) -> dict:
    """Roll initiative: 1d20 + DEX modifier, with optional advantage/disadvantage."""
    if (advantage or disadvantage) and not (advantage and disadvantage):
        r1, r2 = roll_die(20), roll_die(20)
        if advantage:
            roll = max(r1, r2)
            label = "advantage"
        else:
            roll = min(r1, r2)
            label = "disadvantage"
        total = roll + dex_modifier
        mod_str = f"+{dex_modifier}" if dex_modifier >= 0 else str(dex_modifier)
        breakdown = f"[{r1}, {r2}] ({label}, took {roll}) {mod_str} = **{total}**"
        return {"roll": roll, "modifier": dex_modifier, "total": total, "breakdown": breakdown}

    roll = roll_die(20)
    total = roll + dex_modifier
    mod_str = f"+{dex_modifier}" if dex_modifier >= 0 else str(dex_modifier)
    breakdown = f"[{roll}] {mod_str} = **{total}**"
    return {"roll": roll, "modifier": dex_modifier, "total": total, "breakdown": breakdown}


def roll_check(ability_modifier: int, proficiency: int = 0, advantage: bool = False, disadvantage: bool = False) -> dict:
    """Roll an ability check or saving throw."""
    total_mod = ability_modifier + proficiency

    if advantage and not disadvantage:
        r1, r2 = roll_die(20), roll_die(20)
        roll = max(r1, r2)
        roll_desc = f"[{r1}, {r2}] (advantage, took {roll})"
    elif disadvantage and not advantage:
        r1, r2 = roll_die(20), roll_die(20)
        roll = min(r1, r2)
        roll_desc = f"[{r1}, {r2}] (disadvantage, took {roll})"
    else:
        roll = roll_die(20)
        roll_desc = f"[{roll}]"

    total = roll + total_mod
    mod_str = f"+{total_mod}" if total_mod >= 0 else str(total_mod)
    breakdown = f"{roll_desc} {mod_str} = **{total}**"

    return {
        "roll": roll,
        "modifier": total_mod,
        "total": total,
        "breakdown": breakdown,
        "natural_20": roll == 20,
        "natural_1": roll == 1,
    }


def parse_adv_dis(text: str) -> tuple[str, bool, bool]:
    """Parse advantage/disadvantage keywords from a string.

    Returns (cleaned_text, advantage, disadvantage).
    """
    advantage = False
    disadvantage = False
    lower = text.lower()

    # Check for disadvantage first (contains 'adv' substring)
    if ' disadvantage' in lower or lower.startswith('disadvantage') or ' dis ' in f' {lower} ' or lower.endswith(' dis') or lower.startswith('dis ') or lower == 'dis':
        disadvantage = True
        text = re.sub(r'\b(?:disadvantage|dis)\b', '', text, flags=re.IGNORECASE).strip()
    elif ' advantage' in lower or lower.startswith('advantage') or ' adv ' in f' {lower} ' or lower.endswith(' adv') or lower.startswith('adv ') or lower == 'adv':
        advantage = True
        text = re.sub(r'\b(?:advantage|adv)\b', '', text, flags=re.IGNORECASE).strip()

    return text, advantage, disadvantage

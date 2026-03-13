"""World of Darkness dice mechanics.

Chronicles of Darkness / New World of Darkness uses d10 dice pools:
- Roll a pool of d10s equal to Attribute + Skill (+ modifiers)
- Each die showing 8, 9, or 10 is a SUCCESS
- Each 10 "explodes" (10-again): roll another d10, which can also explode
- 0 dice in pool = roll 1 "chance die" (only 10 = success, 1 = dramatic failure)
- 5+ successes on a single roll = Exceptional Success
"""

import random


def roll_d10() -> int:
    return random.randint(1, 10)


def roll_pool(pool_size: int, again: int = 10, rote: bool = False) -> dict:
    """Roll a World of Darkness dice pool.

    Args:
        pool_size: Number of d10s to roll (0 or less = chance die).
        again: The "again" threshold (default 10 = 10-again, 9 = 9-again, 8 = 8-again).
              Set to 11 to disable re-rolls (no-again).
        rote: If True, failed dice on the first roll are re-rolled once (Rote Action).

    Returns dict with:
        pool: original pool size
        rolls: list of all individual die results (including explosions)
        successes: count of successes (8+)
        is_chance: whether this was a chance die roll
        dramatic_failure: True if chance die rolled a 1
        exceptional: True if 5+ successes
        breakdown: formatted string for Discord display
    """
    if pool_size <= 0:
        return _roll_chance_die()

    rolls = []
    successes = 0

    # Roll initial pool
    initial_rolls = [roll_d10() for _ in range(pool_size)]

    for die in initial_rolls:
        rolls.append(die)
        if die >= 8:
            successes += 1
            # Exploding dice (10-again by default)
            if die >= again:
                extra = _explode(again)
                rolls.extend(extra)
                successes += sum(1 for d in extra if d >= 8)
        elif rote:
            # Rote action: re-roll failures once
            reroll = roll_d10()
            rolls.append(reroll)
            if reroll >= 8:
                successes += 1
                if reroll >= again:
                    extra = _explode(again)
                    rolls.extend(extra)
                    successes += sum(1 for d in extra if d >= 8)

    exceptional = successes >= 5

    # Build breakdown string
    roll_strs = []
    for r in rolls:
        if r >= 8:
            roll_strs.append(f"**{r}**")
        else:
            roll_strs.append(str(r))

    breakdown = f"[{', '.join(roll_strs)}]"
    result_label = f"**{successes} success{'es' if successes != 1 else ''}**"
    if exceptional:
        result_label += " (Exceptional!)"
    if successes == 0:
        result_label = "**Failure**"

    extras = []
    if again < 10:
        extras.append(f"{again}-again")
    if again > 10:
        extras.append("no-again")
    if rote:
        extras.append("rote")
    extra_str = f" ({', '.join(extras)})" if extras else ""

    breakdown = f"{pool_size} dice{extra_str}: {breakdown} = {result_label}"

    return {
        "pool": pool_size,
        "rolls": rolls,
        "successes": successes,
        "is_chance": False,
        "dramatic_failure": False,
        "exceptional": exceptional,
        "breakdown": breakdown,
    }


def _explode(again: int) -> list[int]:
    """Roll exploding dice until no more explosions."""
    extra = []
    while True:
        die = roll_d10()
        extra.append(die)
        if die < again:
            break
    return extra


def _roll_chance_die() -> dict:
    """Roll a single chance die (pool of 0 or less)."""
    die = roll_d10()
    successes = 1 if die == 10 else 0
    dramatic = die == 1

    if die == 10:
        result_label = "**1 success** (Chance die!)"
        die_str = f"**{die}**"
    elif die == 1:
        result_label = "**Dramatic Failure!**"
        die_str = f"~~{die}~~"
    else:
        result_label = "**Failure**"
        die_str = str(die)

    breakdown = f"Chance die: [{die_str}] = {result_label}"

    return {
        "pool": 0,
        "rolls": [die],
        "successes": successes,
        "is_chance": True,
        "dramatic_failure": dramatic,
        "exceptional": False,
        "breakdown": breakdown,
    }


def roll_initiative_wod(dexterity: int, composure: int, modifier: int = 0) -> dict:
    """Roll WoD initiative: Dexterity + Composure + 1d10 + modifier.

    Unlike normal pools, initiative is NOT a success-counting roll.
    It's a flat value.
    """
    die = roll_d10()
    base = dexterity + composure + modifier
    total = base + die
    mod_str = f" + {modifier}" if modifier > 0 else (f" - {abs(modifier)}" if modifier < 0 else "")
    breakdown = (
        f"Dex ({dexterity}) + Composure ({composure}){mod_str} + [{die}] = **{total}**"
    )
    return {
        "roll": die,
        "base": base,
        "total": total,
        "breakdown": breakdown,
    }


def roll_rouse_check() -> dict:
    """Roll a Rouse Check (Vampire: The Requiem uses Vitae differently,
    but this implements a simple blood surge / power activation check).

    Roll 1d10: on 6+, success (no Vitae cost beyond 1).
    On 1-5, the power still works but costs additional Vitae.
    """
    die = roll_d10()
    success = die >= 6
    breakdown = f"[{die}] = {'**Success** (no extra cost)' if success else '**Failure** (additional cost)'}"
    return {
        "roll": die,
        "success": success,
        "breakdown": breakdown,
    }


def parse_pool_args(text: str) -> tuple[str, int, bool]:
    """Parse dice pool arguments from a string.

    Looks for modifiers like '9again', '8again', 'noagain', 'rote'.
    Returns (cleaned_text, again_threshold, rote).
    """
    again = 10
    rote = False
    text_lower = text.lower()

    if '8again' in text_lower or '8-again' in text_lower:
        again = 8
        text = text.replace('8again', '').replace('8-again', '').replace('8Again', '').replace('8-Again', '')
    elif '9again' in text_lower or '9-again' in text_lower:
        again = 9
        text = text.replace('9again', '').replace('9-again', '').replace('9Again', '').replace('9-Again', '')
    elif 'noagain' in text_lower or 'no-again' in text_lower:
        again = 11
        text = text.replace('noagain', '').replace('no-again', '').replace('noAgain', '').replace('no-Again', '')

    if 'rote' in text_lower:
        rote = True
        text = text.replace('rote', '').replace('Rote', '').replace('ROTE', '')

    return text.strip(), again, rote

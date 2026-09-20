"""The rules of The Long Climb, as pure functions.

Nothing here touches the database, the clock, or module-level state, and every
function that needs chance takes a ``random.Random``. That is what lets the
tests assert exact outcomes from a seed, and lets ``lib.climb.sim`` play
thousands of climbs with the same code the game runs.

Functions named ``apply_*`` mutate the :class:`Climber` they are given; the
rest compute.
"""

from dataclasses import dataclass, field
from enum import Enum
from random import Random

from lib.climb import data

CREATURE, GATEKEEPER, LADON, CLIMBER = "creature", "gatekeeper", "ladon", "climber"


@dataclass
class Climber:
    """Everything the rules need to know about a player's character."""

    calling: str = data.SPEAR
    level: int = 1
    xp: int = 0
    hp: int = 0
    weapon: int = 1                 # gear tiers, 1..12
    armour: int = 1
    purse: int = data.START_DRACHMAE
    vault: int = 0
    seeds: int = 0
    charm: int = 0
    rank: int = 0                   # calling rank, 0..40
    strength_gift: int = 0          # permanent gifts from the Orchard Gate
    defence_gift: int = 0
    hp_gift: int = 0
    ascents: int = 0
    fights_left: int = data.SLOPE_FIGHTS_PER_DAY
    duels_left: int = data.DUELS_PER_DAY
    skill_left: int = 0
    alive: bool = True
    gate_tried_today: bool = False


@dataclass
class Foe:
    """Whatever is on the other side of a fight."""

    name: str
    hp: int
    attack: int
    xp: int = 0
    drachmae: int = 0
    kind: str = CREATURE
    guard: int = 0                  # only other climbers have any


class Outcome(Enum):
    ONGOING = "ongoing"
    WON = "won"
    LOST = "lost"
    FLED = "fled"


@dataclass
class Fight:
    foe: Foe
    foe_hp: int
    can_run: bool = True
    lethal: bool = True             # gatekeepers leave you at 1 HP instead
    scorched: bool = False          # the foe's next blow is halved
    picked: int = 0                 # extra drachmae lifted by Quick Hands
    outcome: Outcome = Outcome.ONGOING
    # What happened, as (event, number) pairs, for the text layer to narrate.
    events: list[tuple[str, int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The climber
# ---------------------------------------------------------------------------

def new_climber(calling: str) -> Climber:
    if calling not in data.CALLINGS:
        raise ValueError(f"unknown calling: {calling!r}")
    climber = Climber(calling=calling)
    climber.hp = max_hp(climber)
    climber.skill_left = skill_uses_per_day(climber)
    return climber


def max_hp(c: Climber) -> int:
    return data.MAX_HP[c.level - 1] + c.hp_gift


def attack_power(c: Climber) -> int:
    return data.STRENGTH[c.level - 1] + c.strength_gift + data.WEAPON_POWER[c.weapon - 1]


def guard_power(c: Climber) -> int:
    return data.DEFENCE[c.level - 1] + c.defence_gift + data.ARMOUR_POWER[c.armour - 1]


def skill_uses_per_day(c: Climber) -> int:
    return 1 + c.rank // data.RANK_PER_EXTRA_USE


def title(ascents: int) -> str:
    return next(name for needed, name in data.TITLES if ascents >= needed)


def renown(c: Climber) -> int:
    """One number for the BBS's score table: any ascent outranks any level."""
    return c.ascents * (data.LEVELS + 1) * 100 + c.level * 100


def heads_left(fight: "Fight") -> int:
    """Ladon has a hundred heads; this many are still looking at you."""
    return max(1, -(-100 * fight.foe_hp // fight.foe.hp)) if fight.foe_hp > 0 else 0


def xp_to_next(level: int) -> int | None:
    """XP needed to face this band's gatekeeper; None at the top."""
    return data.XP_TO_NEXT[level - 1] if level < data.LEVELS else None


# ---------------------------------------------------------------------------
# Foes
# ---------------------------------------------------------------------------

def _toughness(ascents: int) -> float:
    return 1 + min(ascents, data.ASCENT_TOUGHNESS_CAP) * data.ASCENT_TOUGHNESS_STEP


def creature(band: int, rank: int, ascents: int = 0) -> Foe:
    """The creature of the given rank (1 weakest .. 8 strongest) in a band.

    Health scales with the climber's ascents; attack does not. Scaling both
    compounds, and made a sixth ascent impossible in simulation.
    """
    if not 1 <= band <= data.LEVELS or not 1 <= rank <= data.CREATURES_PER_BAND:
        raise ValueError(f"no creature at band {band}, rank {rank}")
    i = band - 1
    factor = data.RANK_FACTOR_BASE + data.RANK_FACTOR_STEP * (rank - 1)
    # Attack is pitched against a climber wearing this band's armour: enough to
    # get through the guard, plus a share of their health per blow.
    attack = (
        data.MAX_HP[i] * data.CREATURE_ATTACK * factor / 3.2
        + data.DEFENCE[i] / 2 + data.ARMOUR_POWER[i] / 2
    )
    return Foe(
        name=data.CREATURES[i][rank - 1],
        hp=round(data.MAX_HP[i] * data.CREATURE_HP * factor * _toughness(ascents)),
        attack=round(attack),
        xp=round(data.REF_XP[i] * factor),
        drachmae=round(data.REF_DRACHMAE[i] * factor),
    )


def random_creature(rng: Random, c: Climber) -> Foe:
    return creature(c.level, rng.randint(1, data.CREATURES_PER_BAND), c.ascents)


def gatekeeper(level: int, ascents: int = 0) -> Foe:
    """The gatekeeper at the top of a band: its strongest creature, and then some."""
    if not 1 <= level < data.LEVELS:
        raise ValueError(f"no gatekeeper above band {level}")
    strongest = creature(level, data.CREATURES_PER_BAND, ascents)
    return Foe(
        name=data.GATEKEEPERS[level - 1],
        hp=round(strongest.hp * data.GATEKEEPER_HP),
        attack=round(strongest.attack * data.GATEKEEPER_ATTACK),
        kind=GATEKEEPER,
    )


def ladon(ascents: int = 0) -> Foe:
    strongest = creature(data.LEVELS, data.CREATURES_PER_BAND)
    return Foe(
        name=data.BOSS,
        hp=round(data.MAX_HP[-1] * data.LADON_HP * _toughness(ascents)),
        attack=round(strongest.attack * data.LADON_ATTACK),
        kind=LADON,
    )


def can_face_gatekeeper(c: Climber) -> bool:
    needed = xp_to_next(c.level)
    return c.alive and needed is not None and c.xp >= needed and not c.gate_tried_today


def can_seek_ladon(c: Climber) -> bool:
    return c.alive and c.level == data.LEVELS and c.fights_left > 0 and not c.gate_tried_today


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------

def _roll(rng: Random, power: int) -> int:
    return rng.randint(max(1, power // 2), max(1, power))


def _foe_strikes(rng: Random, c: Climber, fight: Fight) -> None:
    blow = _roll(rng, fight.foe.attack)
    if fight.scorched:
        blow //= 2
        fight.scorched = False
    blow = max(1, blow - guard_power(c) // 2)
    c.hp -= blow
    fight.events.append(("foe_hits", blow))
    if c.hp <= 0:
        if fight.lethal:
            c.hp = 0
        else:
            c.hp = 1
        fight.outcome = Outcome.LOST
        fight.events.append(("you_fall", 0))


def _you_strike(rng: Random, c: Climber, fight: Fight, multiplier: int = 1, event: str = "you_hit") -> None:
    blow = _roll(rng, attack_power(c)) * multiplier
    if rng.random() < data.MIGHTY_BLOW_CHANCE:
        blow *= 2
        fight.events.append(("mighty", 0))
    blow = max(1, blow - fight.foe.guard // 2)
    fight.foe_hp -= blow
    fight.events.append((event, blow))
    if fight.foe_hp <= 0:
        fight.foe_hp = 0
        fight.outcome = Outcome.WON
        fight.events.append(("foe_falls", 0))


def open_fight(rng: Random, c: Climber, foe: Foe) -> Fight:
    """Begin a fight. Three times in ten the foe gets an opening blow.

    Followers of the Sandal are never caught off guard.
    """
    fight = Fight(
        foe=foe, foe_hp=foe.hp,
        can_run=foe.kind in (CREATURE, CLIMBER),
        lethal=foe.kind != GATEKEEPER,
    )
    ambushed = rng.random() >= data.FIRST_STRIKE_CHANCE
    if ambushed and c.calling != data.SANDAL:
        fight.events.append(("ambush", 0))
        _foe_strikes(rng, c, fight)
    return fight


def skills(c: Climber) -> tuple[str, ...]:
    """The skills this climber's calling and rank allow, whether or not uses remain."""
    if c.calling == data.SPEAR:
        return ("fury",)
    if c.calling == data.SANDAL:
        return ("quick_hands",)
    known = ["flame"]
    if c.rank >= data.MEND_RANK:
        known.append("mend")
    if c.rank >= data.SHADOW_RANK:
        known.append("shadow")
    return tuple(known)


def actions(c: Climber, fight: Fight) -> tuple[str, ...]:
    """What the climber may do this round. Anything else is not a valid request."""
    if fight.outcome is not Outcome.ONGOING:
        return ()
    allowed = ["attack"]
    if c.skill_left > 0:
        for skill in skills(c):
            if skill == "shadow" and not fight.can_run:
                continue
            if skill == "quick_hands" and fight.picked:
                continue
            allowed.append(skill)
    if fight.can_run:
        allowed.append("run")
    return tuple(allowed)


def take_turn(rng: Random, c: Climber, fight: Fight, action: str) -> Outcome:
    """Play one round: the climber's action, then the foe's blow if it still stands."""
    if action not in actions(c, fight):
        raise ValueError(f"cannot {action!r} now")
    fight.events.clear()

    if action == "run":
        sure_footed = c.calling == data.SANDAL and c.rank >= data.SURE_FOOT_RANK
        if sure_footed or rng.random() < data.RUN_CHANCE:
            fight.outcome = Outcome.FLED
            fight.events.append(("fled", 0))
            return fight.outcome
        fight.events.append(("run_failed", 0))
    elif action == "attack":
        _you_strike(rng, c, fight)
    else:
        c.skill_left -= 1
        if action == "fury":
            _you_strike(rng, c, fight, data.FURY_MULTIPLIER, "fury")
        elif action == "flame":
            _you_strike(rng, c, fight, data.FLAME_MULTIPLIER, "flame")
            fight.scorched = True
        elif action == "mend":
            healed = min(max_hp(c) - c.hp, round(max_hp(c) * data.MEND_SHARE))
            c.hp += healed
            fight.events.append(("mend", healed))
        elif action == "shadow":
            fight.outcome = Outcome.FLED
            fight.events.append(("shadow", 0))
            return fight.outcome
        elif action == "quick_hands":
            _you_strike(rng, c, fight, event="quick_hands")
            fight.picked = round(fight.foe.drachmae * data.QUICK_HANDS_SHARE)

    if fight.outcome is Outcome.ONGOING:
        _foe_strikes(rng, c, fight)
    return fight.outcome


# ---------------------------------------------------------------------------
# After the fight
# ---------------------------------------------------------------------------

@dataclass
class Spoils:
    xp: int = 0
    drachmae: int = 0
    seed: bool = False


def apply_victory(rng: Random, c: Climber, fight: Fight) -> Spoils:
    """Collect what a beaten creature was carrying."""
    if fight.outcome is not Outcome.WON:
        raise ValueError("the fight is not won")
    spoils = Spoils(xp=fight.foe.xp, drachmae=fight.foe.drachmae + fight.picked)
    if fight.foe.kind == CREATURE:
        spoils.seed = rng.random() < data.SEED_DROP_CHANCE
    c.xp += spoils.xp
    c.purse += spoils.drachmae
    c.seeds += spoils.seed
    return spoils


def apply_death(c: Climber) -> tuple[int, int]:
    """Out until dawn; the purse and a tenth of this level's XP are gone.

    Returns (drachmae lost, xp lost). The Vault is never touched.
    """
    lost_drachmae, lost_xp = c.purse, int(c.xp * data.DEATH_XP_LOSS)
    c.purse = 0
    c.xp -= lost_xp
    c.hp = 0
    c.alive = False
    return lost_drachmae, lost_xp


def apply_level_up(c: Climber) -> None:
    """Past the gatekeeper: next band, healed, and a little wiser in your calling."""
    if c.level >= data.LEVELS:
        raise ValueError("already at the garden wall")
    c.level += 1
    c.xp = 0
    c.rank = min(data.MAX_RANK, c.rank + 1)
    c.hp = max_hp(c)


def apply_ascent(c: Climber) -> None:
    """Ladon is dead. Tomorrow you wake in the Foothills.

    Kept: the ascent, calling and rank, charm, seeds and what they bought.
    Lost: level, XP, gear, and every coin — the Vault too.
    """
    c.ascents += 1
    c.level, c.xp = 1, 0
    c.weapon = c.armour = 1
    c.purse, c.vault = data.START_DRACHMAE, 0
    c.hp = max_hp(c)


def apply_dawn(c: Climber) -> None:
    """A new day: the dead rise, wounds close, and the day's allowances return."""
    c.alive = True
    c.hp = max_hp(c)
    c.fights_left = data.SLOPE_FIGHTS_PER_DAY
    c.duels_left = data.DUELS_PER_DAY
    c.skill_left = skill_uses_per_day(c)
    c.gate_tried_today = False


# ---------------------------------------------------------------------------
# Town
# ---------------------------------------------------------------------------

def heal_price_per_point(level: int) -> float:
    """Drachmae per hit point, so a full heal costs about two kills' coin."""
    i = level - 1
    return max(1.0, round(data.FULL_HEAL_IN_KILLS * data.REF_DRACHMAE[i] / data.MAX_HP[i], 1))


def heal_cost(c: Climber, points: int) -> int:
    return round(points * heal_price_per_point(c.level))


def affordable_healing(c: Climber, funds: int) -> int:
    """The most hit points these funds will buy, capped at what is missing."""
    return min(max_hp(c) - c.hp, int(funds / heal_price_per_point(c.level)))


def apply_healing(c: Climber, points: int) -> int:
    """Heal from the purse. Returns the price paid."""
    if not c.alive:
        raise ValueError("Akeso cannot help the dead")
    if points < 1 or points > max_hp(c) - c.hp:
        raise ValueError("nothing to heal")
    cost = heal_cost(c, points)
    if cost > c.purse:
        raise ValueError("not enough drachmae in hand")
    c.purse -= cost
    c.hp += points
    return cost


def _gear(kind: str) -> tuple[tuple[int, ...], str]:
    if kind == "weapon":
        return data.WEAPON_PRICE, "weapon"
    if kind == "armour":
        return data.ARMOUR_PRICE, "armour"
    raise ValueError(f"unknown gear: {kind!r}")


def gear_cost(c: Climber, kind: str, tier: int) -> int:
    """Price of a tier after trading in what the climber carries now."""
    prices, attr = _gear(kind)
    if not 1 <= tier <= data.LEVELS:
        raise ValueError(f"no such tier: {tier}")
    return prices[tier - 1] - int(prices[getattr(c, attr) - 1] * data.TRADE_IN)


def can_buy(c: Climber, kind: str, tier: int) -> bool:
    """Better than what you have, at most one tier above your level, and affordable."""
    _, attr = _gear(kind)
    return (
        c.alive
        and getattr(c, attr) < tier <= min(data.LEVELS, c.level + 1)
        and gear_cost(c, kind, tier) <= c.purse
    )


def apply_purchase(c: Climber, kind: str, tier: int) -> int:
    if not can_buy(c, kind, tier):
        raise ValueError(f"cannot buy {kind} tier {tier}")
    cost = gear_cost(c, kind, tier)
    c.purse -= cost
    setattr(c, _gear(kind)[1], tier)
    return cost


def can_take_gift(c: Climber) -> bool:
    return c.alive and c.seeds >= data.SEEDS_PER_GIFT


def apply_gift(c: Climber, gift: str) -> int:
    """Trade two seeds for a permanent gift that survives every ascent.

    Returns the size of the gift. Vigour raises current as well as maximum
    hit points, so it never leaves you looking wounded.
    """
    if gift not in data.GIFTS:
        raise ValueError(f"unknown gift: {gift!r}")
    if not can_take_gift(c):
        raise ValueError("not enough seeds")
    size = data.GIFTS[gift]
    c.seeds -= data.SEEDS_PER_GIFT
    if gift == "strength":
        c.strength_gift += size
    elif gift == "defence":
        c.defence_gift += size
    else:
        c.hp_gift += size
        c.hp += size
    return size


def gear_on_offer(c: Climber, kind: str) -> list[tuple[int, int, bool]]:
    """Tiers a shop will show: (tier, price after trade-in, affordable now?)."""
    _, attr = _gear(kind)
    top = min(data.LEVELS, c.level + 1)
    return [
        (tier, gear_cost(c, kind, tier), gear_cost(c, kind, tier) <= c.purse)
        for tier in range(getattr(c, attr) + 1, top + 1)
    ]


def apply_deposit(c: Climber, amount: int) -> None:
    if not 0 < amount <= c.purse:
        raise ValueError("cannot deposit that")
    c.purse -= amount
    c.vault += amount


def apply_withdrawal(c: Climber, amount: int) -> None:
    if not 0 < amount <= c.vault:
        raise ValueError("cannot withdraw that")
    c.vault -= amount
    c.purse += amount

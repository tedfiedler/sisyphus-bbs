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
    # Today only; all cleared at dawn.
    sung_today: bool = False
    hp_boost: int = 0               # "Bronze and Breath": extra max HP until dawn
    mercy: bool = False             # "A Stone Remembers": the next lethal fight cannot kill
    room: bool = False              # sleeping at the Lethe House tonight, not the Camp
    wall_today: int = 0
    knucklebones_today: int = 0
    key: bool = False               # Nikandros' key: one room-sleeper may be robbed tonight
    courted_today: bool = False
    flirted_today: bool = False
    # The heart. All of it survives an ascent. `heart` is "" (free),
    # "npc:kalliste" / "npc:theron", or "player:<user id>"; `courtship` is how
    # many of the eight steps are done with a regular; `wed` means married to
    # whoever `heart` names. `open_heart` is the opt-in: only then can other
    # climbers flirt with you, or you with them. It starts closed.
    heart: str = ""
    courtship: int = 0
    wed: bool = False
    open_heart: bool = False
    # Known for good, through every ascent: the way to the Shepherds' Fire.
    fire_known: bool = False


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
    mercy: bool = False             # a blessing: a killing blow ends the fight at 1 HP instead
    scorched: bool = False          # the foe's next blow is halved
    picked: int = 0                 # extra drachmae lifted by Quick Hands
    outcome: Outcome = Outcome.ONGOING
    # What happened, as (event, number) pairs, for the text layer to narrate.
    events: list[tuple[str, int]] = field(default_factory=list)
    target_id: int | None = None    # the sleeping climber being robbed, if that is what this is


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
    return data.MAX_HP[c.level - 1] + c.hp_gift + c.hp_boost


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
        if fight.mercy:
            c.hp = 1
            fight.outcome = Outcome.FLED
            fight.events.append(("stone_saves", 0))
            return
        c.hp = 0 if fight.lethal else 1
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
    if c.mercy and fight.lethal:          # not wasted on a gatekeeper, who kills nobody
        fight.mercy, c.mercy = True, False
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
    c.sung_today = c.mercy = c.room = c.key = False
    c.courted_today = c.flirted_today = False
    c.hp_boost = c.wall_today = c.knucklebones_today = 0
    c.hp = max_hp(c)


# ---------------------------------------------------------------------------
# The Slopes: events
# ---------------------------------------------------------------------------

@dataclass
class EventResult:
    """What came of an event: a line of text by key, a number for it, maybe a fight."""

    key: str
    n: int = 0
    foe: Foe | None = None
    news: bool = False              # worth the Herald's breath


def is_event(rng: Random) -> bool:
    return rng.random() < data.EVENT_CHANCE


def roll_event(rng: Random, c: Climber) -> str:
    pick = rng.randint(1, 100)
    for name, weight in data.EVENTS:
        if pick <= weight:
            # Finding the Fire twice is just finding your way; have an eagle instead.
            return "eagle" if name == "smoke" and c.fire_known else name
        pick -= weight
    raise AssertionError("event weights do not sum to 100")


def _lose_share(c: Climber, share: float) -> int:
    """Lose a share of max HP, but never the last point: events do not kill."""
    lost = min(c.hp - 1, max(1, round(max_hp(c) * share)))
    c.hp -= lost
    return lost


def satyr_max_stake(c: Climber) -> int:
    return min(c.purse, _kills_worth(c, data.SATYR_MAX_STAKE_KILLS))


def event_options(c: Climber, kind: str) -> tuple[str, ...]:
    """The choices an event puts to this climber. The last always walks away."""
    options = list(data.EVENT_OPTIONS[kind])
    if kind == "satyr" and c.purse < 1:
        options.remove("wager")
    if kind == "shrine" and c.purse < _kills_worth(c, data.SHRINE_OFFERING_KILLS):
        options.remove("offer")
    if kind == "toll" and c.purse < _kills_worth(c, data.TOLL_KILLS):
        options.remove("pay")
    return tuple(options)


def resolve_event(rng: Random, c: Climber, kind: str, option: str = "", amount: int = 0) -> EventResult:
    """Carry out an instant event, or the option chosen for one that asked."""
    if kind in data.INSTANT_EVENTS:
        if kind == "spring":
            healed = max_hp(c) - c.hp
            c.hp = max_hp(c)
            return EventResult("spring", healed)
        if kind == "rockslide":
            return EventResult("rockslide", _lose_share(c, data.ROCKSLIDE_SHARE))
        if kind == "eagle":
            found = _kills_worth(c, data.EAGLE_KILLS)
            c.purse += found
            return EventResult("eagle", found)
        if kind == "oracle":
            needed = xp_to_next(c.level)
            if needed is None:
                return EventResult("oracle_garden")
            return EventResult("oracle", max(0, needed - c.xp))
        if kind == "shade":
            c.rank = min(data.MAX_RANK, c.rank + 1)
            return EventResult("shade", c.rank)
        c.fire_known = True
        return EventResult("smoke")

    if option not in event_options(c, kind):
        raise ValueError(f"cannot {option!r} at {kind!r}")
    if option == event_options(c, kind)[-1]:
        return EventResult(f"{kind}_{option}")

    if kind == "boulder":
        lost = _lose_share(c, data.BOULDER_HP_SHARE)
        c.xp += data.REF_XP[c.level - 1]
        if rng.random() < data.BOULDER_LESSON_CHANCE:
            c.rank = min(data.MAX_RANK, c.rank + 1)
            return EventResult("boulder_lesson", lost)
        return EventResult("boulder_help", lost)

    if kind == "wall":
        if rng.random() < data.WALL_GARDENER_CHANCE:
            strongest = creature(c.level, data.CREATURES_PER_BAND, c.ascents)
            gardener = Foe(
                name="Furious Gardener",
                hp=round(strongest.hp * data.GARDENER_FACTOR),
                attack=round(strongest.attack * data.GARDENER_FACTOR),
                xp=strongest.xp, drachmae=strongest.drachmae,
            )
            return EventResult("wall_gardener", foe=gardener)
        c.seeds += 1
        return EventResult("wall_take", c.seeds)

    if kind == "satyr":
        if not 1 <= amount <= satyr_max_stake(c):
            raise ValueError("not a stake you can make")
        chance = min(data.SATYR_MAX_CHANCE, data.SATYR_BASE_CHANCE + data.SATYR_CHARM_STEP * c.charm)
        if rng.random() < chance:
            c.purse += amount
            return EventResult("satyr_won", amount)
        c.purse -= amount
        return EventResult("satyr_lost", amount)

    if kind == "kid":
        if option == "carry":
            c.charm += 1
            return EventResult("kid_carry", c.charm, news=True)
        price = _kills_worth(c, data.KID_SALE_KILLS)
        c.purse += price
        return EventResult("kid_sell", price)

    if kind == "shrine":
        c.purse -= _kills_worth(c, data.SHRINE_OFFERING_KILLS)
        if rng.random() < data.SHRINE_CHANCE:
            c.fights_left += data.SHRINE_EXTRA_FIGHTS
            return EventResult("shrine_pleased", data.SHRINE_EXTRA_FIGHTS)
        return EventResult("shrine_silent")

    if kind == "hive":
        if rng.random() < data.HIVE_HONEY_CHANCE:
            c.hp_gift += data.HIVE_HONEY_HP
            c.hp += data.HIVE_HONEY_HP
            return EventResult("hive_honey", data.HIVE_HONEY_HP)
        return EventResult("hive_stung", _lose_share(c, data.HIVE_STING_SHARE))

    # toll
    if option == "pay":
        toll = _kills_worth(c, data.TOLL_KILLS)
        c.purse -= toll
        return EventResult("toll_pay", toll)
    strongest = creature(c.level, data.CREATURES_PER_BAND, c.ascents)
    strongest.name = "Toll-Taker"
    strongest.drachmae *= data.TOLL_FIGHT_PAYS
    return EventResult("toll_fight", foe=strongest)


# ---------------------------------------------------------------------------
# Courtship
# ---------------------------------------------------------------------------

def courting(c: Climber) -> str | None:
    """The regular this climber is courting or married to, if any."""
    return c.heart.removeprefix("npc:") if c.heart.startswith("npc:") else None


def spouse_id(c: Climber) -> int | None:
    """The user id of the climber this one is married to, if any."""
    return int(c.heart.removeprefix("player:")) if c.wed and c.heart.startswith("player:") else None


def court_chance(c: Climber, step: int) -> float:
    surplus = c.charm - data.COURTSHIP_CHARM[step - 1]
    chance = data.COURT_BASE_CHANCE + data.COURT_CHARM_STEP * surplus
    return max(data.COURT_MIN_CHANCE, min(data.COURT_MAX_CHANCE, chance))


def gift_price(c: Climber) -> int:
    return _kills_worth(c, data.GIFT_PRICE_IN_KILLS)


def why_not_court(c: Climber, regular: str) -> str | None:
    """None if the climber may try the next step with this regular today."""
    if regular not in data.REGULARS:
        raise ValueError(f"nobody here by that name: {regular!r}")
    if not c.alive or c.courted_today:
        return "today"
    if c.heart.startswith("player:"):
        return "taken"
    if c.wed:
        return "wed"
    if courting(c) not in (None, regular):
        return "other"                      # leave one before courting the other
    step = c.courtship + 1
    if c.charm < data.COURTSHIP_CHARM[step - 1]:
        return "charm"
    if step == data.GIFT_STEP and c.purse < gift_price(c):
        return "gift"
    return None


@dataclass
class Courting:
    step: int
    won: bool
    xp: int = 0
    charmed: bool = False
    married: bool = False


def apply_courtship(rng: Random, c: Climber, regular: str) -> Courting:
    """Try the next step with a regular. One attempt a day, win or lose."""
    if why_not_court(c, regular) is not None:
        raise ValueError("not today")
    step = c.courtship + 1
    c.courted_today = True
    c.heart = f"npc:{regular}"
    if step == data.GIFT_STEP:
        c.purse -= gift_price(c)            # the gift is given either way
    if rng.random() >= court_chance(c, step):
        return Courting(step, won=False)
    c.courtship = step
    xp = data.REF_XP[c.level - 1] * data.COURT_XP_KILLS
    c.xp += xp
    charmed = rng.random() < data.COURT_CHARM_CHANCE
    c.charm += charmed
    c.wed = step == len(data.COURTSHIP_CHARM)
    return Courting(step, won=True, xp=xp, charmed=charmed, married=c.wed)


def apply_parting(c: Climber) -> None:
    """End whatever this climber's heart is tied to. It costs a little Charm."""
    if not c.heart:
        raise ValueError("nothing to end")
    c.heart, c.courtship, c.wed = "", 0, False
    c.charm = max(0, c.charm - data.PARTING_CHARM_LOSS)


def flirt_counts(my_last: str | None, their_last: str | None) -> bool:
    """Does a flirt today raise affinity? Only if they have answered since my last.

    Days are ISO strings. One-sided attention never builds anything: the other
    person has to have flirted back, and again after each of mine.
    """
    return their_last is not None and (my_last is None or their_last >= my_last)


def why_not_flirt(me: Climber, them_open: bool) -> str | None:
    if not me.alive or me.flirted_today:
        return "today"
    if not me.open_heart:
        return "closed"                     # you must be open to it yourself
    if not them_open:
        return "their_door"
    if me.wed:
        return "wed"
    return None


def can_propose(me: Climber, affinity: int, their_heart_free: bool) -> bool:
    return (
        me.alive and me.open_heart and not me.wed and their_heart_free
        and affinity >= data.AFFINITY_TO_PROPOSE and me.charm >= data.CHARM_TO_PROPOSE
    )


def apply_wedding(c: Climber, spouse_user_id: int) -> None:
    """Marry another climber. Any half-finished courtship of a regular is dropped."""
    if c.wed:
        raise ValueError("already married")
    c.heart, c.courtship, c.wed = f"player:{spouse_user_id}", 0, True


def apply_spouse_dawn(c: Climber, spouse_played_yesterday: bool = False) -> tuple[str, int] | None:
    """What marriage brings at dawn: (kind, amount), or None."""
    if not c.wed:
        return None
    if courting(c):
        gift = _kills_worth(c, data.SPOUSE_GIFT_KILLS)
        c.purse += gift
        return "gift", gift
    if spouse_played_yesterday:
        c.fights_left += data.SPOUSE_EXTRA_FIGHTS
        return "fights", data.SPOUSE_EXTRA_FIGHTS
    return None


# ---------------------------------------------------------------------------
# The Camp: robbing the sleeping
# ---------------------------------------------------------------------------

def is_sheltered(room: bool, days_since_played: int) -> bool:
    """A night's rent covers tonight and all of tomorrow, and no longer.

    Dawn is applied lazily, so a climber who rented a room and has not been
    back still has ``room`` set. Without the limit, one night's rent would
    protect an absent climber for ever.
    """
    return room and days_since_played <= 1


def as_they_sleep(target: Climber, days_since_played: int) -> Climber:
    """The target as they would wake: dawn applied if theirs is overdue."""
    from copy import copy

    sleeper = copy(target)
    if days_since_played >= 1:
        room = sleeper.room
        apply_dawn(sleeper)
        sleeper.room = room                 # shelter is judged by is_sheltered, not by dawn
    return sleeper


def why_not_rob(
    attacker: Climber, target: Climber, *, days_since_played: int, minutes_since_seen: float,
    days_since_joined: float, already_today: bool, married: bool = False,
) -> str | None:
    """None if *attacker* may rob *target* now, else a short reason."""
    sleeper = as_they_sleep(target, days_since_played)
    if not attacker.alive or attacker.duels_left < 1:
        return "spent"
    if married:
        return "spouse"
    if not sleeper.alive:
        return "dead"
    if minutes_since_seen < data.AWAKE_MINUTES:
        return "awake"
    if days_since_played >= data.IDLE_DAYS:
        return "away"
    if days_since_joined < data.NEWCOMER_DAYS:
        return "newcomer"
    if target.level < attacker.level - data.ROB_LEVELS_BELOW:
        return "beneath"
    if already_today:
        return "already"
    if is_sheltered(target.room, days_since_played) and not attacker.key:
        return "sheltered"
    return None


def sleeper_as_foe(target: Climber, name: str, days_since_played: int) -> Foe:
    """A sleeping climber as the game will play them: their own arm and armour."""
    sleeper = as_they_sleep(target, days_since_played)
    return Foe(
        name=name, kind=CLIMBER,
        hp=max(1, sleeper.hp), attack=attack_power(sleeper), guard=guard_power(sleeper),
        xp=data.REF_XP[target.level - 1] * data.ROB_XP_KILLS,
        drachmae=0,                         # the purse is a transfer, settled against the real row
    )


def apply_robbed(victim: Climber) -> tuple[int, int]:
    """What being robbed costs: the purse and a little XP — never a day."""
    taken, lost_xp = victim.purse, int(victim.xp * data.ROB_XP_LOSS)
    victim.purse = 0
    victim.xp -= lost_xp
    return taken, lost_xp


def apply_defended(victim: Climber, robbers_purse: int, robber_level: int) -> int:
    """The robber lost. Their purse is yours, and you learned something in your sleep."""
    xp = data.REF_XP[robber_level - 1] * data.DEFENDED_XP_KILLS
    victim.purse += robbers_purse
    victim.xp += xp
    return xp


def key_price(c: Climber) -> int:
    return _kills_worth(c, data.KEY_PRICE_IN_KILLS)


def apply_key(c: Climber) -> int:
    if not c.alive or c.key:
        raise ValueError("no key to buy")
    price = key_price(c)
    if price > c.purse:
        raise ValueError("not enough drachmae in hand")
    c.purse -= price
    c.key = True
    return price


# ---------------------------------------------------------------------------
# The Shepherds' Fire
# ---------------------------------------------------------------------------

def knucklebones_max_stake(c: Climber) -> int:
    if not c.alive or c.knucklebones_today >= data.KNUCKLEBONES_PER_DAY:
        return 0
    return min(c.purse, _kills_worth(c, data.KNUCKLEBONES_MAX_STAKE_KILLS))


def apply_knucklebones(rng: Random, c: Climber, stake: int) -> bool:
    """An even-money throw. Returns True on a win."""
    if not 1 <= stake <= knucklebones_max_stake(c):
        raise ValueError("not a stake you can make")
    c.knucklebones_today += 1
    won = rng.random() < data.KNUCKLEBONES_WIN_CHANCE
    c.purse += stake if won else -stake
    return won


def apply_new_calling(c: Climber, calling: str) -> None:
    """Change calling at the Fire. Half of what you knew comes with you."""
    if calling not in data.CALLINGS or calling == c.calling or not c.alive:
        raise ValueError("not a calling you can take up")
    c.calling = calling
    c.rank //= 2
    c.skill_left = min(c.skill_left, skill_uses_per_day(c))


# ---------------------------------------------------------------------------
# The Lethe House
# ---------------------------------------------------------------------------

def _kills_worth(c: Climber, kills: float) -> int:
    return max(1, round(data.REF_DRACHMAE[c.level - 1] * kills))


def apply_song(rng: Random, c: Climber) -> tuple[str, int]:
    """Orpheus sings, once a day. Returns (song, size of its blessing)."""
    if not c.alive or c.sung_today:
        raise ValueError("Orpheus has sung for you today")
    c.sung_today = True
    pick, song = rng.random(), data.SONGS[-1][0]
    for name, share in data.SONGS:
        if pick < share:
            song = name
            break
        pick -= share

    if song == "road":
        c.fights_left += data.ROAD_EXTRA_FIGHTS
        return song, data.ROAD_EXTRA_FIGHTS
    if song == "bronze":
        c.hp_boost = round(data.MAX_HP[c.level - 1] * data.BRONZE_HP_BOOST)
        c.hp = max_hp(c)
        return song, c.hp_boost
    if song == "ferryman":
        purse = _kills_worth(c, data.FERRYMAN_KILLS)
        c.purse += purse
        return song, purse
    if song == "goatherd":
        xp = data.REF_XP[c.level - 1]
        c.xp += xp
        return song, xp
    if song == "sisters":
        c.skill_left += 1
        return song, 1
    if song == "stone":
        c.mercy = True
        return song, 0
    if song == "eurydice":
        c.charm += 1
        return song, 1
    return song, 0                        # he broke a string


def room_price(c: Climber) -> int:
    return _kills_worth(c, data.ROOM_PRICE_IN_KILLS)


def apply_room(c: Climber) -> int:
    """A bed at the Lethe House: nobody robs you tonight. Returns the price."""
    if not c.alive or c.room:
        raise ValueError("no room to take")
    price = room_price(c)
    if price > c.purse:
        raise ValueError("not enough drachmae in hand")
    c.purse -= price
    c.room = True
    return price


def wine_price(c: Climber) -> int:
    return _kills_worth(c, data.WINE_PRICE_IN_KILLS)


def apply_wine(c: Climber) -> tuple[int, int]:
    """A cup of wine. Returns (price, hit points restored)."""
    price = wine_price(c)
    if not c.alive or price > c.purse:
        raise ValueError("no wine for you")
    healed = min(max_hp(c) - c.hp, max(1, round(max_hp(c) * data.WINE_HEAL_SHARE)))
    c.purse -= price
    c.hp += healed
    return price, healed


def clean_wall_line(words: str) -> str:
    """Tidy what someone wants to scratch into the wall, or raise ValueError."""
    # Whitespace first: a newline is "unprintable", and dropping it outright
    # would glue the words on either side of it together.
    words = " ".join(words.split())
    words = "".join(ch for ch in words if ch.isprintable())
    if not 1 <= len(words) <= data.WALL_LINE_LENGTH:
        raise ValueError("too short or too long")
    return words


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

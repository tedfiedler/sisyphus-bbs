"""The five jarls of the coast, and their habits.

Each habit is a function that spends a realm's turns for one day, using only
the public rules, so a computer-run jarl can do nothing a player could not. The
same functions drive the simulator's players, which is how the balance tests
ask whether any one way of playing always wins.

``sail`` is passed in: it takes (kind, attacker, defender, party) and returns
the Settlement, or None if the rules refused the sailing, and it is the
caller's job to apply the settlement to the real defender. Locally that is
``rules.apply_settlement``; on a board with realms abroad it may be a message.
"""

from random import Random

from lib.fjords import data, rules
from lib.fjords.rules import FARMS, LONGHOUSES, RAID, TAKE, WOODS, NotAllowed, Realm


def _try(fn, *args) -> bool:
    try:
        fn(*args)
        return True
    except NotAllowed:
        return False


def _guard_wanted(r: Realm, share: float, day: int = 0) -> int:
    """A jarl raided this week wants a full guard, whatever their habit."""
    if day and day - r.raided_day <= 5 and r.raided_day:
        share = max(share, 1.0)
    return int(r.land * share)


def _wall_up(r: Realm, day: int) -> bool:
    """After a raid, a palisade to level two before anything else."""
    return (r.raided_day and day - r.raided_day <= 5 and r.palisade < 2
            and r.silver >= rules.palisade_cost(r) and _try(rules.apply_palisade, r))


def _grow(r: Realm, day: int, want_woods: bool = False) -> bool:
    """One step of an economy: roofs when full, then a farm (or wood) on wild land, else clear."""
    if r.folk >= r.roofs * 0.9:
        if r.wild and _try(rules.apply_raise, r, LONGHOUSES):
            return True
        if _try(rules.apply_clear, r, day):
            return True
    if r.wild:
        use = WOODS if want_woods and r.woods < r.farms // 3 else FARMS
        if _try(rules.apply_raise, r, use):
            return True
    return _try(rules.apply_clear, r, day)


def _fleet_for(r: Realm) -> bool:
    return r.hold < r.huscarls and _try(rules.apply_ship, r)


def _army_for(r: Realm, others: list, ratio: float) -> int:
    """Huscarls enough to beat the softest target at the given ratio, with a margin; at least a fleet's worth."""
    softest = min((rules.strength_at_home(o) for _, o in others), default=0)
    return max(data.SHIP_HOLD, int(softest * ratio * 1.15 / data.HUSCARL_STRENGTH) + 1)


def farmer(r: Realm, others: list, day: int, rng: Random, sail) -> None:
    """Clears, builds, keeps a guard of half the steadings, never sails, feasts when rich."""
    while r.turns:
        if _wall_up(r, day):
            continue
        if r.huscarls < _guard_wanted(r, 0.5, day) and _try(rules.apply_train, r, 10):
            continue
        if not r.feasted and r.silver > 400 and _try(rules.apply_feast, r):
            continue
        if not _grow(r, day):
            break


def turtle(r: Realm, others: list, day: int, rng: Random, sail) -> None:
    """Palisade first, huscarls at home, then farms. Never sails."""
    while r.turns:
        if r.palisade < data.PALISADE_MAX and r.silver >= rules.palisade_cost(r) + 100 and _try(rules.apply_palisade, r):
            continue
        if r.huscarls < _guard_wanted(r, 1.0) and _try(rules.apply_train, r, 10):
            continue
        if not _grow(r, day):
            break


def raider(r: Realm, others: list, day: int, rng: Random, sail) -> None:
    """Ships and huscarls; raids the richest jarl it may, three times a day; reinvests the loot."""
    while r.turns:
        if _fleet_for(r):
            continue
        if r.folk > 300 and r.huscarls < _army_for(r, others, 1.0) and _try(rules.apply_train, r, 20):
            continue
        # The richest hold it can expect to beat; a raider who loses fleets is no raider.
        party = min(r.huscarls, r.hold)
        targets = sorted(((o_id, o) for o_id, o in others
                          if rules.strength_of_party(party) >= rules.strength_at_home(o) * 1.15),
                         key=lambda p: -(p[1].silver + p[1].grain + p[1].timber))
        sailed = False
        for o_id, o in targets:
            if party >= data.MIN_RAID_PARTY and sail(RAID, r, o_id, party) is not None:
                sailed = True
                break
        if sailed:
            continue
        if not _grow(r, day, want_woods=True):
            break


def conqueror(r: Realm, others: list, day: int, rng: Random, sail) -> None:
    """Takes land from the weakest defended realm it can beat decisively."""
    while r.turns:
        if _fleet_for(r):
            continue
        if r.folk > 300 and r.huscarls < _army_for(r, others, data.TAKE_RATIO) and _try(rules.apply_train, r, 20):
            continue
        party = min(r.huscarls, r.hold)
        targets = sorted(((o_id, o) for o_id, o in others), key=lambda p: rules.strength_at_home(p[1]))
        sailed = False
        for o_id, o in targets:
            if party >= data.MIN_TAKE_PARTY and rules.strength_of_party(party) >= rules.strength_at_home(o) * data.TAKE_RATIO * 1.1:
                if sail(TAKE, r, o_id, party) is not None:
                    sailed = True
                    break
        if sailed:
            continue
        if not _grow(r, day):
            break


def trader(r: Realm, others: list, day: int, rng: Random, sail) -> None:
    """Orm minds his booths: woods and farms, a guard, and nothing more."""
    while r.turns:
        if _wall_up(r, day):
            continue
        if r.huscarls < _guard_wanted(r, 0.5, day) and _try(rules.apply_train, r, 10):
            continue
        if not _grow(r, day, want_woods=True):
            break


HABITS = {
    data.FARMER: farmer, data.RAIDER: raider, data.CONQUEROR: conqueror,
    data.TURTLE: turtle, data.TRADER: trader,
}


def take_turns(r: Realm, others: list, day: int, rng: Random, sail) -> None:
    """Spend a computer-run jarl's turns for the day. ``others`` is [(id, Realm), ...]."""
    HABITS[r.npc](r, others, day, rng, sail)

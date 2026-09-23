"""Balance simulator: plays whole years of Nine Fjords with the real rules.

    python -m lib.fjords.sim            # summary over 100 seeded years
    python -m lib.fjords.sim 20         # fewer, faster

Every realm, player or computer-run, is played by one of the habits in
``lib.fjords.npc``, so the question the simulator answers is the one the
design asks: does any one way of playing always win, does anyone get erased,
and does a farmer grow at the pace intended. ``tests/test_fjords_balance.py``
holds the answers to the targets in the design's §16.
"""

import statistics
import sys
from random import Random

from lib.fjords import data, npc, rules
from lib.fjords.rules import Market, Realm


class Coast:
    """A whole coast for one year: realms by id, the market, the day."""

    def __init__(self, habits: dict[str, str], seed: int = 1):
        self.rng = Random(seed)
        self.realms: dict[str, Realm] = {name: rules.new_realm(day=1, npc=habit) for name, habit in habits.items()}
        self.market = Market()
        self.day = 1
        self.log: list[tuple] = []

    def sail(self, kind, attacker: Realm, defender_id: str, party: int):
        defender = self.realms[defender_id]
        if rules.may_sail(attacker, defender, defender_id, self.day):
            return None
        try:
            settlement = rules.sail(kind, attacker, defender, defender_id, party, self.day, self.rng)
        except rules.NotAllowed:
            return None
        rules.apply_settlement(defender, settlement, self.day)
        self.log.append((self.day, kind, defender_id, settlement.won, settlement.ratio))
        return settlement

    def play_day(self, absent: set[str] = frozenset()):
        rules.apply_market_dawn(self.market)
        for name, r in self.realms.items():
            if name not in absent:
                # A jarl back from days away gets every missed dawn, in order.
                for day in range(r.last_day + 1, self.day + 1):
                    rules.apply_dawn(r, day, self.rng, self.market)
                rules.apply_song(r, self.day)
        # Who plays first in a day is luck, as it is on a real board.
        order = list(self.realms)
        self.rng.shuffle(order)
        for name in order:
            if name in absent:
                continue
            r = self.realms[name]
            others = [(o_id, o) for o_id, o in self.realms.items() if o_id != name]
            npc.take_turns(r, others, self.day, self.rng, self.sail)
        self.day += 1

    def play_year(self, absent_on=None):
        """``absent_on`` maps a name to a predicate on the day: True means they did not play."""
        for _ in range(data.DAYS_IN_YEAR):
            absent = {name for name, skip in (absent_on or {}).items() if skip(self.day)}
            self.play_day(absent)
        return self

    def standings(self) -> list[tuple[str, int]]:
        return sorted(((name, rules.yule_renown(r, self.day)) for name, r in self.realms.items()), key=lambda p: -p[1])


FOUR = {"farmer": data.FARMER, "raider": data.RAIDER, "conqueror": data.CONQUEROR, "turtle": data.TURTLE}


def farmer_alone(seed: int = 1) -> Realm:
    coast = Coast({"farmer": data.FARMER}, seed).play_year()
    return coast.realms["farmer"]


def years(n: int, habits: dict[str, str] = FOUR, seed: int = 0) -> list[Coast]:
    return [Coast(habits, seed + i).play_year() for i in range(n)]


def repel_rate(n: int = 200, seed: int = 100) -> float:
    """How often a well-kept hold turns back a raider of equal renown."""
    repelled = 0
    for i in range(n):
        rng = Random(seed + i)
        home = rules.new_realm()
        home.huscarls, home.palisade = home.land // 2, 3
        raider = rules.new_realm()
        raider.ships = 5
        # Give the raider huscarls until the two renowns match.
        while rules.renown(raider) < rules.renown(home):
            raider.huscarls += 1
        party = min(raider.huscarls, raider.hold)
        s = rules.sail(rules.RAID, raider, home, "home", party, 11, rng)
        repelled += not s.won
    return repelled / n


def summary(n: int = 100) -> str:
    coasts = years(n)
    wins: dict[str, int] = {}
    erased = 0
    for c in coasts:
        wins[c.standings()[0][0]] = wins.get(c.standings()[0][0], 0) + 1
        erased += any(r.land < 10 or r.folk <= data.FOLK_FLOOR for r in c.realms.values())
    alone = [farmer_alone(i).land for i in range(20)]
    lines = [
        f"{n} years, four habits: wins {dict(sorted(wins.items()))}",
        f"realms erased in any year: {erased}",
        f"a farmer alone reaches {statistics.median(alone):.0f} steadings (min {min(alone)}, max {max(alone)})",
        f"a well-kept hold repels an equal raider {repel_rate():.0%} of the time",
    ]
    last = coasts[0]
    for name, ren in last.standings():
        r = last.realms[name]
        lines.append(f"  {name:10s} renown {ren:5d}  land {r.land:3d}  folk {r.folk:4d}  huscarls {r.huscarls:3d}  "
                     f"ships {r.ships}  silver {r.silver:7.0f}  honour {r.honour:3d}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary(int(sys.argv[1]) if len(sys.argv) > 1 else 100))

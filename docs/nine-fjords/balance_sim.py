#!/usr/bin/env python3
"""A rough model of one round of Nine Fjords, to size the economy before it is built.

Not the game: a spreadsheet with a loop. Four jarls with fixed habits play a
30-day round against each other. The point is to see that a farmer's realm
grows steadily, that a raider can hurt a farmer without erasing him, that a
turtle survives, and that nobody's silver goes to infinity.

    python docs/jarldoms/balance_sim.py
"""
import random
from dataclasses import dataclass, field

DAYS = 30
TURNS_PER_DAY, TURN_CAP = 12, 36

# --- the economy per dawn -------------------------------------------------
GRAIN_PER_FARM = 12
TIMBER_PER_WOOD = 6
GRAIN_PER_FOLK = 0.10          # ten folk eat one grain a day
GRAIN_PER_HUSCARL = 0.30
TAX_PER_FOLK = 1.0
GRAIN_PRICE, TIMBER_PRICE = 0.4, 1.0      # what the traders pay for surplus at dawn
GRAIN_STORE_DAYS, TIMBER_STORE = 5, 200
UPKEEP_HUSCARL = 1.0
UPKEEP_SHIP = 5.0
FOLK_PER_LONGHOUSE = 100
FOLK_PER_FARM = 10
FOLK_GROWTH = 0.05             # per day, when fed and housed
FOLK_STARVE = 0.06
LEVY_SHARE = 0.10              # a tenth of the folk will pick up a spear at home

# --- actions ----------------------------------------------------------------
CLEAR_TURNS, CLEAR_SILVER_BASE = 1, 20        # silver cost rises with land: base * (land/40)
BUILD_TURNS, BUILD_SILVER, BUILD_TIMBER = 1, 30, 10
TRAIN_TURNS_PER_10, TRAIN_SILVER, TRAIN_GRAIN = 1, 15, 5
SHIP_TURNS, SHIP_TIMBER, SHIP_SILVER, SHIP_CAPACITY = 2, 60, 40, 40
RAID_TURNS, TAKE_TURNS = 3, 4
HUSCARL_STRENGTH, LEVY_STRENGTH = 3.0, 1.0
HOME_ADVANTAGE, PALISADE_BONUS = 1.2, 0.10
RAID_SILVER_SHARE, RAID_GRAIN_SHARE, RAID_TIMBER_SHARE = 0.25, 0.25, 0.25
RAIDS_PER_DAY = 3              # sailings a day, and never the same realm twice
LAWS_PEACE_LAND = 30           # a realm this small cannot lose land
TAKE_LAND_SHARE, TAKE_RATIO_NEEDED = 0.10, 1.5


@dataclass
class Realm:
    name: str
    habit: str
    farms: int = 20
    woods: int = 5
    longhouses: int = 5
    wild: int = 10
    folk: int = 400
    silver: float = 300
    grain: float = 200
    timber: float = 50
    huscarls: int = 0
    ships: int = 1
    palisade: int = 0
    turns: int = TURNS_PER_DAY
    honour: int = 10
    raided_today: list = field(default_factory=list)
    log: list = field(default_factory=list)

    @property
    def land(self):
        return self.farms + self.woods + self.longhouses + self.wild

    @property
    def levy(self):
        return int(self.folk * LEVY_SHARE)

    def strength(self, at_home):
        s = self.huscarls * HUSCARL_STRENGTH + (self.levy * LEVY_STRENGTH if at_home else 0)
        return s * (HOME_ADVANTAGE + PALISADE_BONUS * self.palisade) if at_home else s

    def renown(self):
        return self.land * 10 + self.folk // 10 + self.huscarls + self.honour * 2 + int(self.silver // 50)

    def dawn(self):
        cap = self.longhouses * FOLK_PER_LONGHOUSE + self.farms * FOLK_PER_FARM
        self.grain += self.farms * GRAIN_PER_FARM - self.folk * GRAIN_PER_FOLK - self.huscarls * GRAIN_PER_HUSCARL
        self.timber += self.woods * TIMBER_PER_WOOD
        self.silver += self.folk * TAX_PER_FOLK - self.huscarls * UPKEEP_HUSCARL - self.ships * UPKEEP_SHIP
        if self.grain < 0:
            self.grain = 0
            self.folk = int(self.folk * (1 - FOLK_STARVE))
            self.huscarls = int(self.huscarls * 0.9)
        elif self.folk < cap:
            self.folk = min(cap, int(self.folk * (1 + FOLK_GROWTH)))
        # The traders take what will not keep.
        keep = (self.folk * GRAIN_PER_FOLK + self.huscarls * GRAIN_PER_HUSCARL) * GRAIN_STORE_DAYS + 100
        if self.grain > keep:
            self.silver += (self.grain - keep) * GRAIN_PRICE
            self.grain = keep
        if self.timber > TIMBER_STORE:
            self.silver += (self.timber - TIMBER_STORE) * TIMBER_PRICE
            self.timber = TIMBER_STORE
        self.turns = min(TURN_CAP, self.turns + TURNS_PER_DAY)
        self.raided_today = []


def clear(r):
    cost = CLEAR_SILVER_BASE * r.land / 40
    if r.turns >= CLEAR_TURNS and r.silver >= cost:
        r.turns -= CLEAR_TURNS
        r.silver -= cost
        r.wild += 1
        return True
    return False


def build(r, kind):
    if r.wild and r.turns >= BUILD_TURNS and r.silver >= BUILD_SILVER and r.timber >= BUILD_TIMBER:
        r.turns -= BUILD_TURNS
        r.silver -= BUILD_SILVER
        r.timber -= BUILD_TIMBER
        r.wild -= 1
        setattr(r, kind, getattr(r, kind) + 1)
        return True
    return False


def train(r, n=10):
    if r.turns >= TRAIN_TURNS_PER_10 and r.silver >= TRAIN_SILVER * n and r.grain >= TRAIN_GRAIN * n and r.folk >= n + 100:
        r.turns -= TRAIN_TURNS_PER_10
        r.silver -= TRAIN_SILVER * n
        r.grain -= TRAIN_GRAIN * n
        r.folk -= n
        r.huscarls += n
        return True
    return False


def ship(r):
    if r.turns >= SHIP_TURNS and r.timber >= SHIP_TIMBER and r.silver >= SHIP_SILVER:
        r.turns -= SHIP_TURNS
        r.timber -= SHIP_TIMBER
        r.silver -= SHIP_SILVER
        r.ships += 1
        return True
    return False


def battle(rng, attacker, defender, warriors):
    """Returns the force ratio; applies losses to both."""
    a = warriors * HUSCARL_STRENGTH * rng.uniform(0.9, 1.1)
    d = defender.strength(at_home=True) * rng.uniform(0.9, 1.1)
    ratio = a / max(d, 1)
    if ratio >= 1:
        attacker.huscarls -= int(warriors * min(0.3, 0.15 / ratio))
        defender.huscarls -= int(defender.huscarls * 0.3)
        defender.folk -= int(defender.levy * 0.1)
    else:
        attacker.huscarls -= int(warriors * 0.35)
        defender.huscarls -= int(defender.huscarls * 0.1)
    return ratio


def raid(rng, r, target):
    warriors = min(r.huscarls, r.ships * SHIP_CAPACITY)
    if r.turns < RAID_TURNS or warriors < 10 or len(r.raided_today) >= RAIDS_PER_DAY or target in r.raided_today:
        return None
    r.turns -= RAID_TURNS
    r.raided_today.append(target)
    ratio = battle(rng, r, target, warriors)
    if ratio >= 1:
        s, g = target.silver * RAID_SILVER_SHARE, target.grain * RAID_GRAIN_SHARE
        t = target.timber * RAID_TIMBER_SHARE
        target.silver -= s
        target.grain -= g
        target.timber -= t
        r.silver += s
        r.grain += g
        r.timber += t
        if target.renown() < r.renown() * 0.5:
            r.honour -= 2                        # no glory in robbing the small
    return ratio


def take(rng, r, target):
    warriors = min(r.huscarls, r.ships * SHIP_CAPACITY)
    if (r.turns < TAKE_TURNS or warriors < 20 or target.land < LAWS_PEACE_LAND
            or len(r.raided_today) >= RAIDS_PER_DAY or target in r.raided_today):
        return None
    r.turns -= TAKE_TURNS
    r.raided_today.append(target)
    ratio = battle(rng, r, target, warriors)
    if ratio >= TAKE_RATIO_NEEDED:
        n = max(1, int(target.land * TAKE_LAND_SHARE))
        for kind in ("wild", "woods", "farms", "longhouses"):
            while n and getattr(target, kind) > 1:
                setattr(target, kind, getattr(target, kind) - 1)
                n -= 1
                r.wild += 1
        r.honour += 2 if target.renown() >= r.renown() * 0.5 else -3
    return ratio


# --- habits -------------------------------------------------------------------
def farmer(rng, r, others):
    """Clears and builds farms and longhouses, keeps a small guard."""
    while r.turns >= 3:
        if r.huscarls < r.land // 2 and train(r):
            continue
        if r.folk >= r.longhouses * FOLK_PER_LONGHOUSE * 0.9 and (build(r, "longhouses") if r.wild else clear(r)):
            continue
        if r.wild and build(r, "farms"):
            continue
        if not clear(r):
            break


def raider(rng, r, others):
    """Ships and huscarls, raids the richest neighbour every day it can, reinvests the loot."""
    while r.turns >= 3:
        if r.ships * SHIP_CAPACITY < r.huscarls + 20 and ship(r):
            continue
        if r.folk > 300 and r.huscarls < 160 and train(r, 20):
            continue
        targets = sorted((o for o in others if o not in r.raided_today), key=lambda o: -(o.silver + o.grain + o.timber))
        if not targets or raid(rng, r, targets[0]) is None:
            cap = r.longhouses * FOLK_PER_LONGHOUSE + r.farms * FOLK_PER_FARM
            if r.folk >= cap * 0.9 and (build(r, "longhouses") if r.wild else clear(r)):
                continue
            if r.wild and build(r, "woods" if r.woods < r.farms // 2 else "farms"):
                continue
            if not clear(r):
                break


def conqueror(rng, r, others):
    """Like the raider, but takes land when it can win decisively."""
    while r.turns >= 4:
        if r.ships * SHIP_CAPACITY < r.huscarls + 20 and ship(r):
            continue
        if r.huscarls < 240 and train(r, 20):
            continue
        targets = sorted((o for o in others if o not in r.raided_today and o.land >= LAWS_PEACE_LAND),
                         key=lambda o: o.strength(True))
        if not targets or take(rng, r, targets[0]) is None:
            if r.wild and build(r, "farms"):
                continue
            if not clear(r):
                break


def turtle(rng, r, others):
    """Palisade, huscarls at home, farms; never leaves."""
    while r.turns >= 3:
        if r.palisade < 5 and r.silver >= 100 * (r.palisade + 1):
            r.silver -= 100 * (r.palisade + 1)
            r.turns -= 2
            r.palisade += 1
            continue
        if r.huscarls < r.land and train(r):
            continue
        if r.wild and build(r, "farms"):
            continue
        if not clear(r):
            break


HABITS = {"farmer": farmer, "raider": raider, "conqueror": conqueror, "turtle": turtle}


def play(seed=1, verbose=False):
    rng = random.Random(seed)
    realms = [Realm(name, habit) for name, habit in
              (("Halvard", "farmer"), ("Sigrun", "raider"), ("Ketil", "conqueror"), ("Ingirid", "turtle"))]
    for day in range(1, DAYS + 1):
        for r in realms:
            r.dawn()
        for r in realms:
            HABITS[r.habit](rng, r, [o for o in realms if o is not r])
        if verbose and day in (1, 5, 10, 15, 20, 25, 30):
            print(f"day {day:2d}  " + "  ".join(
                f"{r.name:7s} land {r.land:3d} folk {r.folk:5d} silver {r.silver:6.0f} grain {r.grain:6.0f} "
                f"husc {r.huscarls:3d} ships {r.ships} hon {r.honour:3d} renown {r.renown():5d}" for r in realms))
    return realms


if __name__ == "__main__":
    realms = play(verbose=True)
    print()
    for r in sorted(realms, key=lambda r: -r.renown()):
        print(f"{r.name:8s} {r.habit:10s} renown {r.renown():5d}  land {r.land:3d}  folk {r.folk:5d}  "
              f"huscarls {r.huscarls:3d}  honour {r.honour:3d}")
    # Across seeds: how often does each habit win, and does anyone get erased?
    wins, erased = {}, 0
    for seed in range(200):
        rs = play(seed)
        best = max(rs, key=lambda r: r.renown())
        wins[best.habit] = wins.get(best.habit, 0) + 1
        erased += any(r.land < 10 or r.folk < 50 for r in rs)
    print("\nwins over 200 rounds:", wins, " rounds where someone was erased:", erased)

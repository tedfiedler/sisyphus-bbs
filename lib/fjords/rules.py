"""The rules of Nine Fjords, as pure functions.

Nothing here touches the database, the clock, or module-level state, and every
function that needs chance takes a ``random.Random``. That is what lets the
tests assert exact outcomes from scripted dice, and lets ``lib.fjords.sim``
play whole years with the same code the game runs.

Functions named ``apply_*`` mutate the :class:`Realm` they are given; the rest
compute. Anything that touches *another* jarl's realm comes back as a
:class:`Settlement` for the caller to apply, never as a direct write: locally
that is one call to :func:`apply_settlement`; for a realm on another board it
is a message (design §19).
"""

from dataclasses import dataclass, field
from random import Random

from lib.fjords import data

FARMS, WOODS, LONGHOUSES, BOATYARDS, WILD = "farms", "woods", "longhouses", "boatyards", "wild"
USES = (FARMS, WOODS, LONGHOUSES, BOATYARDS)
RAID, TAKE = "raid", "take"


class NotAllowed(Exception):
    """An action the rules refuse. The message says why, in the skald's words' key."""


@dataclass
class Realm:
    """Everything the rules need to know about one jarl's holding."""

    farms: int = data.START_FARMS
    woods: int = data.START_WOODS
    longhouses: int = data.START_LONGHOUSES
    boatyards: int = 0
    wild: int = data.START_WILD
    folk: int = data.START_FOLK
    silver: float = data.START_SILVER
    grain: float = data.START_GRAIN
    timber: float = data.START_TIMBER
    huscarls: int = 0
    ships: int = data.START_SHIPS
    palisade: int = 0
    watchers: int = 0               # kept at home, against other jarls' watchers
    honour: int = data.HONOUR_START
    turns: int = data.TURNS_PER_DAY
    joined_day: int = 1             # day of the year this realm was founded
    last_day: int = 0               # the last day whose dawn has been applied
    sailings: list = field(default_factory=list)      # who was sailed against today
    feasted: bool = False
    sung_days: int = 0              # days of Eyvind's song still to come
    raided_day: int = 0             # the last day a sailing landed here
    crowns: int = 0                 # years won; survives Yule
    npc: str = ""                   # a computer-run jarl's habit, or "" for a player
    home: str = ""                  # federation id of the realm's board; "" is here

    @property
    def land(self) -> int:
        return self.farms + self.woods + self.longhouses + self.boatyards + self.wild

    @property
    def levy(self) -> int:
        return int(self.folk * data.LEVY_SHARE)

    @property
    def roofs(self) -> int:
        return self.longhouses * data.FOLK_PER_LONGHOUSE + self.farms * data.FOLK_PER_FARM

    @property
    def hold(self) -> int:
        return self.ships * data.SHIP_HOLD


@dataclass
class Market:
    """Orm's prices, shared by the whole coast."""

    grain_price: float = data.GRAIN_PRICE
    timber_price: float = data.TIMBER_PRICE


@dataclass
class DawnReport:
    """What Gunnhild reads out in the morning."""

    day: int
    grain: float = 0
    timber: float = 0
    tax: float = 0
    upkeep: float = 0
    sold_grain: float = 0
    sold_timber: float = 0
    sold_for: float = 0
    starved: bool = False
    folk_before: int = 0
    folk_after: int = 0
    event: str = ""
    event_n: int = 0


@dataclass
class Settlement:
    """What a sailing did to the other jarl. Applied by whoever owns that realm."""

    kind: str
    won: bool
    ratio: float
    weather: bool = False           # turned back; nothing happened to anyone
    silver: float = 0
    grain: float = 0
    timber: float = 0
    huscarls: int = 0
    folk: int = 0
    steadings: dict = field(default_factory=dict)
    party_lost: int = 0             # the attacker's own losses, for the record


@dataclass
class WatchReport:
    errand: str
    caught: bool
    ledger: dict = field(default_factory=dict)      # for "look"
    n: float = 0                                    # what was burned, stolen, or whispered away


# ---------------------------------------------------------------------------
# Numbers about a realm
# ---------------------------------------------------------------------------

def new_realm(day: int = 1, npc: str = "") -> Realm:
    return Realm(joined_day=day, last_day=day, npc=npc)


def renown(r: Realm) -> int:
    return int(r.land * data.RENOWN_LAND + r.folk * data.RENOWN_FOLK + r.huscarls * data.RENOWN_HUSCARL
               + r.honour * data.RENOWN_HONOUR + r.silver * data.RENOWN_SILVER)


def strength_at_home(r: Realm) -> float:
    return ((r.huscarls * data.HUSCARL_STRENGTH + r.levy * data.LEVY_STRENGTH)
            * (data.HOME_ADVANTAGE + data.PALISADE_BONUS * r.palisade))


def strength_of_party(huscarls: int) -> float:
    return huscarls * data.HUSCARL_STRENGTH


def luck(rng: Random) -> float:
    """0.9 to 1.1, from one roll of ``random()`` so scripted dice can set it."""
    return data.LUCK_LOW + (data.LUCK_HIGH - data.LUCK_LOW) * rng.random()


def under_peace(r: Realm, day: int) -> bool:
    """The Thing's peace: the small and the new cannot be sailed or spied against."""
    return r.land < data.PEACE_LAND or day - r.joined_day < data.PEACE_DAYS


def absent(r: Realm, day: int) -> bool:
    return day - r.last_day >= data.ABSENT_DAYS


def clear_cost(r: Realm, day: int) -> float:
    cost = data.CLEAR_SILVER * r.land / data.CLEAR_BASE_LAND
    return cost / 2 if data.season(day) == data.THAW else cost


def ship_cost(r: Realm) -> tuple[float, float]:
    timber = data.SHIP_TIMBER * (data.BOATYARD_TIMBER_SHARE if r.boatyards else 1)
    return timber, data.SHIP_SILVER


def palisade_cost(r: Realm) -> float:
    return data.PALISADE_SILVER * (r.palisade + 1)


def grain_eaten(r: Realm, day: int) -> float:
    eating = r.folk * data.GRAIN_PER_FOLK + r.huscarls * data.GRAIN_PER_HUSCARL
    return eating * (data.FROST_EATING if data.season(day) == data.FROST else 1)


def _clamp_honour(r: Realm) -> None:
    r.honour = max(data.HONOUR_MIN, min(data.HONOUR_MAX, r.honour))


# ---------------------------------------------------------------------------
# Dawn
# ---------------------------------------------------------------------------

def apply_dawn(r: Realm, day: int, rng: Random, market: Market) -> DawnReport:
    """One dawn: income, eating, growth, upkeep, Orm's purchases, an event. Idempotent by ``last_day``."""
    report = DawnReport(day=day, folk_before=r.folk)
    if day <= r.last_day:
        return report

    event = roll_event(rng)
    farms_pay = data.GRAIN_PER_FARM * (2 if event == "good_year" else 1)
    eating = grain_eaten(r, day) * (2 if event == "hard_frost" else 1)
    report.grain = r.farms * farms_pay - eating
    report.timber = r.woods * data.TIMBER_PER_WOOD
    report.tax = r.folk * data.TAX_PER_FOLK
    report.upkeep = (r.huscarls * data.UPKEEP_HUSCARL + r.ships * data.UPKEEP_SHIP
                     + r.watchers * data.UPKEEP_WATCHER)
    r.grain += report.grain
    r.timber += report.timber
    r.silver += report.tax - report.upkeep
    if r.silver < 0:
        # Unpaid huscarls walk, unpaid ships rot at their moorings, in that order.
        while r.silver < 0 and r.huscarls:
            r.huscarls -= 1
            r.silver += data.UPKEEP_HUSCARL
        while r.silver < 0 and r.ships:
            r.ships -= 1
            r.silver += data.UPKEEP_SHIP
        r.silver = max(0.0, r.silver)

    if r.grain < 0:
        r.grain = 0
        r.folk = int(r.folk * (1 - data.FOLK_STARVE))
        r.huscarls = int(r.huscarls * (1 - data.HUSCARLS_DESERT))
        report.starved = True
    elif r.folk < r.roofs:
        growth = data.FEAST_GROWTH if r.feasted else data.FOLK_GROWTH
        r.folk = min(r.roofs, int(r.folk * (1 + growth)) + 1)

    keep = grain_eaten(r, day) * data.GRAIN_KEEP_DAYS + data.GRAIN_KEEP_BASE
    if r.grain > keep:
        report.sold_grain = r.grain - keep
        r.grain = keep
    if r.timber > data.TIMBER_KEEP:
        report.sold_timber = r.timber - data.TIMBER_KEEP
        r.timber = data.TIMBER_KEEP
    report.sold_for = report.sold_grain * market.grain_price + report.sold_timber * market.timber_price
    r.silver += report.sold_for

    report.event, report.event_n = event, apply_event(r, event)
    report.folk_after = r.folk
    r.turns = min(data.TURN_CAP, r.turns + data.TURNS_PER_DAY)
    r.sailings = []
    r.feasted = False
    if r.sung_days:
        r.sung_days -= 1
    r.last_day = day
    return report


def roll_event(rng: Random) -> str:
    if rng.random() >= data.EVENT_CHANCE:
        return ""
    pick = rng.randint(1, 100)
    for key, weight in data.EVENTS:
        pick -= weight
        if pick <= 0:
            return key
    return data.EVENTS[-1][0]


def apply_event(r: Realm, event: str) -> int:
    """Returns the number the skald's line mentions, if any."""
    if event == "whale":
        r.grain += data.WHALE_GRAIN
        return data.WHALE_GRAIN
    if event == "skald":
        r.honour += 2
        _clamp_honour(r)
        return 2
    if event == "shipwright":
        if r.boatyards:
            r.ships += 1
            return 1
        r.silver += data.SHIPWRIGHT_SILVER
        return data.SHIPWRIGHT_SILVER
    if event == "sickness":
        lost = min(int(r.folk * data.SICKNESS_SHARE), max(0, r.folk - data.FOLK_FLOOR))
        r.folk -= lost
        return lost
    if event == "landslip":
        if r.woods > 1:
            r.woods -= 1
            r.wild += 1
            return 1
        return 0
    if event == "stranger":
        r.silver += data.STRANGER_SILVER
        return data.STRANGER_SILVER
    if event == "wolves":
        lost = min(int(r.folk * data.WOLVES_SHARE), max(0, r.folk - data.FOLK_FLOOR))
        r.folk -= lost
        return lost
    if event == "driftwood":
        r.timber += data.DRIFTWOOD_TIMBER
        return data.DRIFTWOOD_TIMBER
    if event == "wedding":
        gained = int(r.folk * data.WEDDING_SHARE)
        r.folk = min(r.roofs, r.folk + gained)
        return gained
    return 0                                    # hard_frost and good_year act at dawn; missionary does nothing


def apply_market_dawn(market: Market) -> None:
    """Prices drift back toward what Orm always paid."""
    market.grain_price += (data.GRAIN_PRICE - market.grain_price) * data.PRICE_RECOVERY
    market.timber_price += (data.TIMBER_PRICE - market.timber_price) * data.PRICE_RECOVERY


# ---------------------------------------------------------------------------
# The hall
# ---------------------------------------------------------------------------

def _spend(r: Realm, turns: int, silver: float = 0, grain: float = 0, timber: float = 0) -> None:
    if r.turns < turns:
        raise NotAllowed("no_turns")
    if r.silver < silver:
        raise NotAllowed("no_silver")
    if r.grain < grain:
        raise NotAllowed("no_grain")
    if r.timber < timber:
        raise NotAllowed("no_timber")
    r.turns -= turns
    r.silver -= silver
    r.grain -= grain
    r.timber -= timber


def apply_clear(r: Realm, day: int) -> None:
    if data.season(day) == data.FROST:
        raise NotAllowed("frost")
    _spend(r, data.CLEAR_TURNS, silver=clear_cost(r, day))
    r.wild += 1


def apply_raise(r: Realm, use: str) -> None:
    if use not in USES:
        raise NotAllowed("no_such_use")
    if not r.wild:
        raise NotAllowed("no_wild")
    _spend(r, data.RAISE_TURNS, silver=data.RAISE_SILVER, timber=data.RAISE_TIMBER)
    r.wild -= 1
    setattr(r, use, getattr(r, use) + 1)


def apply_pull_down(r: Realm, use: str) -> None:
    if use not in USES or getattr(r, use) < 1:
        raise NotAllowed("nothing_there")
    setattr(r, use, getattr(r, use) - 1)
    r.wild += 1
    r.timber += data.PULL_DOWN_TIMBER_BACK


def apply_train(r: Realm, n: int) -> None:
    if n < 1:
        raise NotAllowed("nobody")
    if r.folk - n < data.FOLK_KEEP:
        raise NotAllowed("no_folk")
    turns = -(-n // data.TRAIN_PER_TURN)              # ceiling
    _spend(r, turns, silver=data.TRAIN_SILVER * n, grain=data.TRAIN_GRAIN * n)
    r.folk -= n
    r.huscarls += n


def apply_dismiss(r: Realm, n: int) -> None:
    if not 1 <= n <= r.huscarls:
        raise NotAllowed("nobody")
    r.huscarls -= n
    r.folk = min(r.roofs, r.folk + n) if r.folk < r.roofs else r.folk


def apply_ship(r: Realm) -> None:
    timber, silver = ship_cost(r)
    _spend(r, data.SHIP_TURNS, silver=silver, timber=timber)
    r.ships += 1


def apply_palisade(r: Realm) -> None:
    if r.palisade >= data.PALISADE_MAX:
        raise NotAllowed("palisade_done")
    _spend(r, data.PALISADE_TURNS, silver=palisade_cost(r))
    r.palisade += 1


def apply_feast(r: Realm) -> None:
    if r.feasted:
        raise NotAllowed("feasted")
    _spend(r, data.FEAST_TURNS, silver=data.FEAST_SILVER, grain=data.FEAST_GRAIN)
    r.feasted = True
    r.honour += data.FEAST_HONOUR
    _clamp_honour(r)


def apply_keep_watchers(r: Realm, n: int) -> None:
    """Set how many watchers stay home. They cost their keep at dawn."""
    if not 0 <= n <= data.WATCHERS_HOME_MAX:
        raise NotAllowed("too_many")
    r.watchers = n


# ---------------------------------------------------------------------------
# Saltvik
# ---------------------------------------------------------------------------

def apply_sell(r: Realm, market: Market, grain: float = 0, timber: float = 0) -> float:
    """Sell to Orm at today's price; a big sale pushes the price down for everyone."""
    if grain < 0 or timber < 0 or grain > r.grain or timber > r.timber or not (grain or timber):
        raise NotAllowed("not_that")
    _spend(r, data.MARKET_TURNS)
    silver = grain * market.grain_price + timber * market.timber_price
    r.grain -= grain
    r.timber -= timber
    r.silver += silver
    for amount, attr, base in ((grain, "grain_price", data.GRAIN_PRICE), (timber, "timber_price", data.TIMBER_PRICE)):
        if amount:
            drop = min(data.PRICE_DROP_PER_VISIT_MAX, amount / data.PRICE_DROP_AT_VOLUME * data.PRICE_DROP_PER_VISIT_MAX)
            setattr(market, attr, max(base * data.PRICE_MIN_SHARE, getattr(market, attr) * (1 - drop)))
    return silver


def apply_buy(r: Realm, market: Market, grain: float = 0, timber: float = 0) -> float:
    if grain < 0 or timber < 0 or not (grain or timber):
        raise NotAllowed("not_that")
    cost = (grain * market.grain_price + timber * market.timber_price) * data.BUY_MARKUP
    _spend(r, data.MARKET_TURNS, silver=cost)
    r.grain += grain
    r.timber += timber
    return cost


# ---------------------------------------------------------------------------
# The sea
# ---------------------------------------------------------------------------

def may_sail(attacker: Realm, defender: Realm, defender_id, day: int, pact: bool = False) -> str | None:
    """Why not, as a text key; None when the sailing is allowed."""
    if defender is attacker:
        return "yourself"
    if pact:
        return "pact"
    if under_peace(defender, day):
        return "peace"
    if absent(defender, day):
        return "absent"
    if len(attacker.sailings) >= data.SAILINGS_PER_DAY:
        return "sailed_enough"
    if defender_id in attacker.sailings:
        return "sailed_already"
    if attacker.ships < 1:
        return "no_ships"
    return None


def sail(kind: str, attacker: Realm, defender: Realm, defender_id, party: int, day: int, rng: Random) -> Settlement:
    """A raid or a land-taking. Mutates the attacker; returns what happens to the defender.

    The caller checks :func:`may_sail` first and applies the settlement to the
    real defender, so this function never touches another jarl's row.
    """
    turns = {RAID: data.RAID_TURNS_SAILING if data.season(day) == data.SAILING else data.RAID_TURNS,
             TAKE: data.TAKE_TURNS}[kind]
    if party < (data.MIN_RAID_PARTY if kind == RAID else data.MIN_TAKE_PARTY):
        raise NotAllowed("too_few")
    if party > attacker.huscarls or party > attacker.hold:
        raise NotAllowed("no_hold")
    if attacker.turns < turns:
        raise NotAllowed("no_turns")
    attacker.turns -= turns
    attacker.sailings.append(defender_id)

    if data.season(day) == data.FROST and rng.random() < data.FROST_WEATHER:
        return Settlement(kind=kind, won=False, ratio=0.0, weather=True)

    attack = strength_of_party(party) * luck(rng)
    defence = strength_at_home(defender) * luck(rng)
    ratio = attack / max(defence, 1.0)
    won = ratio >= (data.TAKE_RATIO if kind == TAKE else 1.0)
    s = Settlement(kind=kind, won=won, ratio=round(ratio, 3))
    bully = renown(defender) < renown(attacker) * data.BULLY_RATIO

    if ratio >= 1.0:
        lost = int(party * min(data.ATTACKER_WIN_LOSS_MAX, data.ATTACKER_WIN_LOSS / ratio))
        s.huscarls = int(defender.huscarls * data.DEFENDER_LOSS_HUSCARLS)
        s.folk = min(int(defender.levy * data.DEFENDER_LOSS_LEVY), max(0, defender.folk - data.FOLK_FLOOR))
    else:
        lost = int(party * data.ATTACKER_LOSE_LOSS)
        s.huscarls = int(defender.huscarls * data.DEFENDER_WIN_LOSS)
    attacker.huscarls -= lost
    s.party_lost = lost

    if kind == RAID and won:
        share = data.RAID_SHARE_SAILING if data.season(day) == data.SAILING else data.RAID_SHARE
        s.silver, s.grain, s.timber = defender.silver * share, defender.grain * share, defender.timber * share
        attacker.silver += s.silver
        attacker.grain += s.grain
        attacker.timber += s.timber
        if bully:
            attacker.honour += data.RAID_BULLY
    elif kind == TAKE and won:
        n = max(1, int(defender.land * data.TAKE_SHARE))
        for use in data.TAKE_ORDER:
            have = getattr(defender, use) - (n if use == WILD else 0)
            can = max(0, getattr(defender, use) - (0 if use == WILD else 1))
            give = min(n, can)
            if give:
                s.steadings[use] = give
                n -= give
            if not n:
                break
        attacker.wild += sum(s.steadings.values())
        attacker.honour += data.TAKE_BULLY if bully else data.TAKE_PEER
    _clamp_honour(attacker)
    return s


def apply_settlement(defender: Realm, s: Settlement, day: int = 0) -> None:
    """What a sailing cost the jarl who was sailed against."""
    if s.weather:
        return
    if s.kind in (RAID, TAKE):
        defender.raided_day = max(defender.raided_day, day)
    defender.huscarls = max(0, defender.huscarls - s.huscarls)
    defender.folk = max(data.FOLK_FLOOR, defender.folk - s.folk) if defender.folk > data.FOLK_FLOOR else defender.folk
    defender.silver = max(0.0, defender.silver - s.silver)
    defender.grain = max(0.0, defender.grain - s.grain)
    defender.timber = max(0.0, defender.timber - s.timber)
    for use, n in s.steadings.items():
        setattr(defender, use, max(0 if use == WILD else 1, getattr(defender, use) - n))


# ---------------------------------------------------------------------------
# The watchers
# ---------------------------------------------------------------------------

def watch_chance(defender: Realm, sent_today: int) -> float:
    return data.WATCH_BASE - data.WATCH_PER_HOME * defender.watchers + data.WATCH_PER_SENT * sent_today


def send_watcher(errand: str, attacker: Realm, defender: Realm, sent_today: int, rng: Random) -> tuple[WatchReport, Settlement | None]:
    """One watcher, one errand. Returns the report and, on success, what it costs the other jarl."""
    if errand not in data.ERRANDS:
        raise NotAllowed("no_such_errand")
    _spend(attacker, data.WATCHER_TURNS, silver=data.WATCHER_SILVER)
    if rng.random() >= watch_chance(defender, sent_today):
        attacker.honour += data.CAUGHT_HONOUR[errand]
        _clamp_honour(attacker)
        return WatchReport(errand, caught=True), None
    if errand == data.LOOK:
        return WatchReport(errand, caught=False, ledger=ledger(defender)), None
    s = Settlement(kind=errand, won=True, ratio=0.0)
    if errand == data.BURN:
        s.grain = defender.grain * data.BURN_SHARE
    elif errand == data.STEAL:
        s.silver = min(defender.silver * data.STEAL_SHARE, data.STEAL_MAX)
        attacker.silver += s.silver
    elif errand == data.WHISPER:
        s.folk = min(int(defender.folk * data.WHISPER_SHARE), max(0, defender.folk - data.FOLK_FLOOR))
        attacker.folk = min(attacker.roofs, attacker.folk + s.folk // 2)
    return WatchReport(errand, caught=False, n=s.grain or s.silver or s.folk), s


def ledger(r: Realm) -> dict:
    """What Gunnhild reads out, and what a successful look brings home."""
    return {
        "land": r.land, "farms": r.farms, "woods": r.woods, "longhouses": r.longhouses,
        "boatyards": r.boatyards, "wild": r.wild, "folk": r.folk, "roofs": r.roofs,
        "silver": int(r.silver), "grain": int(r.grain), "timber": int(r.timber),
        "huscarls": r.huscarls, "levy": r.levy, "ships": r.ships, "hold": r.hold,
        "palisade": r.palisade, "watchers": r.watchers, "honour": r.honour, "renown": renown(r),
    }


# ---------------------------------------------------------------------------
# The Thing, and Yule
# ---------------------------------------------------------------------------

def apply_pact_broken(breaker: Realm) -> None:
    breaker.honour += data.PACT_BREAK
    _clamp_honour(breaker)


def apply_song(r: Realm, day: int) -> bool:
    """Every tenth day, Eyvind sings of the honourable: +1 renown a day for the rest of the year."""
    if day % data.SUNG_EVERY == 0 and r.honour > data.SUNG_ABOVE:
        r.sung_days = data.DAYS_IN_YEAR - day + 1
        return True
    return False


def yule_renown(r: Realm, day: int) -> int:
    """Renown as reckoned at Yule, with the skald's song added."""
    return renown(r) + (data.SUNG_RENOWN * r.sung_days if r.sung_days else 0)


def apply_yule(r: Realm, crowned: bool) -> None:
    """A new year: back to the first forty steadings. Crowns and nothing else survive."""
    crowns = r.crowns + (1 if crowned else 0)
    fresh = new_realm(day=1, npc=r.npc)
    fresh.crowns = crowns
    fresh.home = r.home
    r.__dict__.update(fresh.__dict__)

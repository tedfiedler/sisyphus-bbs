"""Every number and name in Nine Fjords. The prose is in text.py.

All of it is original (docs/nine-fjords/DESIGN.md §0). The economy was sized by
docs/nine-fjords/balance_sim.py and is held to the targets in §16 by
lib/fjords/sim.py and tests/test_fjords_balance.py. Change a constant here,
run ``python -m lib.fjords.sim``, read the summary.
"""

TITLE = "Nine Fjords"
CREDIT = "In the tradition of the BBS door games of the early '90s."

# --- the year -----------------------------------------------------------------
DAYS_IN_YEAR = 30
THAW, SAILING, FROST = "thaw", "sailing", "frost"
SEASON_LENGTH = 10
TURNS_PER_DAY, TURN_CAP = 12, 36


def season(day: int) -> str:
    """Days 1-10 thaw, 11-20 sailing, 21-30 frost. Day 31 is Yule, which is dawn of a new year."""
    return (THAW, SAILING, FROST)[min(2, max(0, (day - 1) // SEASON_LENGTH))]


# --- the realm at the start of a year ---------------------------------------------
START_FARMS, START_WOODS, START_LONGHOUSES, START_WILD = 20, 5, 5, 10
START_FOLK, START_SILVER, START_GRAIN, START_TIMBER, START_SHIPS = 400, 300, 200, 50, 1
HONOUR_START, HONOUR_MIN, HONOUR_MAX = 10, -50, 50

# --- each dawn ------------------------------------------------------------------
GRAIN_PER_FARM = 12
TIMBER_PER_WOOD = 6
FOLK_PER_FARM = 10                 # roofs: a farm houses a few, a longhouse many
FOLK_PER_LONGHOUSE = 100
GRAIN_PER_FOLK = 0.10              # ten folk eat one grain a day
GRAIN_PER_HUSCARL = 0.30
FROST_EATING = 1.5                 # everyone eats half again as much in frost
TAX_PER_FOLK = 1.0
UPKEEP_HUSCARL = 1.0
UPKEEP_SHIP = 5.0
UPKEEP_WATCHER = 1.0
FOLK_GROWTH = 0.05                 # a day, when fed and housed
FEAST_GROWTH = 0.10                # the night after a feast
FOLK_STARVE = 0.06
HUSCARLS_DESERT = 0.10             # when the grain runs out
FOLK_FLOOR = 50                    # nobody drops below this from anything but starvation
LEVY_SHARE = 0.10                  # the folk who pick up a spear at home

# What will not keep is sold to Orm at dawn.
GRAIN_KEEP_DAYS, GRAIN_KEEP_BASE = 5, 100
TIMBER_KEEP = 200

# --- the hall ---------------------------------------------------------------------
CLEAR_TURNS, CLEAR_SILVER = 1, 20          # silver x (steadings / 40); half in thaw; never in frost
CLEAR_BASE_LAND = 40
RAISE_TURNS, RAISE_SILVER, RAISE_TIMBER = 1, 30, 10
PULL_DOWN_TIMBER_BACK = 5
TRAIN_PER_TURN, TRAIN_SILVER, TRAIN_GRAIN = 10, 15, 5
FOLK_KEEP = 100                            # training never takes the folk below this
SHIP_TURNS, SHIP_TIMBER, SHIP_SILVER, SHIP_HOLD = 2, 60, 40, 40
BOATYARD_TIMBER_SHARE = 0.5
PALISADE_TURNS, PALISADE_SILVER, PALISADE_MAX = 2, 100, 5
FEAST_TURNS, FEAST_GRAIN, FEAST_SILVER, FEAST_HONOUR = 2, 100, 50, 1
MARKET_TURNS = 1
WATCHER_TURNS, WATCHER_SILVER, WATCHERS_HOME_MAX = 1, 20, 10

# --- Saltvik ------------------------------------------------------------------------
GRAIN_PRICE, TIMBER_PRICE = 0.4, 1.0
PRICE_MIN_SHARE, PRICE_MAX_SHARE = 0.5, 1.5    # a price never strays past half or half again
PRICE_DROP_PER_VISIT_MAX = 0.20                # selling a lot in one visit pushes the price down...
PRICE_DROP_AT_VOLUME = 2000                    # ...this much sold drops it the maximum
PRICE_RECOVERY = 1 / 3                         # ...and it recovers over three days
BUY_MARKUP = 1.5                               # Orm sells at half again what he buys for

# --- the sea -------------------------------------------------------------------------
RAID_TURNS, RAID_TURNS_SAILING, TAKE_TURNS = 3, 2, 4
SAILINGS_PER_DAY = 3
HUSCARL_STRENGTH, LEVY_STRENGTH = 3.0, 1.0
HOME_ADVANTAGE, PALISADE_BONUS = 1.2, 0.10
LUCK_LOW, LUCK_HIGH = 0.9, 1.1
RAID_SHARE, RAID_SHARE_SAILING = 0.25, 1 / 3
ATTACKER_WIN_LOSS, ATTACKER_WIN_LOSS_MAX = 0.15, 0.30      # divided by the ratio, capped
DEFENDER_LOSS_HUSCARLS, DEFENDER_LOSS_LEVY = 0.30, 0.10
ATTACKER_LOSE_LOSS, DEFENDER_WIN_LOSS = 0.35, 0.10
TAKE_RATIO, TAKE_SHARE = 2.0, 0.10        # decisive means twice their strength; the sim found 1.5 let a week-old army eat a farm
TAKE_ORDER = ("wild", "woods", "farms", "longhouses")     # never the last of anything
FROST_WEATHER = 0.10                                       # a sailing turned back in frost
MIN_RAID_PARTY, MIN_TAKE_PARTY = 10, 20

# --- the peace, the absent -----------------------------------------------------------
PEACE_LAND, PEACE_DAYS = 30, 5
ABSENT_DAYS = 3
STONE_DAYS = 14

# --- honour -------------------------------------------------------------------------
BULLY_RATIO = 0.5                  # a target under half your renown
RAID_BULLY, TAKE_PEER, TAKE_BULLY = -2, 2, -3
PACT_BREAK, PACT_COOLDOWN = -10, 10
SUNG_ABOVE, SUNG_EVERY, SUNG_RENOWN = 30, 10, 1

# --- the watchers -------------------------------------------------------------------
WATCH_BASE, WATCH_PER_HOME, WATCH_PER_SENT = 0.70, 0.05, 0.05
LOOK, BURN, STEAL, WHISPER = "look", "burn", "steal", "whisper"
ERRANDS = (LOOK, BURN, STEAL, WHISPER)
BURN_SHARE, STEAL_SHARE, STEAL_MAX, WHISPER_SHARE = 0.10, 0.10, 200, 0.03
CAUGHT_HONOUR = {LOOK: 0, BURN: -2, STEAL: -3, WHISPER: -3}

# --- renown -------------------------------------------------------------------------
RENOWN_LAND, RENOWN_FOLK, RENOWN_HUSCARL, RENOWN_HONOUR, RENOWN_SILVER = 10, 1 / 10, 1, 2, 1 / 50
NPC_YULE_SCALE = 0.90              # a computer-run jarl never wins outright

# --- events: one day in five, weights sum to 100 -----------------------------------------
EVENT_CHANCE = 0.20
EVENTS = (
    ("whale", 12),          # +150 grain
    ("hard_frost", 10),     # the folk eat double today
    ("skald", 8),           # +2 honour
    ("shipwright", 6),      # a longship if you have a boatyard, else 50 silver
    ("sickness", 9),        # folk -4%
    ("good_year", 10),      # farms pay double today
    ("landslip", 8),        # one woodland to wild
    ("missionary", 9),      # nothing happens
    ("stranger", 8),        # +100 silver
    ("wolves", 8),          # levy folk -1%
    ("driftwood", 7),       # +80 timber
    ("wedding", 5),         # folk +3%
)
assert sum(w for _, w in EVENTS) == 100
WHALE_GRAIN, SHIPWRIGHT_SILVER, SICKNESS_SHARE, STRANGER_SILVER = 150, 50, 0.04, 100
WOLVES_SHARE, DRIFTWOOD_TIMBER, WEDDING_SHARE = 0.01, 80, 0.03

# --- the five jarls of the coast --------------------------------------------------------
FARMER, RAIDER, CONQUEROR, TURTLE, TRADER = "farmer", "raider", "conqueror", "turtle", "trader"
JARLS = (
    ("Halvard the Grey", FARMER),
    ("Sigrun Oarbreaker", RAIDER),
    ("Ketil Half-Troll", CONQUEROR),
    ("Ingirid Salt-Wise", TURTLE),
    ("Orm Sheep-Rich", TRADER),
)
STEWARD, SKALD, MERCHANT = "Gunnhild", "Eyvind the Skald", "Orm Sheep-Rich"
MARKET, ASSEMBLY, STONE = "Saltvik", "the Thing", "the Stone"

# --- the map ---------------------------------------------------------------------------
FJORDS = (
    "Ravnfjord", "Saltfjord", "Ulvfjord", "Hvalfjord", "Isfjord",
    "Bjornfjord", "Ornfjord", "Tarefjord", "Skyfjord",
)

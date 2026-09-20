"""Tables and constants for The Long Climb.

Every number and every name here is original to this project or drawn from
Greek myth (DESIGN.md section 0). Numeric tables are ``base * growth**(level-1)``
so the whole curve moves by changing two numbers; ``lib.climb.sim`` says what a
change does to the length of a climb, and a test holds it to about a month.

Levels, bands, and gear tiers are 1-based everywhere outside this module's
tuples, which are indexed ``level - 1``.
"""

LEVELS = 12

# --- the day --------------------------------------------------------------
SLOPE_FIGHTS_PER_DAY = 15
DUELS_PER_DAY = 3
START_DRACHMAE = 60


def _curve(base: float, growth: float, n: int = LEVELS) -> tuple[int, ...]:
    return tuple(round(base * growth ** i) for i in range(n))


def _two_figures(n: int) -> int:
    """Round to two significant figures: prices a shopkeeper would chalk up."""
    if n < 100:
        return n
    magnitude = 10 ** (len(str(n)) - 2)
    return round(n / magnitude) * magnitude


# --- the climber, by level --------------------------------------------------
MAX_HP = _curve(24, 1.42)
STRENGTH = _curve(6, 1.40)
DEFENCE = _curve(2, 1.40)

# --- what a kill in each band is worth (before the creature's rank factor) --
REF_XP = _curve(12, 1.95)
REF_DRACHMAE = _curve(22, 1.75)

# Intended days of steady play in each band, levels 1..11.
_DAYS_IN_BAND = tuple(1.4 + 0.17 * i for i in range(LEVELS - 1))
XP_TO_NEXT = tuple(
    round(REF_XP[i] * SLOPE_FIGHTS_PER_DAY * _DAYS_IN_BAND[i] * 0.97) for i in range(LEVELS - 1)
)

# --- gear, by tier ----------------------------------------------------------
WEAPON_POWER = _curve(6, 1.48)
ARMOUR_POWER = _curve(4, 1.48)
_GEAR_DAYS = 1.6        # a weapon costs this many days of its band's earnings
WEAPON_PRICE = tuple(_two_figures(round(g * SLOPE_FIGHTS_PER_DAY * _GEAR_DAYS)) for g in REF_DRACHMAE)
ARMOUR_PRICE = tuple(_two_figures(round(p * 0.85)) for p in WEAPON_PRICE)
TRADE_IN = 0.5

WEAPONS = (
    "Olive Branch", "Shepherd's Crook", "Bronze Knife", "Hunting Spear",
    "Hoplite's Xiphos", "Boar Lance", "Labrys", "Thracian Rhomphaia",
    "Spear of Ash and Iron", "Adamant Sickle", "Star-Metal Blade", "Thunder-Scorched Spear",
)
ARMOURS = (
    "Wool Cloak", "Goatskin Jerkin", "Linen Cuirass", "Wicker Shield and Greaves",
    "Bronze Bell Cuirass", "Hoplon and Bronze", "Scale Coat", "Helm and Ringmail",
    "Muscled Cuirass", "Nemean Hide", "Adamant Plate", "Fragment of the Aegis",
)

# --- combat -----------------------------------------------------------------
FIRST_STRIKE_CHANCE = 0.70
MIGHTY_BLOW_CHANCE = 0.10
RUN_CHANCE = 0.75
CREATURE_HP = 0.62          # a rank-factor-1.0 creature has this share of your max HP
CREATURE_ATTACK = 0.46      # see rules.creature for how this becomes an attack value
RANK_FACTOR_BASE, RANK_FACTOR_STEP = 0.70, 0.09     # ranks 1..8 -> 0.70 .. 1.33
CREATURES_PER_BAND = 8

GATEKEEPER_HP, GATEKEEPER_ATTACK = 2.2, 1.3         # times the band's strongest creature
LADON_HP, LADON_ATTACK = 2.8, 1.3                   # times level-12 max HP / strongest creature's attack

ASCENT_TOUGHNESS_STEP, ASCENT_TOUGHNESS_CAP = 0.03, 10    # +3% creature health per ascent, to +30%

# A full heal costs this many kills' coin at your band. The most sensitive
# number in the game: 2 gives a 34-day first ascent, 3 gives 45, and at 5 no
# simulated climber ever finishes. Do not change it without running the sim.
FULL_HEAL_IN_KILLS = 2.0

DEATH_XP_LOSS = 0.10
SEED_DROP_CHANCE = 1 / 40

# --- callings ---------------------------------------------------------------
SPEAR, TORCH, SANDAL = "spear", "torch", "sandal"
CALLINGS = {
    SPEAR: ("The Spear", "Ares"),
    TORCH: ("The Torch", "Hecate"),
    SANDAL: ("The Sandal", "Hermes"),
}
MAX_RANK = 40
RANK_PER_EXTRA_USE = 5
FURY_MULTIPLIER = 3
FLAME_MULTIPLIER = 2
MEND_RANK, MEND_SHARE = 10, 1 / 3
SHADOW_RANK = 20
SURE_FOOT_RANK = 10          # the Sandal: fleeing never fails
QUICK_HANDS_SHARE = 0.25

# --- the mountain -----------------------------------------------------------
BANDS = (
    "The Foothills", "The Olive Terraces", "The Goat Tracks", "The Pine Belt",
    "The Scree Fields", "The Cloud Line", "The Eagle Crags", "The Snow Line",
    "The Windgap", "The Black Stair", "The Last Shoulder", "The Garden Wall",
)

# The gatekeeper at the top of bands 1..11.
GATEKEEPERS = (
    "Agathe the Goatherd", "Old Stavros", "Kleitos Two-Dogs", "Ione of the Pines",
    "Damon and Lykos", "Brother Aither", "Aella Eagle-Caller", "Chione",
    "Zetes", "The Warden", "Aigle of the Hesperides",
)

BOSS = "Ladon"

# Eight creatures per band, weakest first.
CREATURES = (
    ("Irritable Goat", "Olive Thief", "Tipsy Satyr", "Stray Hound",
     "Road Bandit", "Deserter Hoplite", "Wild Boar", "Overzealous Tax Collector"),
    ("Terrace Viper", "Mob of Crows", "Angry Beekeeper", "Grove Poacher",
     "Scarecrow That Moved", "Cattle Rustler", "Sow with Piglets", "Landlord's Bailiff"),
    ("Cliff Ram", "Pebble Daimon", "Goat-Rustling Satyr", "Hill Brigand",
     "Mountain Lynx", "Mad Hermit", "Stymphalian Fledgling", "Brigand Captain"),
    ("Marten Swarm", "Scorned Dryad", "Feral Charcoal-Burner", "Grey Wolf",
     "Lost Maenad", "Pair of Wolves", "She-Bear", "Pack Leader"),
    ("Scree Scorpion", "Bone Picker", "Rival Climber", "Harpy Chick",
     "Twin Vipers", "Cyclops Shepherd-Boy", "Sliding Boulder", "Harpy"),
    ("Mist Shade", "Cloud-Blind Ox", "Echo That Hits Back", "Fog Wolf",
     "Storm-Petrel Flock", "Ghost of a Lost Legionary", "Walking Lightning-Struck Pine", "Nephele's Hound"),
    ("Crag Eagle", "Nest Guardian", "Bandit on a Rope", "Griffin Fledgling",
     "Archer's Shade", "The Talon Twins", "Griffin", "Aetos the Old Eagle"),
    ("Surprisingly Vicious Hare", "Ice Viper", "Frostbitten Shade", "White Wolf",
     "White Lynx", "Frozen Hoplite", "Avalanche Spirit", "Boreal Giant's Child"),
    ("Gale Sprite", "Tumbling Harpy", "Wind-Mad Pilgrim", "Kite-Winged Thief",
     "Hound of the Four Winds", "Thunder Ram", "Harpy Matron", "Shade of the Gap Warden"),
    ("Stair Crawler", "Obsidian Asp", "Step-Counting Daimon", "Black Stair Hound",
     "Shade of a Proud King", "Bronze Automaton", "Oath-Breaker's Ghost", "Automaton Captain"),
    ("Titan's Knucklebone", "Sleepless Sentinel", "Chimera Cub", "Sky-Weary Giant",
     "Atlas' Dropped Pebble", "Young Chimera", "Hundred-Handed Stripling", "Chimera"),
    ("Garden Wasps", "Apple Thief", "Hesperid's Peacock", "Root Serpent",
     "Ladon's Shed Skin", "Lesser Head of Ladon", "Twin Heads of Ladon", "Nymph-Guard of the Tree"),
)

# Grammar for narration. Creatures take "the" ("the Irritable Goat") unless they
# are named here; people (gatekeepers, climbers, Ladon) never do. Plural foes
# take plural verbs ("the Twin Vipers hit you").
NO_ARTICLE_FOES = frozenset({
    "Aetos the Old Eagle", "Nephele's Hound", "Ladon's Shed Skin", "Atlas' Dropped Pebble",
})
PLURAL_FOES = frozenset({
    "Twin Vipers", "Garden Wasps", "The Talon Twins", "Twin Heads of Ladon", "Damon and Lykos",
})

# Ascents needed for each title, highest first.
TITLES = (
    (10, "the Happy"), (7, "Friend of the Mountain"), (5, "Stone-Roller"),
    (3, "Thrice-Risen"), (2, "Twice-Risen"), (1, "Apple-Bearer"), (0, "Climber"),
)

# --- the Slopes: things that are not fights ------------------------------------
EVENT_CHANCE = 1 / 8
# (event, weight); weights sum to 100. The first six resolve at once; the rest
# put a choice to the climber.
EVENTS = (
    ("spring", 11), ("rockslide", 9), ("eagle", 11), ("oracle", 7), ("shade", 2), ("smoke", 4),
    ("boulder", 12), ("wall", 8), ("satyr", 8), ("kid", 7), ("shrine", 7), ("hive", 7), ("toll", 7),
)
INSTANT_EVENTS = frozenset({"spring", "rockslide", "eagle", "oracle", "shade", "smoke"})
EVENT_OPTIONS = {
    # The last option always walks away at no cost.
    "boulder": ("help", "around"),
    "wall": ("take", "leave"),
    "satyr": ("wager", "decline"),
    "kid": ("carry", "sell", "leave"),
    "shrine": ("offer", "pass"),
    "hive": ("reach", "leave"),
    "toll": ("pay", "fight", "back"),
}
ROCKSLIDE_SHARE = 0.20
EAGLE_KILLS = 2.0
BOULDER_HP_SHARE = 0.25
BOULDER_LESSON_CHANCE = 0.10
WALL_GARDENER_CHANCE = 0.25
GARDENER_FACTOR = 1.10
SATYR_BASE_CHANCE, SATYR_CHARM_STEP, SATYR_MAX_CHANCE = 0.45, 0.01, 0.65
SATYR_MAX_STAKE_KILLS = 15
KID_SALE_KILLS = 1.5
SHRINE_OFFERING_KILLS = 1.0
SHRINE_CHANCE = 1 / 3
SHRINE_EXTRA_FIGHTS = 3
HIVE_HONEY_CHANCE = 0.5
HIVE_HONEY_HP = 2
HIVE_STING_SHARE = 1 / 3
TOLL_KILLS = 1.0
TOLL_FIGHT_PAYS = 2           # times the creature's usual purse

# --- the Shepherds' Fire ---------------------------------------------------------
KNUCKLEBONES_PER_DAY = 3
KNUCKLEBONES_MAX_STAKE_KILLS = 10
KNUCKLEBONES_WIN_CHANCE = 0.5

# --- the Camp: robbing the sleeping ---------------------------------------------
ROB_XP_LOSS = 0.05              # what the robbed lose of this level's XP
ROB_XP_KILLS = 2                # a win is worth this many kills' XP at the VICTIM's band
DEFENDED_XP_KILLS = 1           # what a sleeper earns when the robber loses
ROB_LEVELS_BELOW = 1            # you may rob someone at most this many levels beneath you
AWAKE_MINUTES = 10              # acted this recently: awake, and not to be robbed
NEWCOMER_DAYS = 3
IDLE_DAYS = 14
KEY_PRICE_IN_KILLS = 20.0
CAMP_LIST_LENGTH = 9

# --- courtship -------------------------------------------------------------------
REGULARS = ("kalliste", "theron")
# Charm needed for each of the eight steps with a regular.
COURTSHIP_CHARM = (1, 2, 4, 7, 10, 14, 19, 25)
GIFT_STEP = 5                       # "bring a gift" costs drachmae
GIFT_PRICE_IN_KILLS = 3.0
COURT_BASE_CHANCE, COURT_CHARM_STEP = 0.50, 0.05
COURT_MIN_CHANCE, COURT_MAX_CHANCE = 0.30, 0.95
COURT_XP_KILLS = 2
COURT_CHARM_CHANCE = 0.25           # a success sometimes leaves you more charming
SPOUSE_GIFT_KILLS = 1.0             # what a regular you married leaves by the bed each dawn
PARTING_CHARM_LOSS = 2
# Between climbers.
AFFINITY_TO_PROPOSE = 5
CHARM_TO_PROPOSE = 5
SPOUSE_EXTRA_FIGHTS = 2             # at dawn, when your spouse played yesterday
HEARTS_LIST_LENGTH = 9

# --- the Lethe House ----------------------------------------------------------
# Orpheus' songs and how often he picks each. The shares sum to 1.
SONGS = (
    ("road", 0.18), ("bronze", 0.18), ("ferryman", 0.18), ("goatherd", 0.18),
    ("sisters", 0.12), ("stone", 0.08), ("eurydice", 0.04), ("string", 0.04),
)
ROAD_EXTRA_FIGHTS = 3
BRONZE_HP_BOOST = 0.10
FERRYMAN_KILLS = 3            # a purse worth this many kills at your band
ROOM_PRICE_IN_KILLS = 2.0
WINE_PRICE_IN_KILLS = 0.5
WINE_HEAL_SHARE = 0.15
WALL_LINES_SHOWN = 15
WALL_LINES_PER_DAY = 5
WALL_LINE_LENGTH = 120
NEWS_DAYS = 3

# The Orchard Gate: what two pomegranate seeds buy, permanently.
SEEDS_PER_GIFT = 2
GIFTS = {"strength": 2, "defence": 2, "vigour": 5}

CREDIT = "In the tradition of the BBS door games of the early '90s."

assert len(CREATURES) == LEVELS and all(len(band) == CREATURES_PER_BAND for band in CREATURES)
assert len(GATEKEEPERS) == LEVELS - 1 == len(XP_TO_NEXT)
assert len(WEAPONS) == len(ARMOURS) == len(BANDS) == LEVELS
_every_foe = {name for band in CREATURES for name in band} | set(GATEKEEPERS)
assert NO_ARTICLE_FOES <= _every_foe and PLURAL_FOES <= _every_foe
assert abs(sum(share for _, share in SONGS) - 1) < 1e-9
assert sum(weight for _, weight in EVENTS) == 100
assert {name for name, _ in EVENTS} == INSTANT_EVENTS | set(EVENT_OPTIONS)

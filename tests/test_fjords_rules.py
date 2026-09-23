"""Nine Fjords: every rule, with scripted dice."""

import pytest

from lib.fjords import data, rules
from lib.fjords.rules import FARMS, LONGHOUSES, RAID, TAKE, WOODS, Market, NotAllowed
from tests.test_climb_rules import Dice

NO_EVENT = 0.99                # vs EVENT_CHANCE
AN_EVENT = 0.0
CALM = 0.99                    # vs FROST_WEATHER
STORM = 0.0
EVEN = 0.5                     # luck of exactly 1.0, for either side


def realm(**attrs):
    r = rules.new_realm()
    for key, value in attrs.items():
        setattr(r, key, value)
    return r


def quiet_dawn(r, day, market=None):
    """A dawn with no event and Orm's usual prices."""
    return rules.apply_dawn(r, day, Dice(chance=[NO_EVENT]), market or Market())


# ---------------------------------------------------------------------------
# The year
# ---------------------------------------------------------------------------

def test_the_seasons():
    assert [data.season(d) for d in (1, 10, 11, 20, 21, 30)] == ["thaw", "thaw", "sailing", "sailing", "frost", "frost"]


def test_a_new_realm_is_the_forty_steadings_of_the_design():
    r = rules.new_realm()
    assert (r.land, r.farms, r.woods, r.longhouses, r.wild) == (40, 20, 5, 5, 10)
    assert (r.folk, r.silver, r.grain, r.timber, r.ships, r.honour, r.turns) == (400, 300, 200, 50, 1, 10, 12)
    assert r.roofs == 700 and r.levy == 40 and r.hold == 40


# ---------------------------------------------------------------------------
# Dawn
# ---------------------------------------------------------------------------

def test_dawn_pays_feeds_taxes_and_grows():
    r = realm(huscarls=10, last_day=1)
    report = quiet_dawn(r, 2)
    assert report.grain == 20 * 12 - (400 * 0.1 + 10 * 0.3)          # farms pay, folk and huscarls eat
    assert report.timber == 30 and report.tax == 400 and report.upkeep == 10 + 5
    assert r.folk == 421                                              # 5% growth, rounded up by one
    assert r.turns == 24 and r.last_day == 2 and not report.starved


def test_dawn_is_applied_once_per_day():
    r = realm(last_day=3)
    before = rules.ledger(r)
    quiet_dawn(r, 3)
    assert rules.ledger(r) == before and r.turns == 12
    quiet_dawn(r, 4)
    assert r.turns == 24
    quiet_dawn(r, 4)
    assert r.turns == 24


def test_turns_keep_for_three_days_and_no_more():
    r = realm(turns=30, last_day=1)
    quiet_dawn(r, 2)
    assert r.turns == 36


def test_starving_folk_leave_and_huscarls_desert():
    r = realm(grain=0, farms=1, huscarls=100, last_day=1)
    report = quiet_dawn(r, 2)
    assert report.starved and r.grain == 0
    assert r.folk == 376 and r.huscarls == 90


def test_frost_eats_more_and_the_roofs_cap_growth():
    r = realm(folk=695, last_day=20)
    assert rules.grain_eaten(r, 21) == pytest.approx(695 * 0.1 * 1.5)
    quiet_dawn(r, 21)
    assert r.folk == 700


def test_unpaid_huscarls_walk_before_ships_rot():
    r = realm(silver=0, folk=100, huscarls=150, ships=2, last_day=1)   # tax 100 against upkeep 160
    quiet_dawn(r, 2)
    assert r.silver >= 0 and r.huscarls < 150 and r.ships == 2


def test_orm_buys_what_will_not_keep():
    market = Market()
    r = realm(grain=5000, timber=1000, last_day=1)
    report = quiet_dawn(r, 2, market)
    keep = rules.grain_eaten(r, 2) * 5 + 100
    assert r.grain == pytest.approx(keep) and r.timber == 200
    assert report.sold_for == pytest.approx(report.sold_grain * 0.4 + report.sold_timber * 1.0)


def test_the_days_sailings_and_feast_reset_at_dawn():
    r = realm(sailings=["a", "b"], feasted=True, sung_days=3, last_day=1)
    quiet_dawn(r, 2)
    assert r.sailings == [] and not r.feasted and r.sung_days == 2


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def test_events_are_one_day_in_five_and_weighted():
    assert rules.roll_event(Dice(chance=[NO_EVENT])) == ""
    assert rules.roll_event(Dice(chance=[AN_EVENT], rolls=[1])) == "whale"
    assert rules.roll_event(Dice(chance=[AN_EVENT], rolls=[100])) == "wedding"
    assert rules.roll_event(Dice(chance=[AN_EVENT], rolls=[13])) == "hard_frost"


@pytest.mark.parametrize("event, field, change", [
    ("whale", "grain", 150), ("stranger", "silver", 100), ("driftwood", "timber", 80),
    ("skald", "honour", 2), ("missionary", "folk", 0),
])
def test_simple_events(event, field, change):
    r = rules.new_realm()
    before = getattr(r, field)
    rules.apply_event(r, event)
    assert getattr(r, field) == before + change


def test_the_shipwright_needs_a_boatyard():
    r = rules.new_realm()
    assert rules.apply_event(r, "shipwright") == 50 and r.ships == 1 and r.silver == 350
    r.boatyards = 1
    assert rules.apply_event(r, "shipwright") == 1 and r.ships == 2


def test_a_landslip_spares_the_last_wood_and_sickness_spares_the_floor():
    r = realm(woods=1, folk=52)
    assert rules.apply_event(r, "landslip") == 0 and r.woods == 1
    assert rules.apply_event(r, "sickness") == 2 and r.folk == 50


def test_hard_frost_and_good_year_act_at_dawn():
    good = realm(last_day=1)
    rules.apply_dawn(good, 2, Dice(chance=[AN_EVENT], rolls=[50]), Market())      # good_year
    plain = realm(last_day=1)
    quiet_dawn(plain, 2)
    # Orm buys the surplus at dawn, so the good year shows up as silver.
    assert good.silver - plain.silver == pytest.approx(20 * 12 * 0.4)


# ---------------------------------------------------------------------------
# The hall
# ---------------------------------------------------------------------------

def test_clearing_costs_more_as_the_realm_grows_half_in_thaw_and_never_in_frost():
    r = rules.new_realm()
    assert rules.clear_cost(r, 1) == 10 and rules.clear_cost(r, 11) == 20
    r.wild += 40
    assert rules.clear_cost(r, 11) == 40
    rules.apply_clear(r, 11)
    assert r.wild == 51 and r.turns == 11 and r.silver == 260
    with pytest.raises(NotAllowed, match="frost"):
        rules.apply_clear(r, 25)


def test_raising_and_pulling_down():
    r = rules.new_realm()
    rules.apply_raise(r, FARMS)
    assert (r.farms, r.wild, r.silver, r.timber, r.turns) == (21, 9, 270, 40, 11)
    with pytest.raises(NotAllowed):
        rules.apply_raise(r, "castle")
    rules.apply_pull_down(r, FARMS)
    assert (r.farms, r.wild, r.timber) == (20, 10, 45)
    r.wild = 0
    with pytest.raises(NotAllowed, match="no_wild"):
        rules.apply_raise(r, WOODS)


def test_training_takes_folk_but_never_below_a_hundred():
    r = rules.new_realm()
    rules.apply_train(r, 10)
    assert (r.huscarls, r.folk, r.turns, r.silver, r.grain) == (10, 390, 11, 150, 150)
    with pytest.raises(NotAllowed, match="no_folk"):
        rules.apply_train(r, 300)
    with pytest.raises(NotAllowed, match="no_silver"):
        rules.apply_train(r, 20)
    rules.apply_dismiss(r, 5)
    assert (r.huscarls, r.folk) == (5, 395)


def test_a_boatyard_halves_a_ships_timber():
    r = realm(timber=100)
    assert rules.ship_cost(r) == (60, 40)
    r.boatyards = 1
    assert rules.ship_cost(r) == (30, 40)
    rules.apply_ship(r)
    assert (r.ships, r.timber, r.silver, r.turns) == (2, 70, 260, 10)


def test_the_palisade_has_five_levels():
    r = realm(silver=100_000)
    for level in range(1, 6):
        assert rules.palisade_cost(r) == 100 * level
        rules.apply_palisade(r)
    with pytest.raises(NotAllowed, match="palisade_done"):
        rules.apply_palisade(r)
    assert rules.strength_at_home(r) == pytest.approx(40 * (1.2 + 0.5))


def test_one_feast_a_day():
    r = rules.new_realm()
    rules.apply_feast(r)
    assert r.feasted and r.honour == 11 and r.grain == 100 and r.silver == 250
    with pytest.raises(NotAllowed, match="feasted"):
        rules.apply_feast(r)
    r.last_day = 1
    quiet_dawn(r, 2)
    assert r.folk == 441                                              # a tenth, the night of the feast


def test_honour_is_capped():
    r = realm(honour=49)
    rules.apply_feast(r)
    assert r.honour == 50
    r.honour = -45
    rules.apply_pact_broken(r)
    assert r.honour == -50


# ---------------------------------------------------------------------------
# Saltvik
# ---------------------------------------------------------------------------

def test_selling_moves_the_price_and_it_drifts_back():
    market = Market()
    r = realm(grain=4000)
    got = rules.apply_sell(r, market, grain=4000)
    assert got == 1600 and r.grain == 0 and r.turns == 11
    assert market.grain_price == pytest.approx(0.4 * 0.8)            # the biggest drop one visit can cause
    rules.apply_market_dawn(market)
    assert market.grain_price == pytest.approx(0.32 + (0.4 - 0.32) / 3)
    for _ in range(20):
        rules.apply_sell(realm(grain=4000), market, grain=4000)
    assert market.grain_price == pytest.approx(0.2)                   # never below half


def test_orm_sells_dear_and_not_on_credit():
    r = realm(silver=100)
    assert rules.apply_buy(r, Market(), grain=100) == 60 and r.grain == 300
    with pytest.raises(NotAllowed, match="no_silver"):
        rules.apply_buy(r, Market(), timber=1000)


# ---------------------------------------------------------------------------
# The sea
# ---------------------------------------------------------------------------

def test_who_may_be_sailed_against():
    me, them = realm(huscarls=50), realm(joined_day=1, last_day=10)
    them.wild += 0
    assert rules.may_sail(me, me, "me", 10) == "yourself"
    assert rules.may_sail(me, them, "them", 10, pact=True) == "pact"
    assert rules.may_sail(me, them, "them", 3) == "peace"             # their first five days
    small = realm(farms=5, woods=1, longhouses=1, wild=0, joined_day=1, last_day=10)
    assert small.land < 30 and rules.may_sail(me, small, "small", 10) == "peace"
    gone = realm(joined_day=1, last_day=5)
    assert rules.may_sail(me, gone, "gone", 8) == "absent"
    assert rules.may_sail(me, gone, "gone", 7) is None
    me.sailings = ["a", "b", "c"]
    assert rules.may_sail(me, them, "them", 10) == "sailed_enough"
    me.sailings = ["them"]
    assert rules.may_sail(me, them, "them", 10) == "sailed_already"
    me.sailings, me.ships = [], 0
    assert rules.may_sail(me, them, "them", 10) == "no_ships"


def test_a_raid_won_takes_a_quarter_of_the_stores_and_nothing_else_changes_hands():
    me = realm(huscarls=40, silver=0, grain=0, timber=0, turns=12)
    them = realm(huscarls=5, silver=1000, grain=400, timber=100, last_day=10)
    s = rules.sail(RAID, me, them, "them", 40, 10, Dice(chance=[EVEN, EVEN]))    # even luck: ratio 120/(15+40)/1.2
    assert s.kind == RAID and s.won and s.ratio == pytest.approx(120 / 66, abs=0.01)
    assert (s.silver, s.grain, s.timber) == (250, 100, 25) and s.steadings == {}
    assert (me.silver, me.grain, me.timber, me.turns) == (250, 100, 25, 9)
    assert s.party_lost == int(40 * min(0.3, 0.15 / s.ratio)) and me.huscarls == 40 - s.party_lost
    assert s.huscarls == 1 and s.folk == 4
    rules.apply_settlement(them, s)
    assert (them.silver, them.grain, them.timber, them.huscarls, them.folk) == (750, 300, 75, 4, 396)
    assert me.sailings == ["them"]


def test_in_sailing_season_a_raid_is_cheaper_and_takes_a_third():
    me = realm(huscarls=40, silver=0)
    them = realm(huscarls=0, silver=900, last_day=15)
    s = rules.sail(RAID, me, them, "them", 40, 15, Dice(chance=[EVEN, EVEN]))
    assert me.turns == 10 and s.silver == pytest.approx(300)


def test_a_raid_lost_costs_the_party_and_takes_nothing():
    me = realm(huscarls=10)
    them = realm(huscarls=100, silver=1000, last_day=10)
    s = rules.sail(RAID, me, them, "them", 10, 10, Dice(chance=[EVEN, EVEN]))
    assert not s.won and s.silver == 0 and s.party_lost == 3 and me.huscarls == 7
    assert s.huscarls == 10                                           # they lose a tenth, even winning
    rules.apply_settlement(them, s)
    assert them.silver == 1000 and them.huscarls == 90


def test_land_taking_needs_a_decisive_win_and_takes_a_tenth():
    me = realm(huscarls=100, ships=3)
    them = realm(huscarls=0, wild=3, woods=5, farms=20, longhouses=5, last_day=10)   # land 33
    s = rules.sail(TAKE, me, them, "them", 100, 10, Dice(chance=[EVEN, EVEN]))
    assert s.won and s.ratio == pytest.approx(300 / 48, abs=0.01)
    assert s.steadings == {"wild": 3} and me.wild == 13 and me.turns == 8 and me.honour == 12
    rules.apply_settlement(them, s)
    assert them.wild == 0 and them.land == 30

    close = realm(huscarls=30, ships=1)                                          # 90 against 39 levy x 1.2: not twice
    s = rules.sail(TAKE, close, them, "them", 30, 10, Dice(chance=[EVEN, EVEN]))
    assert s.ratio == pytest.approx(90 / 46.8, abs=0.01) and not s.won and s.steadings == {}
    enough = realm(huscarls=40, ships=1)                                         # 120 against 46.8: decisive
    s = rules.sail(TAKE, enough, them, "them", 40, 10, Dice(chance=[EVEN, EVEN]))
    assert s.won and s.steadings == {"woods": 3}


def test_land_taking_never_takes_the_last_of_anything():
    me = realm(huscarls=200, ships=5)
    them = realm(wild=0, woods=1, farms=1, longhouses=1, huscarls=0, folk=100, last_day=10)   # land 3 (peace; but the rule itself)
    them.farms = 30                                                   # land 32; a tenth is 3
    s = rules.sail(TAKE, me, them, "them", 200, 10, Dice(chance=[EVEN, EVEN]))
    assert s.steadings == {"farms": 3}


def test_bullying_costs_honour_and_beating_an_equal_earns_it():
    big = realm(huscarls=200, ships=5, silver=5000, wild=100)
    small = realm(huscarls=0, last_day=10)
    assert rules.renown(small) < rules.renown(big) * 0.5
    rules.sail(RAID, big, small, "small", 40, 10, Dice(chance=[EVEN, EVEN]))
    assert big.honour == 8
    rules.sail(TAKE, big, small, "small2", 150, 10, Dice(chance=[EVEN, EVEN]))
    assert big.honour == 5
    peer_me, peer = realm(huscarls=100, ships=3), realm(huscarls=0, last_day=10)
    rules.sail(TAKE, peer_me, peer, "peer", 100, 10, Dice(chance=[EVEN, EVEN]))
    assert peer_me.honour == 12


def test_frost_weather_turns_a_sailing_back_with_the_turns_spent():
    me = realm(huscarls=40)
    them = realm(silver=1000, last_day=25)
    s = rules.sail(RAID, me, them, "them", 40, 25, Dice(chance=[STORM]))
    assert s.weather and not s.won and me.turns == 9 and me.silver == 300 and me.huscarls == 40
    rules.apply_settlement(them, s)
    assert them.silver == 1000


def test_the_sea_refuses_the_impossible():
    me = realm(huscarls=5, ships=1, turns=2)
    them = realm(last_day=10)
    with pytest.raises(NotAllowed, match="too_few"):
        rules.sail(RAID, me, them, "them", 5, 10, Dice())
    me.huscarls = 100
    with pytest.raises(NotAllowed, match="no_hold"):
        rules.sail(RAID, me, them, "them", 100, 10, Dice())
    with pytest.raises(NotAllowed, match="no_turns"):
        rules.sail(RAID, me, them, "them", 40, 10, Dice())


# ---------------------------------------------------------------------------
# The watchers
# ---------------------------------------------------------------------------

def test_watchers_succeed_or_are_caught():
    me, them = realm(), realm(silver=1000, grain=500, folk=400, watchers=2)
    assert rules.watch_chance(them, 0) == pytest.approx(0.6) and rules.watch_chance(them, 2) == pytest.approx(0.7)
    report, s = rules.send_watcher(data.LOOK, me, them, 0, Dice(chance=[0.5]))
    assert not report.caught and report.ledger["silver"] == 1000 and s is None and me.turns == 11 and me.silver == 280
    report, s = rules.send_watcher(data.STEAL, me, them, 1, Dice(chance=[0.5]))
    assert report.n == 100 and s.silver == 100 and me.silver == 360               # 280 - 20 + 100
    rules.apply_settlement(them, s)
    assert them.silver == 900
    report, s = rules.send_watcher(data.BURN, me, them, 2, Dice(chance=[0.99]))
    assert report.caught and s is None and me.honour == 8
    report, s = rules.send_watcher(data.WHISPER, me, them, 3, Dice(chance=[0.1]))
    assert s.folk == 12 and me.folk == 406


def test_stealing_is_capped():
    me, them = realm(), realm(silver=100_000)
    _, s = rules.send_watcher(data.STEAL, me, them, 0, Dice(chance=[0.0]))
    assert s.silver == 200


# ---------------------------------------------------------------------------
# Renown, the song, Yule
# ---------------------------------------------------------------------------

def test_renown_is_mostly_land():
    r = rules.new_realm()
    assert rules.renown(r) == 400 + 40 + 0 + 20 + 6
    r.wild += 100
    assert rules.renown(r) == 1466


def test_eyvind_sings_of_the_honourable_every_tenth_day():
    r = realm(honour=31)
    assert not rules.apply_song(r, 9) and rules.apply_song(r, 10) and r.sung_days == 21
    assert rules.yule_renown(r, 10) == rules.renown(r) + 21
    plain = realm(honour=30)
    assert not rules.apply_song(plain, 10)


def test_yule_keeps_only_the_crowns():
    r = realm(wild=200, silver=9999, huscarls=300, honour=40, crowns=1, npc="raider", home="elsewhere")
    rules.apply_yule(r, crowned=True)
    assert (r.land, r.silver, r.huscarls, r.honour, r.crowns, r.npc, r.home) == (40, 300, 0, 10, 2, "raider", "elsewhere")

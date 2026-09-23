"""Nine Fjords: the shape of a whole year, checked by playing it.

These run the simulator over the real rules and pin the targets of the
design's §16, so that a well-meant tweak to a constant cannot quietly make a
farmer unbeatable, a raider pointless, or a small realm erasable.
"""

import statistics
from pathlib import Path

import pytest

from lib.fjords import data, rules, sim

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def coasts():
    return sim.years(40)


def test_a_farmer_alone_reaches_the_intended_size():
    sizes = [sim.farmer_alone(i).land for i in range(10)]
    assert 120 <= statistics.median(sizes) <= 180, sizes


def test_no_habit_always_wins(coasts):
    wins = {}
    for c in coasts:
        wins[c.standings()[0][0]] = wins.get(c.standings()[0][0], 0) + 1
    assert max(wins.values()) <= 0.65 * len(coasts), wins
    assert len(wins) >= 2


def test_the_aggressive_habits_are_viable(coasts):
    """They need not win, but a raider or conqueror who plays the whole year is not a footnote."""
    for habit in ("raider", "conqueror"):
        theirs = statistics.median(c.realms[habit].land for c in coasts)
        best = statistics.median(max(r.land for r in c.realms.values()) for c in coasts)
        assert theirs >= best * 0.45, (habit, theirs, best)


def test_nobody_is_ever_erased(coasts):
    for c in coasts:
        for r in c.realms.values():
            assert r.land >= data.PEACE_LAND - data.PEACE_LAND * data.TAKE_SHARE
            assert r.folk > data.FOLK_FLOOR
            assert r.farms >= 1 and r.woods >= 1 and r.longhouses >= 1


def test_a_well_kept_hold_repels_an_equal_raider():
    assert sim.repel_rate(200) >= 0.70


def test_the_absent_are_safe_and_dawns_catch_up():
    coast = sim.Coast(sim.FOUR, seed=3)
    coast.play_year(absent_on={"farmer": lambda day: 5 <= day <= 12})
    farmer = coast.realms["farmer"]
    assert farmer.last_day == 30                                   # the missed dawns were applied on return
    # Absent from day 5, untouchable from day 7 until back on day 13.
    assert not any(7 <= day <= 12 and target == "farmer" for day, _, target, *_ in coast.log)


def test_playing_every_other_day_is_not_ruinous():
    daily = sim.Coast({"a": data.FARMER, "b": data.FARMER}, seed=9).play_year()
    halved = sim.Coast({"a": data.FARMER, "b": data.FARMER}, seed=9).play_year(absent_on={"b": lambda day: day % 2 == 0})
    every_day = rules.renown(daily.realms["b"])
    every_other = rules.renown(halved.realms["b"])
    assert every_other >= every_day * 2 / 3, (every_day, every_other)


def test_nothing_borrowed_appears_in_the_game():
    """No proper noun from the games that inspired this one, in code, prose or templates."""
    borrowed = [w.lower() for w in (
        "Barren", "Solar Realms", "Trade Wars", "Tradewars", "Usurper", "Global War", "Food Fight",
        "Hyperion", "Regime", "Empire Deluxe", "Falcon", "Overkill",
    )]
    shipped = [ROOT / "lib" / "fjords", ROOT / "frontend" / "templates", ROOT / "frontend" / "static", ROOT / "admin"]
    for base in shipped:
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".html", ".js", ".css"):
                text = path.read_text(encoding="utf-8").lower()
                for word in borrowed:
                    assert word not in text, (path, word)

"""The Long Climb: the shape of the whole game, checked by playing it.

These run the simulator over the real rules. They exist because the numbers
that matter most are not visible in any table: during design, a healing price
that merely *sounded* reasonable made the game impossible to finish.
"""

import statistics
from pathlib import Path
from random import Random

import pytest

from lib.climb import data, rules, sim

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def first_ascents():
    return sim.first_ascents(80)


def test_a_first_ascent_takes_about_a_month(first_ascents):
    assert all(r.finished for r in first_ascents)
    assert 25 <= statistics.median(r.days for r in first_ascents) <= 40


def test_no_band_is_a_slog_or_a_blink(first_ascents):
    spent: dict[int, list[int]] = {}
    for report in first_ascents:
        previous = 0
        for day, level in report.reached:
            spent.setdefault(level, []).append(day - previous)
            previous = day
    assert sorted(spent) == list(range(2, 13))
    for level, days in spent.items():
        assert 1 <= statistics.median(days) <= 5, (level, statistics.median(days))


def test_the_climb_is_dangerous_but_not_a_meat_grinder(first_ascents):
    assert statistics.median(r.deaths for r in first_ascents) <= 4
    assert any(r.deaths for r in first_ascents)


def test_a_veteran_climbs_about_as_fast_as_a_newcomer():
    veterans = sim.first_ascents(40, seed=5000, ascents=5, strength_gift=12, defence_gift=8)
    assert all(r.finished for r in veterans)
    assert 25 <= statistics.median(r.days for r in veterans) <= 45


def test_even_the_tenth_ascent_can_be_finished():
    hardest = sim.first_ascents(20, seed=7000, ascents=10)
    assert all(r.finished for r in hardest)


@pytest.mark.parametrize("level", range(1, 12))
def test_gear_matters_at_the_gate_without_being_a_wall(level):
    rng = Random(level)
    gate = rules.gatekeeper(level)
    assert sim.win_rate(rng, level, gate, trials=800) >= 0.65
    if level > 1:
        assert 0.15 <= sim.win_rate(rng, level, gate, tiers_behind=1, trials=800) <= 0.65


def test_ladon_is_a_coin_flip_in_the_best_gear_and_hopeless_without():
    rng = Random(12)
    assert 0.35 <= sim.win_rate(rng, 12, rules.ladon(), trials=1500) <= 0.65
    assert sim.win_rate(rng, 12, rules.ladon(), tiers_behind=1, trials=1500) <= 0.15


def test_the_healing_price_really_is_a_cliff(monkeypatch):
    """Guards the comment on FULL_HEAL_IN_KILLS: this is why nobody should nudge it casually."""
    monkeypatch.setattr(data, "FULL_HEAL_IN_KILLS", 5.0)
    assert not any(r.finished for r in sim.first_ascents(6, seed=300))


# ---------------------------------------------------------------------------
# Ground rule: this is an original game (DESIGN.md section 0)
# ---------------------------------------------------------------------------

# Proper nouns belonging to other people's games and books. None may appear in
# anything the game ships. The list lives in a test, not in the game.
_NOT_OURS = (
    "red dragon", "green dragon", "l.o.r.d", "seth able", "violet", "turgon", "barak",
    "halder", "aragorn", "gandalf", "olodrin", "sandtiger", "sparhawk", "atsuko",
    "aladdin", "caspian", "dark cloak", "erdrick", "jennie", "abdul", "king arthur",
)


def _shipped_text() -> str:
    paths = list((ROOT / "lib" / "climb").rglob("*.py"))
    paths += list((ROOT / "frontend" / "templates").rglob("climb*"))
    paths += list((ROOT / "frontend" / "static" / "js").glob("climb*"))
    return "\n".join(p.read_text(encoding="utf-8").lower() for p in paths if p.is_file())


def test_nothing_borrowed_appears_in_the_game():
    text = _shipped_text()
    assert [name for name in _NOT_OURS if name in text] == []


def test_the_credit_line_is_the_agreed_one():
    assert data.CREDIT == "In the tradition of the BBS door games of the early '90s."

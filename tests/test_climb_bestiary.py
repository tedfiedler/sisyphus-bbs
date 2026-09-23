"""Every creature has a face and an exit: two lines when it appears, one when it is beaten."""

import pytest

from lib.climb import data, rules, text
from tests.helpers import client_for
from tests.test_climb_routes import (  # noqa: F401  (fixtures)
    PAGE, PLAIN, NO_AMBUSH, NO_EVENT, act, alice, begin, dice, fixed_day,
)


def test_the_bestiary_and_the_prose_name_the_same_creatures():
    names = {name for band in data.CREATURES for name in band}
    assert names <= set(text.FOES)
    # The one creature no band lists: an event conjures it (rules.resolve_event).
    assert set(text.FOES) - names == {"Furious Gardener"}
    for name, (seen, beaten) in text.FOES.items():
        assert seen.endswith(".") and beaten.endswith("."), name
        assert 40 < len(seen) < 260 and 20 < len(beaten) < 200, name
        assert "{" not in seen + beaten, name          # nothing left to fill in


@pytest.mark.asyncio
async def test_a_creature_is_described_when_met_and_seen_off_when_beaten(alice, dice):
    goat_seen, goat_beaten = text.FOES["Irritable Goat"]
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:slopes")
        dice(chance=[NO_EVENT, NO_AMBUSH], rolls=[1])                  # rank 1: an Irritable Goat
        await act(client, "seek")
        html = (await client.get(PAGE)).text
        assert "Something moves on the path ahead: the Irritable Goat." in html
        assert goat_seen in html and goat_beaten not in html

        dice(chance=[PLAIN, 0.99], rolls=["max"])                      # one full blow; no seed
        await act(client, "fight:attack")
        html = (await client.get(PAGE)).text
        assert "Irritable Goat is beaten." in html
        assert html.index(goat_beaten) > html.index("Irritable Goat is beaten.")
        assert goat_seen not in html


def test_people_are_not_described_like_creatures():
    """Gatekeepers and Ladon have their own prose; the bestiary is only consulted for creatures."""
    for level in range(1, 12):
        gatekeeper = rules.gatekeeper(level, 0)
        assert gatekeeper.kind != rules.CREATURE and gatekeeper.name not in text.FOES
    assert rules.ladon(0).kind != rules.CREATURE and rules.ladon(0).name not in text.FOES

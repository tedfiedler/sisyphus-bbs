"""The Long Climb, step 5b: things on the Slopes that are not fights, and the Shepherds' Fire."""

from html import unescape

import pytest

from lib.climb import data, rules, scenes, store, text
from tests.helpers import client_for
from tests.test_climb_routes import PAGE, act, begin, offered, tweak
from tests.test_climb_routes import alice, dice, fixed_day  # noqa: F401  (fixtures)
from tests.test_climb_rules import AN_EVENT, NO_AMBUSH, NO_EVENT, Dice, climber


def pick(event: str) -> int:
    """A 1..100 roll that lands on the given event."""
    roll = 0
    for name, weight in data.EVENTS:
        if name == event:
            return roll + 1
        roll += weight
    raise KeyError(event)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def test_the_event_table_is_reachable_end_to_end():
    assert rules.is_event(Dice(chance=[AN_EVENT])) and not rules.is_event(Dice(chance=[NO_EVENT]))
    seen = {rules.roll_event(Dice(rolls=[n]), climber()) for n in range(1, 101)}
    assert seen == {name for name, _ in data.EVENTS}
    for name, _ in data.EVENTS:
        assert rules.roll_event(Dice(rolls=[pick(name)]), climber()) == name


def test_every_event_and_every_outcome_has_words():
    for kind, options in data.EVENT_OPTIONS.items():
        assert kind in text.EVENT_INTRO and set(text.EVENT_OPTIONS[kind]) == set(options)
        keys = [key for key, _ in text.EVENT_OPTIONS[kind].values()]
        assert len(keys) == len(set(keys))
        assert f"{kind}_{options[-1]}" in text.EVENT_RESULT       # walking away
    for line in text.EVENT_RESULT.values():
        line.format(n=3)


def test_instant_events():
    c = climber(level=4, hp=10)
    assert rules.resolve_event(Dice(), c, "spring").n == data.MAX_HP[3] - 10 and c.hp == data.MAX_HP[3]

    c = climber(level=4)
    lost = rules.resolve_event(Dice(), c, "rockslide").n
    assert lost == round(data.MAX_HP[3] * 0.20) and c.hp == data.MAX_HP[3] - lost
    c = climber(level=4, hp=3)
    assert rules.resolve_event(Dice(), c, "rockslide").n == 2 and c.hp == 1      # never fatal

    c = climber(level=4, purse=5)
    found = rules.resolve_event(Dice(), c, "eagle").n
    assert found == round(data.REF_DRACHMAE[3] * 2) and c.purse == 5 + found

    assert rules.resolve_event(Dice(), climber(level=2, xp=100), "oracle").n == data.XP_TO_NEXT[1] - 100
    assert rules.resolve_event(Dice(), climber(level=2, xp=10**9), "oracle").n == 0
    assert rules.resolve_event(Dice(), climber(level=12), "oracle").key == "oracle_garden"

    c = climber(rank=40)
    assert rules.resolve_event(Dice(), c, "shade").n == 40                       # capped

    c = climber()
    assert rules.resolve_event(Dice(), c, "smoke").key == "smoke" and c.fire_known
    assert rules.roll_event(Dice(rolls=[pick("smoke")]), c) == "eagle"           # found already


def test_walking_away_always_costs_nothing():
    for kind, options in data.EVENT_OPTIONS.items():
        c = climber(level=3, purse=500)
        before = (c.hp, c.purse, c.xp, c.charm, c.seeds, c.rank)
        dice = Dice()
        assert rules.resolve_event(dice, c, kind, options[-1]).key == f"{kind}_{options[-1]}"
        assert before == (c.hp, c.purse, c.xp, c.charm, c.seeds, c.rank)


def test_the_boulder():
    c = climber(level=5)
    result = rules.resolve_event(Dice(chance=[0.99]), c, "boulder", "help")
    assert result.key == "boulder_help" and c.xp == data.REF_XP[4] and c.rank == 0
    assert c.hp == data.MAX_HP[4] - round(data.MAX_HP[4] * 0.25)

    c = climber(level=5, hp=2)
    assert rules.resolve_event(Dice(chance=[0.0]), c, "boulder", "help").key == "boulder_lesson"
    assert c.rank == 1 and c.hp == 1


def test_persephones_wall():
    c = climber(seeds=1)
    assert rules.resolve_event(Dice(chance=[0.99]), c, "wall", "take").n == 2 and c.seeds == 2

    c = climber(level=6, ascents=2)
    result = rules.resolve_event(Dice(chance=[0.0]), c, "wall", "take")
    strongest = rules.creature(6, 8, 2)
    assert result.key == "wall_gardener" and result.foe.name == "Furious Gardener"
    assert result.foe.hp == round(strongest.hp * 1.1) and result.foe.xp == strongest.xp
    assert c.seeds == 0


def test_the_satyrs_wager_favours_the_charming():
    c = climber(purse=100, charm=0)
    assert rules.resolve_event(Dice(chance=[0.44]), c, "satyr", "wager", 40).key == "satyr_won" and c.purse == 140
    assert rules.resolve_event(Dice(chance=[0.46]), c, "satyr", "wager", 40).key == "satyr_lost" and c.purse == 100
    assert rules.resolve_event(Dice(chance=[0.54]), climber(purse=100, charm=10), "satyr", "wager", 1).key == "satyr_won"
    assert rules.resolve_event(Dice(chance=[0.66]), climber(purse=100, charm=90), "satyr", "wager", 1).key == "satyr_lost"

    rich = climber(purse=10**9)
    assert rules.satyr_max_stake(rich) == round(data.REF_DRACHMAE[0] * 15)
    for bad in (0, -1, rules.satyr_max_stake(rich) + 1):
        with pytest.raises(ValueError):
            rules.resolve_event(Dice(), rich, "satyr", "wager", bad)
    assert rich.purse == 10**9
    assert rules.event_options(climber(purse=0), "satyr") == ("decline",)


def test_kid_shrine_hive_and_toll():
    c = climber(charm=2)
    result = rules.resolve_event(Dice(), c, "kid", "carry")
    assert c.charm == 3 and result.news
    c = climber(level=3, purse=0)
    assert rules.resolve_event(Dice(), c, "kid", "sell").n == c.purse == round(data.REF_DRACHMAE[2] * 1.5)

    offering = data.REF_DRACHMAE[0]
    c = climber(purse=100)
    assert rules.resolve_event(Dice(chance=[0.2]), c, "shrine", "offer").key == "shrine_pleased"
    assert (c.purse, c.fights_left) == (100 - offering, 18)
    assert rules.resolve_event(Dice(chance=[0.5]), c, "shrine", "offer").key == "shrine_silent"
    assert rules.event_options(climber(purse=offering - 1), "shrine") == ("pass",)
    with pytest.raises(ValueError):
        rules.resolve_event(Dice(), climber(purse=0), "shrine", "offer")

    c = climber(level=2, hp=10)
    assert rules.resolve_event(Dice(chance=[0.1]), c, "hive", "reach").key == "hive_honey"
    assert (c.hp_gift, c.hp) == (2, 12)
    c = climber(level=2)
    assert rules.resolve_event(Dice(chance=[0.9]), c, "hive", "reach").key == "hive_stung"
    assert c.hp == data.MAX_HP[1] - round(data.MAX_HP[1] / 3) and c.alive

    c = climber(level=4, purse=1000)
    assert rules.resolve_event(Dice(), c, "toll", "pay").n == data.REF_DRACHMAE[3] and c.purse == 1000 - data.REF_DRACHMAE[3]
    result = rules.resolve_event(Dice(), c, "toll", "fight")
    assert result.foe.name == "Toll-Taker" and result.foe.drachmae == rules.creature(4, 8).drachmae * 2
    assert rules.event_options(climber(purse=0), "toll") == ("fight", "back")


def test_knucklebones_and_changing_calling():
    c = climber(level=3, purse=10**6)
    cap = round(data.REF_DRACHMAE[2] * 10)
    assert rules.knucklebones_max_stake(c) == cap
    assert rules.apply_knucklebones(Dice(chance=[0.4]), c, cap) is True and c.purse == 10**6 + cap
    assert rules.apply_knucklebones(Dice(chance=[0.6]), c, 5) is False
    rules.apply_knucklebones(Dice(chance=[0.6]), c, 5)
    assert rules.knucklebones_max_stake(c) == 0                                  # three a day
    with pytest.raises(ValueError):
        rules.apply_knucklebones(Dice(), c, 5)
    for bad in (0, -5, cap + 1):
        with pytest.raises(ValueError):
            rules.apply_knucklebones(Dice(), climber(level=3, purse=10**6), bad)
    assert rules.knucklebones_max_stake(climber(purse=7)) == 7

    c = climber(data.SPEAR, rank=25, skill_left=6)
    rules.apply_new_calling(c, data.TORCH)
    assert (c.calling, c.rank, c.skill_left) == (data.TORCH, 12, 3)
    assert rules.skills(c) == ("flame", "mend")
    for bad in (data.TORCH, "bard"):
        with pytest.raises(ValueError):
            rules.apply_new_calling(c, bad)


def test_the_fire_is_remembered_through_an_ascent():
    c = climber(level=12, fire_known=True)
    rules.apply_ascent(c)
    assert c.fire_known


# ---------------------------------------------------------------------------
# Through the routes
# ---------------------------------------------------------------------------

async def _meet(client, dice, event, user_id):
    await act(client, "go:slopes")
    dice(chance=[AN_EVENT], rolls=[pick(event)])
    await act(client, "seek")
    return await store.load(user_id)


@pytest.mark.asyncio
async def test_an_instant_event_costs_the_climb_and_leaves_you_on_the_slopes(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], hp=3)
        player = await _meet(client, dice, "spring", alice["id"])
        assert player.scene == "slopes" and player.fight is None and player.event is None
        assert player.climber.hp == 24 and player.climber.fights_left == 14
        assert "so cold it aches" in (await client.get(PAGE)).text


@pytest.mark.asyncio
async def test_the_man_with_the_boulder(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        player = await _meet(client, dice, "boulder", alice["id"])
        assert player.scene == "event" and player.event == "boulder" and player.climber.fights_left == 14
        html = unescape((await client.get(PAGE)).text)
        assert "Nearly there" in html and offered(html) == ["event:help", "event:around"]

        dice()                                               # nothing else is possible meanwhile
        for cheat in ("seek", "go:agora", "event:take", "event:wager", "fight:attack"):
            await act(client, cheat)
        assert (await store.load(alice["id"])).scene == "event"

        dice(chance=[0.99])
        await act(client, "event:help")
        player = await store.load(alice["id"])
        assert player.scene == "slopes" and player.event is None
        assert player.climber.xp == data.REF_XP[0] and player.climber.hp == 18
        assert "Same time tomorrow" in unescape((await client.get(PAGE)).text)


@pytest.mark.asyncio
async def test_an_event_can_turn_into_a_fight(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await _meet(client, dice, "wall", alice["id"])
        dice(chance=[0.0, NO_AMBUSH])                        # the gardener was watching; no ambush
        await act(client, "event:take")
        player = await store.load(alice["id"])
        assert player.scene == "fight" and player.fight.foe.name == "Furious Gardener" and player.event is None
        html = unescape((await client.get(PAGE)).text)
        assert "very firm view of property" in html and "fight:run" in offered(html)


@pytest.mark.asyncio
async def test_the_satyr_takes_a_stake_and_refuses_a_silly_one(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await _meet(client, dice, "satyr", alice["id"])
        html = unescape((await client.get(PAGE)).text)
        assert "any stake up to 60 drachmae" in html and 'max="60"' in html

        dice()
        await act(client, "event:wager", amount=61)
        player = await store.load(alice["id"])
        assert player.scene == "event" and player.climber.purse == 60            # still waiting

        dice(chance=[0.1])
        await act(client, "event:wager", amount=25)
        player = await store.load(alice["id"])
        assert player.climber.purse == 85 and player.scene == "slopes"


@pytest.mark.asyncio
async def test_carrying_the_kid_home_makes_the_news(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await _meet(client, dice, "kid", alice["id"])
        dice()
        await act(client, "event:carry")
        assert (await store.load(alice["id"])).climber.charm == 1
        await act(client, "go:agora")
        await act(client, "go:herald")
        assert "lost goat on their shoulders" in unescape((await client.get(PAGE)).text)


@pytest.mark.asyncio
async def test_an_unanswered_event_is_gone_by_morning(alice, dice, fixed_day):
    from datetime import timedelta

    async with await client_for(alice["id"]) as client:
        await begin(client)
        await _meet(client, dice, "hive", alice["id"])
        fixed_day["today"] += timedelta(days=1)
        await client.get(PAGE)
    player = await store.load(alice["id"])
    assert player.event is None and player.scene == "agora"


@pytest.mark.asyncio
async def test_the_shepherds_fire(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client, data.SPEAR)
        await act(client, "go:slopes")
        assert "go:fire" not in offered((await client.get(PAGE)).text)
        await act(client, "go:fire")                         # you cannot walk to a place you have not found
        assert (await store.load(alice["id"])).scene == "slopes"

        await act(client, "go:agora")
        await _meet(client, dice, "smoke", alice["id"])
        html = unescape((await client.get(PAGE)).text)
        assert "make room as if they had been expecting you" in html and "go:fire" in offered(html)

        await tweak(alice["id"], rank=9)
        await act(client, "go:fire")
        html = unescape((await client.get(PAGE)).text)
        assert offered(html) == ["knucklebones", "calling:torch", "calling:sandal", "go:others", "go:slopes"]
        assert "up to 60 drachmae a throw, 3 more today" in html

        dice(chance=[0.9])
        await act(client, "knucklebones", amount=20)
        assert (await store.load(alice["id"])).climber.purse == 40
        dice()
        await act(client, "knucklebones", amount=500)
        assert text.KNUCKLES_REFUSED in unescape((await client.get(PAGE)).text)

        await act(client, "calling:sandal")
        c = (await store.load(alice["id"])).climber
        assert (c.calling, c.rank) == (data.SANDAL, 4)
        html = unescape((await client.get(PAGE)).text)
        assert "you follow The Sandal, at rank 4" in html
        assert offered(html) == ["knucklebones", "calling:spear", "calling:torch", "go:others", "go:slopes"]


def test_every_event_screen_has_distinct_hotkeys_and_ends_with_a_way_out():
    for kind in data.EVENT_OPTIONS:
        player = store.Player(user_id=1, climber=climber(purse=10**6), scene="event", event=kind)
        choices = scenes.screen(player).choices
        keys = [choice.key for choice in choices]
        assert len(keys) == len(set(keys)) and len(choices) >= 2
        assert choices[-1].action == f"event:{data.EVENT_OPTIONS[kind][-1]}"

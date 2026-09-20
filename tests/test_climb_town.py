"""The Long Climb, step 3: the shops, the gatekeepers, the Orchard Gate — and the whole climb."""

from datetime import timedelta
from html import unescape
from random import Random

import pytest

from lib import auth
from lib.climb import data, rules, scenes, store, text
from lib.climb.rules import Outcome
from tests.helpers import client_for
from tests.test_climb_routes import DAY_ONE, PAGE, act, begin, offered, tweak
from tests.test_climb_routes import alice, dice, fixed_day  # noqa: F401  (fixtures)
from tests.test_climb_rules import NO_AMBUSH, PLAIN, Dice, climber


# ---------------------------------------------------------------------------
# Rules added in this step
# ---------------------------------------------------------------------------

def test_gear_on_offer_is_everything_better_up_to_one_tier_above_your_level():
    c = climber(level=4, weapon=2, purse=rules.gear_cost(climber(level=4, weapon=2), "weapon", 4))
    assert rules.gear_on_offer(c, "weapon") == [
        (3, rules.gear_cost(c, "weapon", 3), True),
        (4, rules.gear_cost(c, "weapon", 4), True),
        (5, rules.gear_cost(c, "weapon", 5), False),
    ]
    assert rules.gear_on_offer(climber(level=12, armour=12), "armour") == []
    assert [tier for tier, _, _ in rules.gear_on_offer(climber(level=12, armour=10), "armour")] == [11, 12]


def test_gifts_cost_two_seeds_and_are_permanent():
    c = climber(level=3, seeds=5, hp=10)
    assert rules.apply_gift(c, "strength") == 2 and rules.apply_gift(c, "defence") == 2
    assert (c.seeds, c.strength_gift, c.defence_gift) == (1, 2, 2)
    assert not rules.can_take_gift(c)
    with pytest.raises(ValueError):
        rules.apply_gift(c, "vigour")

    c.seeds = 2
    before = rules.max_hp(c)
    assert rules.apply_gift(c, "vigour") == 5
    assert rules.max_hp(c) == before + 5 and c.hp == 15

    with pytest.raises(ValueError):
        rules.apply_gift(climber(seeds=9), "luck")
    assert not rules.can_take_gift(climber(seeds=9, alive=False))

    rules.apply_ascent(c)
    assert (c.strength_gift, c.defence_gift, c.hp_gift) == (2, 2, 5)


def test_every_gatekeeper_has_something_to_say():
    assert len(text.GATEKEEPERS) == len(data.GATEKEEPERS)
    for name, lines in zip(data.GATEKEEPERS, text.GATEKEEPERS):
        assert len(lines) == 3 and all(len(line) > 20 for line in lines)
        first_name = name.replace("The ", "").replace("Old ", "").split()[0]
        assert first_name in lines[0], (name, lines[0])


# ---------------------------------------------------------------------------
# Shops
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_forge(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:forge")
        html = (await client.get(PAGE)).text
        assert "You carry: Olive Branch." in html
        assert "Shepherd&#39;s Crook: 645 drachmae. (You have 60.)" in html       # 910 less half of 530
        assert offered(html) == ["go:agora"]

        await tweak(alice["id"], purse=2000, level=3)
        html = (await client.get(PAGE)).text
        assert offered(html) == ["buy:weapon:2", "buy:weapon:3", "go:agora"]   # tier 4 shown, not affordable
        assert "Hunting Spear: 2535 drachmae. (You have 2000.)" in html

        await act(client, "buy:weapon:3")
        c = (await store.load(alice["id"])).climber
        assert c.weapon == 3 and c.purse == 2000 - (1600 - 265)
        html = (await client.get(PAGE)).text
        assert "hands you the Bronze Knife" in html and "You carry: Bronze Knife." in html

        # Not on the screen, so not for sale: a tier too high, a downgrade, the other shop's goods.
        for cheat in ("buy:weapon:5", "buy:weapon:12", "buy:weapon:2", "buy:armour:2", "buy:weapon:abc", "buy:helmet:2"):
            await act(client, cheat)
        c = (await store.load(alice["id"])).climber
        assert (c.weapon, c.armour) == (3, 1)


@pytest.mark.asyncio
async def test_aegis_row_and_the_top_of_the_ladder(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], purse=10**7, level=12, armour=11, weapon=12)
        await act(client, "go:aegis")
        assert offered((await client.get(PAGE)).text) == ["buy:armour:12", "go:agora"]
        await act(client, "buy:armour:12")
        html = (await client.get(PAGE)).text
        assert "fits the Fragment of the Aegis" in html and text.BEST_THERE_IS in html
        assert offered(html) == ["go:agora"]

        await act(client, "go:agora")
        await act(client, "go:forge")
        assert text.BEST_THERE_IS in (await client.get(PAGE)).text


@pytest.mark.asyncio
async def test_the_dead_cannot_shop(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:forge")
        await tweak(alice["id"], purse=10**6, alive=False, hp=0)
        # The dead see no buttons, so replay the shop's form by hand.
        await act(client, "buy:weapon:2", turn=(await store.load(alice["id"])).turn)
    assert (await store.load(alice["id"])).climber.weapon == 1


# ---------------------------------------------------------------------------
# The Orchard Gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_orchard_gate(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:orchard")
        html = (await client.get(PAGE)).text
        assert "You have no seeds." in html and offered(html) == ["go:agora"]

        await tweak(alice["id"], seeds=3)
        html = (await client.get(PAGE)).text
        assert "You have 3 seeds." in html
        assert offered(html) == ["gift:strength", "gift:defence", "gift:vigour", "go:agora"]

        await act(client, "gift:vigour")
        c = (await store.load(alice["id"])).climber
        assert (c.seeds, c.hp_gift, c.hp) == (1, 5, 29)
        html = (await client.get(PAGE)).text
        assert "You have one seed." in html and ">29</span>/29" in html
        assert offered(html) == ["go:agora"]
        await act(client, "gift:strength")
        assert (await store.load(alice["id"])).climber.strength_gift == 0


# ---------------------------------------------------------------------------
# The Palaestra
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_myrto_turns_away_the_unready(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:palaestra")
        html = (await client.get(PAGE)).text
        assert "Agathe the Goatherd" in html and "You have 0 of the 244 XP" in html
        assert offered(html) == ["go:agora"]
        await act(client, "gate")
        assert (await store.load(alice["id"])).fight is None


@pytest.mark.asyncio
async def test_beating_the_gatekeeper(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], xp=300, hp=9, weapon=12, purse=77)
        await act(client, "go:palaestra")
        assert offered((await client.get(PAGE)).text) == ["gate", "go:agora"]

        dice(chance=[NO_AMBUSH])
        await act(client, "gate")
        player = await store.load(alice["id"])
        assert player.fight.foe.name == "Agathe the Goatherd" and player.climber.gate_tried_today
        assert player.climber.fights_left == 15              # a gate attempt is not a climb
        html = (await client.get(PAGE)).text
        assert "Agathe leans on her staff" in html
        assert offered(html) == ["fight:attack", "fight:fury"]          # no running

        rolls = dice(chance=[PLAIN], rolls=["max"])          # the Thunder-Scorched Spear settles it
        await act(client, "fight:attack")
        assert rolls.spent()                                 # no seed roll: gatekeepers carry nothing

        player = await store.load(alice["id"])
        c = player.climber
        assert (c.level, c.xp, c.rank, c.hp, c.purse) == (2, 0, 1, data.MAX_HP[1], 77)
        assert player.scene == "palaestra" and player.fight is None
        html = unescape((await client.get(PAGE)).text)
        assert "Mind the olives" in html and "The Olive Terraces, level 2" in html
        assert "Old Stavros" in html and text.GATE_TRIED in html
        assert offered(html) == ["go:agora"]


@pytest.mark.asyncio
async def test_losing_to_the_gatekeeper_costs_pride_only_and_once_a_day(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], xp=300, hp=2, purse=500)
        await act(client, "go:palaestra")
        dice(chance=[NO_AMBUSH])
        await act(client, "gate")
        dice(chance=[PLAIN], rolls=["min", "max"])
        await act(client, "fight:attack")

        player = await store.load(alice["id"])
        c = player.climber
        assert c.alive and c.hp == 1 and (c.level, c.xp, c.purse) == (1, 300, 500)
        html = unescape((await client.get(PAGE)).text)
        assert "Feet. You have two." in html and text.GATE_TRIED in html
        assert offered(html) == ["go:agora"]
        dice()
        await act(client, "gate")
        assert (await store.load(alice["id"])).fight is None

        fixed_day["today"] = DAY_ONE + timedelta(days=1)
        await client.get(PAGE)                               # dawn returns you to the Agora
        await act(client, "go:palaestra")
        assert offered((await client.get(PAGE)).text) == ["gate", "go:agora"]


@pytest.mark.asyncio
async def test_an_ambush_can_decide_a_gate_before_you_move(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], xp=300, hp=1)
        await act(client, "go:palaestra")
        dice(chance=[0.99], rolls=["max"])
        await act(client, "gate")
    player = await store.load(alice["id"])
    assert player.fight is None and player.scene == "palaestra"
    assert player.climber.alive and player.climber.hp == 1 and player.climber.level == 1


@pytest.mark.asyncio
async def test_at_the_garden_wall_there_is_nobody_left_to_face(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], level=12, xp=10**9)
        await act(client, "go:palaestra")
        html = (await client.get(PAGE)).text
    assert "not on my tablet" in html and offered(html) == ["go:agora"]


# ---------------------------------------------------------------------------
# The whole climb, using only what the screens offer
# ---------------------------------------------------------------------------

def _play_a_day(rng, player):
    """A sensible player who can see nothing but the screen in front of them."""
    def go(place):
        if player.scene != place:
            if player.scene != "agora":
                scenes.act(rng, player, "go:agora")
            if place != "agora":
                scenes.act(rng, player, f"go:{place}")

    def has(action):
        return any(choice.action == action for choice in scenes.screen(player).choices)

    def fight():
        if player.scene == "event":                          # cautious: always walk away
            scenes.act(rng, player, scenes.screen(player).choices[-1].action)
        while player.fight is not None:
            scenes.act(rng, player, "fight:attack")

    for _ in range(60):
        c = player.climber
        if not c.alive:
            return
        # Spend on gear, best first, drawing on the Vault.
        for shop in ("forge", "aegis"):
            kind = "weapon" if shop == "forge" else "armour"
            for tier, price, _ in reversed(rules.gear_on_offer(c, kind)):
                if price <= c.purse + c.vault:
                    if price > c.purse:
                        go("vault")
                        scenes.act(rng, player, "vault:withdraw", price - c.purse)
                    go(shop)
                    scenes.act(rng, player, f"buy:{kind}:{tier}")
                    break
        if c.hp < 0.5 * rules.max_hp(c):
            if c.vault:
                go("vault")
                scenes.act(rng, player, "vault:withdraw_all")
            go("hygieia")
            if has("heal:all"):
                scenes.act(rng, player, "heal:all")
        if c.purse:
            go("vault")
            scenes.act(rng, player, "vault:deposit_all")
        if c.hp >= 0.9 * rules.max_hp(c) and rules.can_face_gatekeeper(c):
            go("palaestra")
            scenes.act(rng, player, "gate")
            fight()
            continue
        if c.fights_left == 0 or c.hp < 0.3 * rules.max_hp(c):
            return
        go("slopes")
        scenes.act(rng, player, "seek")
        fight()


def test_the_garden_wall_can_be_reached_using_only_what_the_screens_offer():
    rng = Random(2026)
    player = store.Player(user_id=1, climber=rules.new_climber(data.SPEAR), last_day=DAY_ONE)
    levels_seen = {1}
    for day in range(1, 61):
        scenes.dawn(player, DAY_ONE + timedelta(days=day))
        _play_a_day(rng, player)
        levels_seen.add(player.climber.level)
        if player.climber.level == data.LEVELS:
            break
    assert player.climber.level == data.LEVELS, f"stuck at level {player.climber.level} after {day} days"
    assert levels_seen == set(range(1, 13))
    assert 20 <= day <= 45
    assert player.climber.rank >= 11                          # one for each gatekeeper, plus any lessons met on the way

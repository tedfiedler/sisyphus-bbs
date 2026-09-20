"""The Long Climb through its routes: create, fight, die, heal, bank, wake tomorrow."""

import re
from datetime import date, timedelta

import pytest

from lib import auth
from lib.climb import clock, data, rules, scenes, store, text
from lib.db import get_db
from lib.routes import climb_routes
from tests.helpers import anon_client, client_for
from tests.test_climb_rules import AMBUSH, NO_AMBUSH, PLAIN, STUMBLE, Dice

PAGE = "/games/climb"
DAY_ONE = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def fixed_day(monkeypatch):
    """The game's clock stands still unless a test moves it."""
    days = {"today": DAY_ONE}
    monkeypatch.setattr(clock, "today", lambda: days["today"])
    return days


@pytest.fixture
def dice(monkeypatch):
    """Replace the game's randomness. Tests script exactly the rolls they expect."""
    def load(chance=(), rolls=()):
        scripted = Dice(chance, rolls)
        monkeypatch.setattr(climb_routes, "rng", scripted)
        return scripted
    load()          # by default any roll at all is an error
    return load


@pytest.fixture
async def alice():
    await auth.register_user("admin", "password123")
    return await auth.register_user("alice", "password123")


async def act(client, action, amount=None, turn=None):
    """Submit a choice the way the page's form does."""
    if turn is None:
        turn = int(re.search(r'name="turn" value="(\d+)"', (await client.get(PAGE)).text).group(1))
    fields = {"action": action, "turn": turn}
    if amount is not None:
        fields["amount"] = amount
    return await client.post(f"{PAGE}/act", data=fields)


async def begin(client, calling=data.SPEAR):
    return await client.post(f"{PAGE}/act", data={"action": f"begin:{calling}", "turn": 0})


async def tweak(user_id, **attrs):
    """Reach into a saved climber, as a test may and a player may not."""
    player = await store.load(user_id)
    for key, value in attrs.items():
        setattr(player.climber, key, value)
    assert await store.save(player)


def offered(html):
    return re.findall(r'name="action" value="([^"]+)"', html)


# ---------------------------------------------------------------------------
# Arriving
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_requires_login_and_is_listed_with_the_games(alice):
    async with anon_client() as client:
        resp = await client.get(PAGE)
        assert resp.status_code == 302 and resp.headers["location"] == "/"
    async with await client_for(alice["id"]) as client:
        assert f'href="{PAGE}"' in (await client.get("/games")).text


@pytest.mark.asyncio
async def test_a_newcomer_chooses_a_calling(alice, dice):
    async with await client_for(alice["id"]) as client:
        html = (await client.get(PAGE)).text
        assert offered(html) == ["begin:spear", "begin:torch", "begin:sandal"]
        assert data.CREDIT.replace("'", "&#39;") in html
        assert await store.load(alice["id"]) is None

        for nonsense in ("begin:bard", "seek", "go:slopes", ""):
            await client.post(f"{PAGE}/act", data={"action": nonsense, "turn": 0})
        assert await store.load(alice["id"]) is None

        resp = await begin(client, data.TORCH)
        assert resp.status_code == 303 and resp.headers["location"] == PAGE
        player = await store.load(alice["id"])
        assert player.climber.calling == data.TORCH and player.scene == "agora"
        assert player.last_day == DAY_ONE

        html = (await client.get(PAGE)).text
        assert text.BEGUN["torch"] in html
        assert offered(html) == ["go:slopes", "go:hygieia", "go:vault"]

        # Asking again does not replace the climber you have.
        await begin(client, data.SPEAR)
        assert (await store.load(alice["id"])).climber.calling == data.TORCH


@pytest.mark.asyncio
async def test_status_line(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        html = (await client.get(PAGE)).text
    for fragment in (">24</span>/24", ">60</span>", "(Vault 0)", "0/244", "Olive Branch, Wool Cloak", "Climber of The Spear"):
        assert fragment in html, fragment


@pytest.mark.asyncio
async def test_post_needs_the_csrf_token(alice, dice):
    async with await client_for(alice["id"], csrf=False) as client:
        resp = await client.post(f"{PAGE}/act", data={"action": "begin:spear", "turn": 0})
    assert resp.status_code == 403 and await store.load(alice["id"]) is None


# ---------------------------------------------------------------------------
# The Slopes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_fight_won(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:slopes")
        assert offered((await client.get(PAGE)).text) == ["seek", "go:agora"]

        dice(chance=[NO_AMBUSH], rolls=[1])                  # rank 1: an Irritable Goat
        await act(client, "seek")
        player = await store.load(alice["id"])
        assert player.scene == "fight" and player.fight.foe.name == "Irritable Goat"
        assert player.climber.fights_left == 14
        html = (await client.get(PAGE)).text
        assert "Irritable Goat" in html and offered(html) == ["fight:attack", "fight:fury", "fight:run"]

        goat = rules.creature(1, 1)
        rolls = dice(chance=[PLAIN, 0.99], rolls=["max"])    # one full blow; no seed
        await act(client, "fight:attack")
        assert rolls.spent()

        player = await store.load(alice["id"])
        assert player.fight is None and player.scene == "slopes"
        assert player.climber.xp == goat.xp and player.climber.purse == 60 + goat.drachmae
        html = (await client.get(PAGE)).text
        assert "Irritable Goat is beaten." in html
        assert f"You find {goat.drachmae} drachmae" in html


@pytest.mark.asyncio
async def test_looking_at_the_page_never_rolls_dice(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:slopes")
        dice(chance=[NO_AMBUSH], rolls=[8])
        await act(client, "seek")
        dice()                                               # any roll now raises
        before = await store.load(alice["id"])
        for _ in range(3):
            assert (await client.get(PAGE)).status_code == 200
        after = await store.load(alice["id"])
    assert (after.turn, after.fight.foe_hp, after.climber.hp) == (before.turn, before.fight.foe_hp, before.climber.hp)


@pytest.mark.asyncio
async def test_a_repeated_or_stale_form_does_nothing(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:slopes")
        turn = (await store.load(alice["id"])).turn

        dice(chance=[NO_AMBUSH], rolls=[1])
        await act(client, "seek", turn=turn)
        dice()                                               # a second roll would raise
        await act(client, "seek", turn=turn)                 # double-click
        await act(client, "fight:attack", turn=turn)         # other tab, old screen
        await act(client, "fight:attack", turn=turn + 50)    # nonsense

    player = await store.load(alice["id"])
    assert player.climber.fights_left == 14 and player.fight.foe_hp == player.fight.foe.hp
    assert player.turn == turn + 1


@pytest.mark.asyncio
async def test_only_what_the_screen_offers_is_accepted(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        for cheat in ("fight:attack", "seek", "heal:all", "vault:withdraw_all", "begin:torch", "go:nowhere", "go:fight"):
            await act(client, cheat)
        player = await store.load(alice["id"])
        assert player.scene == "agora" and player.fight is None and player.climber.fights_left == 15

        await act(client, "go:slopes")
        dice(chance=[NO_AMBUSH], rolls=[1])
        await act(client, "seek")
        dice()
        for cheat in ("go:agora", "go:hygieia", "heal:all", "seek", "vault:deposit_all", "fight:flame", "fight:mend"):
            await act(client, cheat)
        assert (await store.load(alice["id"])).scene == "fight"


@pytest.mark.asyncio
async def test_bad_numbers_are_rejected_before_the_game_sees_them(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:vault")
        turn = (await store.load(alice["id"])).turn
        for bad in ("-5", "abc", "1.5", str(10**13)):
            resp = await client.post(f"{PAGE}/act", data={"action": "vault:deposit", "turn": turn, "amount": bad})
            assert resp.status_code == 422, bad
        resp = await client.post(f"{PAGE}/act", data={"action": "x" * 41, "turn": turn})
        assert resp.status_code == 422
    assert (await store.load(alice["id"])).climber.purse == 60


@pytest.mark.asyncio
async def test_the_days_climbing_runs_out(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], fights_left=1)
        await act(client, "go:slopes")
        dice(chance=[NO_AMBUSH], rolls=[1])
        await act(client, "seek")
        dice(chance=[STUMBLE * 0, ], rolls=[])               # run: escape succeeds on a low roll
        await act(client, "fight:run")

        html = (await client.get(PAGE)).text
        assert text.SLOPES_SPENT in html and offered(html) == ["go:agora"]
        dice()
        await act(client, "seek")
        assert (await store.load(alice["id"])).fight is None


# ---------------------------------------------------------------------------
# Death and dawn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_death_then_dawn(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:vault")
        await act(client, "vault:deposit", amount=45)
        await act(client, "go:agora")
        await tweak(alice["id"], hp=1, xp=200)
        await act(client, "go:slopes")

        dice(chance=[AMBUSH], rolls=[8, "max"])              # the Tax Collector strikes first
        await act(client, "seek")

        player = await store.load(alice["id"])
        c = player.climber
        assert not c.alive and c.hp == 0 and player.fight is None
        assert (c.purse, c.vault, c.xp) == (0, 45, 180)
        html = (await client.get(PAGE)).text
        assert text.AMBUSH in html and "15 drachmae" in html and "Dead until dawn" in html
        assert offered(html) == []

        dice()
        for action in ("go:slopes", "seek", "go:hygieia", "heal:all"):
            await act(client, action, turn=player.turn)
        assert not (await store.load(alice["id"])).climber.alive

        fixed_day["today"] = DAY_ONE + timedelta(days=1)
        html = (await client.get(PAGE)).text
        assert text.DAWN_AFTER_DEATH in html and "The Agora" in html
        c = (await store.load(alice["id"])).climber
        assert c.alive and c.hp == 24 and c.fights_left == 15 and c.vault == 45

        # Dawn happens once: another look changes nothing.
        turn = (await store.load(alice["id"])).turn
        await client.get(PAGE)
        assert (await store.load(alice["id"])).turn == turn


@pytest.mark.asyncio
async def test_dawn_restores_the_living_and_ends_a_fight_left_overnight(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:slopes")
        dice(chance=[NO_AMBUSH], rolls=[8])
        await act(client, "seek")
        await tweak(alice["id"], hp=5, fights_left=3, skill_left=0)
        stale_turn = (await store.load(alice["id"])).turn

        fixed_day["today"] = DAY_ONE + timedelta(days=3)
        dice()                                               # yesterday's attack must not be played today
        await act(client, "fight:attack", turn=stale_turn)

        player = await store.load(alice["id"])
        assert player.fight is None and player.scene == "agora" and player.last_day == fixed_day["today"]
        assert (player.climber.hp, player.climber.fights_left, player.climber.skill_left) == (24, 15, 1)
        html = (await client.get(PAGE)).text
        assert text.DAWN in html and text.DAWN_MID_FIGHT in html


# ---------------------------------------------------------------------------
# Town
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hygieia(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:hygieia")
        html = (await client.get(PAGE)).text
        assert text.HYGIEIA_WHOLE.replace('"', "&#34;") in html and offered(html) == ["go:agora"]

        await tweak(alice["id"], hp=4)
        html = (await client.get(PAGE)).text
        assert offered(html) == ["heal:all", "heal:some", "go:agora"]
        assert 'max="20"' in html

        await act(client, "heal:some", amount=5)
        c = (await store.load(alice["id"])).climber
        assert c.hp == 9 and c.purse == 60 - rules.heal_cost(c, 5)

        await act(client, "heal:some", amount=500)           # more than is missing
        assert (await store.load(alice["id"])).climber.hp == 9
        assert text.HEAL_REFUSED in (await client.get(PAGE)).text

        await act(client, "heal:all")
        c = (await store.load(alice["id"])).climber
        assert c.hp == 24

        await tweak(alice["id"], hp=1, purse=0)
        assert offered((await client.get(PAGE)).text) == ["go:agora"]


@pytest.mark.asyncio
async def test_heal_all_you_can_afford(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], hp=1, purse=10)
        await act(client, "go:hygieia")
        assert "all you can afford (5)" in (await client.get(PAGE)).text
        await act(client, "heal:all")
    c = (await store.load(alice["id"])).climber
    assert c.hp == 6 and c.purse == 10 - rules.heal_cost(c, 5)


@pytest.mark.asyncio
async def test_the_vault(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:vault")
        assert offered((await client.get(PAGE)).text) == ["vault:deposit_all", "vault:deposit", "go:agora"]

        await act(client, "vault:deposit", amount=25)
        await act(client, "vault:deposit", amount=36)        # one more than is left
        html = (await client.get(PAGE)).text
        assert text.VAULT_REFUSED in html
        assert offered(html) == ["vault:deposit_all", "vault:deposit", "vault:withdraw_all", "vault:withdraw", "go:agora"]

        await act(client, "vault:deposit_all")
        c = (await store.load(alice["id"])).climber
        assert (c.purse, c.vault) == (0, 60)

        await act(client, "vault:withdraw", amount=0)
        await act(client, "vault:withdraw", amount=10)
        await act(client, "vault:withdraw_all")
        c = (await store.load(alice["id"])).climber
        assert (c.purse, c.vault) == (60, 0)


# ---------------------------------------------------------------------------
# Storage, markup, and the rest of the BBS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_fight_survives_the_round_trip_to_the_database(alice):
    climber = rules.new_climber(data.SANDAL)
    await store.create(alice["id"], climber, DAY_ONE, ["hello"])
    player = await store.load(alice["id"])
    player.fight = rules.Fight(
        foe=rules.creature(3, 5), foe_hp=17, can_run=False, lethal=False, scorched=True, picked=9,
        events=[("you_hit", 12), ("foe_hits", 3)],
    )
    player.scene, player.notice = "fight", ["one", "two"]
    assert await store.save(player)

    again = await store.load(alice["id"])
    assert again.fight == player.fight and again.fight.outcome is rules.Outcome.ONGOING
    assert again.notice == ["one", "two"] and again.turn == 1 and again.climber == climber

    again.turn = 0                                           # someone else got there first
    assert not await store.save(again)


@pytest.mark.asyncio
async def test_saved_climbers_from_an_older_or_newer_version_still_load(alice):
    await store.create(alice["id"], rules.new_climber(data.SPEAR), DAY_ONE, [])
    db = await get_db()
    await db.execute(
        "UPDATE climb_players SET climber = json_set(json_remove(climber, '$.charm'), '$.pet_owl', 1)"
    )
    await db.commit()
    climber = (await store.load(alice["id"])).climber
    assert climber.charm == 0 and not hasattr(climber, "pet_owl")


@pytest.mark.asyncio
async def test_every_choice_is_a_real_button_with_a_hotkey(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:vault")
        html = (await client.get(PAGE)).text
    forms = re.findall(r'<form method="post" action="/games/climb/act".*?</form>', html, re.DOTALL)
    assert len(forms) == 3
    for form in forms:
        assert 'name="csrf_token"' in form and 'name="turn"' in form and "<button" in form
        assert len(re.findall(r'data-key="[a-z]"', form)) == 1
    assert 'src="/static/js/climb.js' in html
    keys = re.findall(r'data-key="([a-z])"', html)
    assert len(keys) == len(set(keys))


@pytest.mark.asyncio
async def test_every_screen_has_distinct_hotkeys():
    players = []
    for calling in data.CALLINGS:
        for scene in ("agora", "slopes", "hygieia", "vault", "fight"):
            c = rules.new_climber(calling)
            c.rank, c.skill_left, c.hp, c.vault = 40, 5, 3, 10
            fight = rules.Fight(foe=rules.creature(1, 1), foe_hp=5) if scene == "fight" else None
            players.append(store.Player(user_id=1, climber=c, scene=scene, fight=fight))
    for player in players + [None]:
        choices = (scenes.screen(player) if player else scenes.welcome()).choices
        keys = [choice.key for choice in choices]
        assert len(keys) == len(set(keys)), (player and player.scene, keys)
        for choice in choices:
            assert f"({choice.key.upper()})" in choice.label or f"({choice.key})" in choice.label, choice.label


@pytest.mark.asyncio
async def test_deleting_a_user_removes_their_climber(alice, dice):
    admin = await auth.get_user(1)
    async with await client_for(alice["id"]) as client:
        await begin(client)
    await auth.delete_user(alice["id"], reassign_channels_to=admin["id"])
    assert await store.load(alice["id"]) is None
    assert await auth.get_user(alice["id"]) is None


@pytest.mark.asyncio
async def test_climbers_are_separate(alice, dice):
    bob = await auth.register_user("bob", "password123")
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await begin(a, data.SPEAR)
        assert offered((await b.get(PAGE)).text)[0] == "begin:spear"
        await begin(b, data.SANDAL)
        await act(a, "go:vault")
        await act(a, "vault:deposit_all")
    assert (await store.load(bob["id"])).climber.purse == 60
    assert (await store.load(alice["id"])).climber.vault == 60

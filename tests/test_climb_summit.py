"""The Long Climb, step 4: Ladon, the ascent, the Stele, and scores into the BBS."""

from datetime import timedelta
from html import unescape
from random import Random

import pytest

from lib import auth, mille
from lib.climb import data, rules, scenes, store, text
from lib.db import get_db
from tests.helpers import client_for
from tests.test_climb_routes import DAY_ONE, PAGE, act, begin, offered, tweak
from tests.test_climb_routes import alice, dice, fixed_day  # noqa: F401  (fixtures)
from tests.test_climb_rules import NO_AMBUSH, PLAIN, climber
from tests.test_climb_town import _play_a_day


async def _scores(user_id):
    db = await get_db()
    cursor = await db.execute(
        "SELECT game, score, opponent, won FROM game_scores WHERE user_id = ? ORDER BY id", (user_id,)
    )
    return [tuple(row) for row in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def test_any_ascent_outranks_any_level():
    assert rules.renown(climber(level=12)) < rules.renown(climber(level=1, ascents=1))
    assert rules.renown(climber(level=5)) < rules.renown(climber(level=6))
    assert rules.renown(climber(level=3, ascents=2)) < rules.renown(climber(level=4, ascents=2))


def test_heads_are_counted_down_from_a_hundred():
    boss = rules.ladon()
    count = lambda hp: rules.heads_left(rules.Fight(foe=boss, foe_hp=hp))
    assert count(boss.hp) == 100 and count(boss.hp // 2) == 50
    assert count(1) == 1 and count(0) == 0
    assert all(count(hp) >= count(hp - 1) for hp in range(1, boss.hp, 97))


# ---------------------------------------------------------------------------
# The Garden
# ---------------------------------------------------------------------------

async def _at_the_wall(client, user_id, **extra):
    await begin(client)
    await tweak(user_id, **{"level": 12, "weapon": 12, "armour": 12, "purse": 4000, "vault": 900_000,
                            "xp": 5000, "rank": 11, "charm": 6, "seeds": 1, "strength_gift": 4, **extra})
    await act(client, "go:slopes")


@pytest.mark.asyncio
async def test_the_garden_is_only_offered_at_the_wall(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], level=11)
        await act(client, "go:slopes")
        assert offered((await client.get(PAGE)).text) == ["seek", "go:agora"]
        await act(client, "garden")
        assert (await store.load(alice["id"])).fight is None

        await tweak(alice["id"], level=12)
        assert offered((await client.get(PAGE)).text) == ["seek", "garden", "go:agora"]
        await tweak(alice["id"], fights_left=0)
        assert offered((await client.get(PAGE)).text) == ["go:agora"]


@pytest.mark.asyncio
async def test_killing_ladon(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await _at_the_wall(client, alice["id"])
        dice(chance=[NO_AMBUSH])
        await act(client, "garden")

        player = await store.load(alice["id"])
        assert player.fight.foe.name == "Ladon" and player.climber.fights_left == 14
        html = (await client.get(PAGE)).text
        assert "100 of a hundred heads" in html and "A hundred heads turn" in html
        assert offered(html) == ["fight:attack", "fight:fury"]           # nowhere to run

        # Skip to the last head rather than scripting thirty rounds.
        player.fight.foe_hp = 1
        assert await store.save(player)
        assert text.LADON_ONE_HEAD in (await client.get(PAGE)).text
        rolls = dice(chance=[PLAIN], rolls=["min"])
        await act(client, "fight:attack")
        assert rolls.spent()

        player = await store.load(alice["id"])
        c = player.climber
        assert (c.ascents, c.level, c.xp, c.weapon, c.armour) == (1, 1, 0, 1, 1)
        assert (c.purse, c.vault) == (60, 0)                             # the Vault too
        assert (c.rank, c.charm, c.seeds, c.strength_gift, c.calling) == (11, 6, 1, 4, data.SPEAR)
        assert c.hp == rules.max_hp(c) and c.alive
        assert c.fights_left == 0 and c.duels_left == 0                  # the day is done
        assert player.scene == "summit" and player.fight is None

        html = unescape((await client.get(PAGE)).text)
        assert "You find that you are smiling." in html
        assert "ascent number 1" in html and "call you Apple-Bearer" in html
        assert "Apple-Bearer of The Spear" in html
        assert offered(html) == ["go:agora"]

        assert await _scores(alice["id"]) == [("climb", rules.renown(c), "Ladon", 1)]
        assert (await auth.check_file_access(alice))["has_game"] is True

        await act(client, "go:agora")
        await act(client, "go:slopes")
        assert offered((await client.get(PAGE)).text) == ["go:agora"]    # nothing left today

        fixed_day["today"] = DAY_ONE + timedelta(days=1)
        await client.get(PAGE)
        c = (await store.load(alice["id"])).climber
        assert c.fights_left == 15 and c.ascents == 1
        # The mountain remembers: its creatures are a little tougher now. (Three
        # per cent of a Foothills goat rounds to nothing; look higher up.)
        assert rules.creature(6, 8, c.ascents).hp > rules.creature(6, 8, 0).hp


@pytest.mark.asyncio
async def test_ladon_kills_for_real_and_the_garden_is_once_a_day(alice, dice):
    async with await client_for(alice["id"]) as client:
        await _at_the_wall(client, alice["id"], hp=5)
        dice(chance=[NO_AMBUSH])
        await act(client, "garden")
        dice(chance=[PLAIN], rolls=["min", "max"])
        await act(client, "fight:attack")

        player = await store.load(alice["id"])
        c = player.climber
        assert not c.alive and (c.purse, c.vault, c.ascents, c.level) == (0, 900_000, 0, 12)
        assert c.xp == 4500
        html = (await client.get(PAGE)).text
        assert text.LADON_WINS in html
        assert await _scores(alice["id"]) == []

    # Alive again the same day (as only a test can arrange): no second visit.
    await tweak(alice["id"], alive=True, hp=500)
    async with await client_for(alice["id"]) as client:
        player = await store.load(alice["id"])
        player.scene = "slopes"
        await store.save(player)
        html = (await client.get(PAGE)).text
        assert text.GARDEN_TRIED in html and "garden" not in offered(html)


@pytest.mark.asyncio
async def test_a_level_gained_is_a_score_and_a_replayed_form_is_not_a_second_one(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        assert (await auth.check_file_access(alice))["has_game"] is False
        await tweak(alice["id"], xp=300, weapon=12)
        await act(client, "go:palaestra")
        dice(chance=[NO_AMBUSH])
        await act(client, "gate")
        turn = (await store.load(alice["id"])).turn
        dice(chance=[PLAIN], rolls=["max"])
        await act(client, "fight:attack", turn=turn)
        dice()
        await act(client, "fight:attack", turn=turn)                     # the double-click

    c = (await store.load(alice["id"])).climber
    assert c.level == 2
    assert await _scores(alice["id"]) == [("climb", rules.renown(c), "Agathe the Goatherd", 0)]
    assert (await auth.check_file_access(alice))["has_game"] is True


@pytest.mark.asyncio
async def test_climb_scores_stay_out_of_the_mille_bornes_table(alice, dice):
    await store.record_score(alice["id"], 99_999, "Ladon", True)
    assert await mille.get_high_scores() == []


# ---------------------------------------------------------------------------
# The Stele
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_stele_ranks_active_climbers(alice, dice):
    names = {}
    for name in ("bob", "carol", "dave", "erin"):
        names[name] = await auth.register_user(name, "password123")
    make = {
        "bob": dict(level=9, xp=10), "carol": dict(level=2, ascents=1),
        "dave": dict(level=9, xp=500, alive=False), "erin": dict(level=12, ascents=3),
    }
    for name, attrs in make.items():
        c = rules.new_climber(data.TORCH)
        for key, value in attrs.items():
            setattr(c, key, value)
        await store.create(names[name]["id"], c, DAY_ONE, [])
    db = await get_db()
    await db.execute("UPDATE climb_players SET last_seen = datetime('now', '-15 days') WHERE user_id = ?",
                     (names["erin"]["id"],))
    await db.commit()

    async with await client_for(alice["id"]) as client:
        await begin(client, data.SANDAL)
        await act(client, "go:stele")
        html = unescape((await client.get(PAGE)).text)

    rows = [r for r in html.split("<tr")[2:]]
    order = [next(n for n in ("alice", "bob", "carol", "dave") if f"<td>{n} " in row) for row in rows]
    assert order == ["carol", "dave", "bob", "alice"]                    # ascents, then level, then XP
    assert "erin" not in html                                            # away a fortnight
    assert "Apple-Bearer" in rows[0] and "The Olive Terraces" in rows[0]
    assert "dead until dawn" in rows[1] and "dead until dawn" not in rows[2]
    assert 'class="c-sky"' in rows[3] and "The Sandal" in rows[3]
    assert offered(html) == ["go:agora"]


# ---------------------------------------------------------------------------
# The whole loop
# ---------------------------------------------------------------------------

def test_a_full_ascent_and_the_start_of_the_next_using_only_the_screens():
    rng = Random(7)
    player = store.Player(user_id=1, climber=rules.new_climber(data.TORCH), last_day=DAY_ONE)
    heard = []

    def day_with_garden():
        c = player.climber
        # The Garden first, while fresh: it costs a climb, and a day's fighting leaves none.
        if c.level == data.LEVELS and c.weapon == c.armour == data.LEVELS and rules.can_seek_ladon(c):
            if player.scene != "slopes":
                if player.scene != "agora":
                    scenes.act(rng, player, "go:agora")
                scenes.act(rng, player, "go:slopes")
            scenes.act(rng, player, "garden")
            while player.fight is not None:
                scenes.act(rng, player, "fight:attack")
                heard.extend(player.happenings)
        if not player.climber.ascents:
            _play_a_day(rng, player)

    for day in range(1, 91):
        scenes.dawn(player, DAY_ONE + timedelta(days=day))
        day_with_garden()
        if player.climber.ascents:
            break
    c = player.climber
    assert c.ascents == 1, f"no ascent in {day} days (level {c.level})"
    assert 25 <= day <= 70
    assert (scenes.ASCENDED, "Ladon") in heard
    assert (c.level, c.weapon, c.vault, c.rank, c.calling) == (1, 1, 0, 11, data.TORCH)
    assert player.scene == "summit" and rules.title(c.ascents) == "Apple-Bearer"

    # And the next morning the climb simply begins again.
    scenes.dawn(player, DAY_ONE + timedelta(days=day + 1))
    _play_a_day(rng, player)
    assert player.climber.xp > 0 or not player.climber.alive

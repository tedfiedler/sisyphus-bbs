"""The Long Climb, step 5a: the Lethe House, the Herald, and the sysop's tools."""

from datetime import timedelta
from html import unescape

import pytest

from lib import auth
from lib.climb import data, rules, store, text
from lib.climb.rules import Outcome
from lib.db import get_db
from tests.helpers import client_for
from tests.test_climb_routes import DAY_ONE, PAGE, act, begin, offered, tweak
from tests.test_climb_routes import alice, dice, fixed_day  # noqa: F401  (fixtures)
from tests.test_climb_rules import NO_AMBUSH, PLAIN, Dice, climber, dummy

# A value of random() that selects each song, given the shares in data.SONGS.
PICK = {"road": 0.0, "bronze": 0.20, "ferryman": 0.40, "goatherd": 0.60,
        "sisters": 0.75, "stone": 0.86, "eurydice": 0.93, "string": 0.99}


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def test_the_picks_above_really_select_each_song():
    for song, pick in PICK.items():
        assert rules.apply_song(Dice(chance=[pick]), climber())[0] == song


def test_what_each_song_does():
    c = climber(level=5, hp=10)
    assert rules.apply_song(Dice(chance=[PICK["road"]]), c) == ("road", 3) and c.fights_left == 18

    c = climber(level=5, hp=10)
    boost = round(data.MAX_HP[4] * 0.10)
    assert rules.apply_song(Dice(chance=[PICK["bronze"]]), c) == ("bronze", boost)
    assert rules.max_hp(c) == data.MAX_HP[4] + boost == c.hp

    c = climber(level=5, purse=7)
    _, purse = rules.apply_song(Dice(chance=[PICK["ferryman"]]), c)
    assert purse == round(data.REF_DRACHMAE[4] * 3) and c.purse == 7 + purse

    c = climber(level=5, xp=1)
    assert rules.apply_song(Dice(chance=[PICK["goatherd"]]), c) == ("goatherd", data.REF_XP[4]) and c.xp == 1 + data.REF_XP[4]

    c = climber(rank=0)
    rules.apply_song(Dice(chance=[PICK["sisters"]]), c)
    assert c.skill_left == 2

    c = climber(charm=3)
    rules.apply_song(Dice(chance=[PICK["eurydice"]]), c)
    assert c.charm == 4

    c = climber()
    before = (c.hp, c.purse, c.xp, c.fights_left, c.charm, c.skill_left)
    assert rules.apply_song(Dice(chance=[PICK["string"]]), c) == ("string", 0)
    assert before == (c.hp, c.purse, c.xp, c.fights_left, c.charm, c.skill_left) and not c.mercy


def test_one_song_a_day_and_none_for_the_dead():
    c = climber()
    rules.apply_song(Dice(chance=[0.0]), c)
    with pytest.raises(ValueError):
        rules.apply_song(Dice(chance=[0.0]), c)
    with pytest.raises(ValueError):
        rules.apply_song(Dice(chance=[0.0]), climber(alive=False))
    rules.apply_dawn(c)
    rules.apply_song(Dice(chance=[0.0]), c)


def test_dawn_ends_the_days_blessings():
    c = climber(level=5, sung_today=True, hp_boost=10, mercy=True, room=True, wall_today=4)
    rules.apply_dawn(c)
    assert (c.sung_today, c.hp_boost, c.mercy, c.room, c.wall_today) == (False, 0, False, False, 0)
    assert c.hp == data.MAX_HP[4]


def test_a_stone_remembers():
    c = climber(hp=3, mercy=True)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(attack=500))
    assert fight.mercy and not c.mercy                        # spent on this fight
    outcome = rules.take_turn(Dice(chance=[PLAIN], rolls=["min", "max"]), c, fight, "attack")
    assert outcome is Outcome.FLED and c.hp == 1 and c.alive
    assert fight.events[-1] == ("stone_saves", 0)

    # A gatekeeper kills nobody, so the blessing waits for a fight that would.
    c = climber(mercy=True)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(kind=rules.GATEKEEPER))
    assert c.mercy and not fight.mercy
    # It works in the garden, too: a free look at Ladon, not a free win.
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, rules.ladon())
    assert fight.mercy and not c.mercy


def test_rooms_and_wine():
    c = climber(level=4, purse=10_000, hp=10)
    price = rules.room_price(c)
    assert price == round(data.REF_DRACHMAE[3] * 2)
    assert rules.apply_room(c) == price and c.room and c.purse == 10_000 - price
    with pytest.raises(ValueError):
        rules.apply_room(c)                                   # already have one
    with pytest.raises(ValueError):
        rules.apply_room(climber(purse=0))

    cost, healed = rules.apply_wine(c)
    assert cost == rules.wine_price(c) and healed == round(rules.max_hp(c) * 0.15) and c.hp == 10 + healed
    c.hp = rules.max_hp(c) - 1
    assert rules.apply_wine(c)[1] == 1                        # never past full
    with pytest.raises(ValueError):
        rules.apply_wine(climber(purse=0))


@pytest.mark.parametrize("raw, clean", [
    ("  hello   there  ", "hello there"),
    ("line\none\ttwo", "line one two"),
    ("bell\x07 and escape\x1b[31m red", "bell and escape[31m red"),
    ("x" * 120, "x" * 120),
])
def test_wall_lines_are_tidied(raw, clean):
    assert rules.clean_wall_line(raw) == clean


@pytest.mark.parametrize("bad", ["", "   ", "\n\t", "x" * 121])
def test_wall_lines_have_limits(bad):
    with pytest.raises(ValueError):
        rules.clean_wall_line(bad)


def test_every_song_has_a_lyric_and_a_blessing():
    assert set(text.SONGS) == {name for name, _ in data.SONGS}
    for name, (title, lyric, blessing) in text.SONGS.items():
        assert title and lyric and "{n}" in blessing or name in ("stone", "string"), name
        blessing.format(n=3)


# ---------------------------------------------------------------------------
# The Lethe House, through the routes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orpheus_sings_once_a_day(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:lethe")
        assert offered((await client.get(PAGE)).text) == ["song", "go:wall", "room", "wine", "go:agora"]

        dice(chance=[PICK["road"]])
        await act(client, "song")
        html = unescape((await client.get(PAGE)).text)
        assert "The Road Goes Up" in html and "remind them they are not alone." in html
        assert "You can climb 3 more times today." in html
        assert (await store.load(alice["id"])).climber.fights_left == 18
        assert "song" not in offered(html) and text.ORPHEUS_DONE in html
        dice()
        await act(client, "song")

        fixed_day["today"] = DAY_ONE + timedelta(days=1)
        await client.get(PAGE)
        await act(client, "go:lethe")
        assert "song" in offered((await client.get(PAGE)).text)


@pytest.mark.asyncio
async def test_a_room_and_a_cup_of_wine(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], hp=5)
        await act(client, "go:lethe")
        dice(rolls=[2])                                       # which piece of gossip
        await act(client, "wine")
        c = (await store.load(alice["id"])).climber
        assert c.purse == 60 - 11 and c.hp == 5 + round(24 * 0.15)
        html = unescape((await client.get(PAGE)).text)
        assert "Nikandros pours." in html and text.GOSSIP[2] in html

        await act(client, "room")
        c = (await store.load(alice["id"])).climber
        assert c.room and c.purse == 60 - 11 - 44
        html = unescape((await client.get(PAGE)).text)
        assert "wooden fish" in html and text.LETHE_ROOMED in html
        assert offered(html) == ["song", "go:wall", "go:agora"]           # no second room; too poor for wine


# ---------------------------------------------------------------------------
# The wall
# ---------------------------------------------------------------------------

async def write(client, words):
    turn = (await store.load((await _me(client)))).turn
    return await client.post(f"{PAGE}/act", data={"action": "wall:write", "turn": turn, "words": words})


async def _me(client):
    token = client.cookies["session_token"]
    return (await auth.get_user_by_token(token))["id"]


@pytest.mark.asyncio
async def test_the_wall_is_shared_escaped_and_limited(alice, dice):
    bob = await auth.register_user("bob", "password123")
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await begin(a)
        await begin(b)
        for client in (a, b):
            await act(client, "go:lethe")
            await act(client, "go:wall")
        assert text.WALL_EMPTY in (await a.get(PAGE)).text

        await write(a, "  Agathe   hits  hard.  ")
        await write(a, "<script>alert(1)</script> & co")
        html = (await b.get(PAGE)).text
        assert "Agathe hits hard." in html and ">alice</span>" in html
        assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co" in html

        for refused in ("see http://evil.example", "www.evil.example now", "   ", "y" * 121):
            await write(a, refused)
            assert text.WALL_REFUSED in unescape((await a.get(PAGE)).text)
        assert (await write(a, "z" * 401)).status_code == 422
        assert len(await store.wall_lines()) == 2

        for i in range(3):
            await write(a, f"line {i}")
        html = unescape((await a.get(PAGE)).text)
        assert "wall:write" not in offered(html)                          # five today
        await write(a, "a sixth")
        assert len(await store.wall_lines()) == 5
        assert "wall:write" in offered((await b.get(PAGE)).text)


@pytest.mark.asyncio
async def test_the_wall_shows_the_latest_fifteen_oldest_first(alice, dice):
    for i in range(18):
        await store.add_wall_line(alice["id"], f"note {i}")
    lines = [entry["line"] for entry in await store.wall_lines()]
    assert lines == [f"note {i}" for i in range(3, 18)]


@pytest.mark.asyncio
async def test_sysop_can_remove_a_line_and_reset_a_climber_and_nobody_else_can(alice, dice):
    admin = await auth.get_user(1)
    bob = await auth.register_user("bob", "password123")
    await store.add_wall_line(alice["id"], "something regrettable")
    line_id = (await store.wall_lines())[0]["id"]
    await store.create(alice["id"], rules.new_climber(data.SPEAR), DAY_ONE, [])

    async with await client_for(bob["id"]) as b:
        assert (await b.post(f"{PAGE}/admin/wall/{line_id}/delete")).status_code == 403
        assert (await b.post(f"{PAGE}/admin/reset/{alice['id']}")).status_code == 403
    assert len(await store.wall_lines()) == 1 and await store.load(alice["id"]) is not None

    async with await client_for(admin["id"]) as client:
        await begin(client)
        await act(client, "go:lethe")
        await act(client, "go:wall")
        assert f'action="{PAGE}/admin/wall/{line_id}/delete"' in (await client.get(PAGE)).text
        await act(client, "go:lethe")
        await act(client, "go:agora")
        await act(client, "go:stele")
        html = unescape((await client.get(PAGE)).text)
        assert f'action="{PAGE}/admin/reset/{alice["id"]}"' in html
        assert "data-confirm=\"Delete alice's climber?" in html

        assert (await client.post(f"{PAGE}/admin/wall/{line_id}/delete")).status_code == 303
        assert (await client.post(f"{PAGE}/admin/reset/{alice['id']}")).status_code == 303
    assert await store.wall_lines() == [] and await store.load(alice["id"]) is None

    async with await client_for(alice["id"]) as a:
        html = (await a.get(PAGE)).text
        assert offered(html)[0] == "begin:spear" and "/admin/" not in html


# ---------------------------------------------------------------------------
# The Herald
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_herald_reports_what_climbers_do(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], xp=300, weapon=12)
        await act(client, "go:palaestra")
        dice(chance=[NO_AMBUSH])
        await act(client, "gate")
        dice(chance=[PLAIN], rolls=["max"])
        await act(client, "fight:attack")

        await tweak(alice["id"], hp=1, weapon=1)
        await act(client, "go:agora")
        await act(client, "go:slopes")
        dice(chance=[0.99, 0.99], rolls=[8, "max"])          # no event; ambushed
        await act(client, "seek")
        assert not (await store.load(alice["id"])).climber.alive

        fixed_day["today"] = DAY_ONE + timedelta(days=1)
        await client.get(PAGE)
        await act(client, "go:herald")
        html = unescape((await client.get(PAGE)).text)

    today, yesterday = html.split("<h3>Yesterday</h3>")[0], html.split("<h3>Yesterday</h3>")[1]
    assert "<h3>Today</h3>" in today and text.DAILY[fixed_day["today"].toordinal() % len(text.DAILY)] in today
    assert "alice" in yesterday and "Agathe the Goatherd" in yesterday and "The Olive Terraces" in yesterday
    assert "Landlord's Bailiff" in yesterday                  # what killed them, in band 2
    assert yesterday.index("olive branch") < yesterday.index("Agathe") < yesterday.index("Bailiff") \
        or yesterday.index("newcomer") < yesterday.index("Agathe")


@pytest.mark.asyncio
async def test_news_is_kept_three_days_and_the_daily_line_is_written_once(alice, dice, fixed_day):
    await store.add_news(DAY_ONE, alice["id"], "day one")
    await store.add_news(DAY_ONE + timedelta(days=1), alice["id"], "day two")
    await store.add_news(DAY_ONE + timedelta(days=3), alice["id"], "day four")
    today = DAY_ONE + timedelta(days=3)
    for _ in range(3):
        await store.ensure_daily_line(today, "colour")
    news = await store.news(today)
    assert news == [(today, ["colour", "day four"]), (DAY_ONE + timedelta(days=1), ["day two"])]


@pytest.mark.asyncio
async def test_an_ascent_makes_the_news(alice, dice):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], level=12, weapon=12, armour=12)
        await act(client, "go:slopes")
        dice(chance=[NO_AMBUSH])
        await act(client, "garden")
        player = await store.load(alice["id"])
        player.fight.foe_hp = 1
        await store.save(player)
        dice(chance=[PLAIN], rolls=["min"])
        await act(client, "fight:attack")
        await act(client, "go:agora")
        await act(client, "go:herald")
        html = unescape((await client.get(PAGE)).text)
    assert "alice HAS COME DOWN WITH AN APPLE. That is ascent number 1." in html


@pytest.mark.asyncio
async def test_deleting_a_user_takes_their_news_and_wall_lines(alice, dice):
    admin = await auth.get_user(1)
    await store.add_wall_line(alice["id"], "I was here")
    await store.add_news(DAY_ONE, alice["id"], "alice did a thing")
    await store.ensure_daily_line(DAY_ONE, "colour")
    await auth.delete_user(alice["id"], reassign_channels_to=admin["id"])
    assert await store.wall_lines() == []
    assert await store.news(DAY_ONE) == [(DAY_ONE, ["colour"])]
    assert await auth.get_user(alice["id"]) is None

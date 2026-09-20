"""The Long Climb, step 6: robbing the sleeping. The first part of the game with two players in it."""

from datetime import timedelta
from html import unescape

import pytest

from lib import auth
from lib.climb import data, rules, store, text
from lib.db import get_db
from tests.helpers import client_for
from tests.test_climb_routes import DAY_ONE, PAGE, act, begin, offered, tweak
from tests.test_climb_routes import alice, dice, fixed_day  # noqa: F401  (fixtures)
from tests.test_climb_rules import NO_AMBUSH, PLAIN, climber

ASLEEP = dict(days_since_played=0, minutes_since_seen=60.0, days_since_joined=10.0, already_today=False)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def test_who_may_be_robbed():
    me, them = climber(level=5), climber(level=5)
    assert rules.why_not_rob(me, them, **ASLEEP) is None

    def why(attacker=me, target=them, **changes):
        return rules.why_not_rob(attacker, target, **{**ASLEEP, **changes})

    assert why(attacker=climber(level=5, duels_left=0)) == "spent"
    assert why(attacker=climber(level=5, alive=False)) == "spent"
    assert why(target=climber(level=5, alive=False)) == "dead"
    assert why(minutes_since_seen=9.9) == "awake"
    assert why(days_since_played=14) == "away" and why(days_since_played=13) is None
    assert why(days_since_joined=2.9) == "newcomer"
    assert why(already_today=True) == "already"
    assert why(target=climber(level=3)) == "beneath"
    assert why(target=climber(level=4)) is None and why(target=climber(level=12)) is None
    assert why(target=climber(level=5, room=True)) == "sheltered"
    assert why(attacker=climber(level=5, key=True), target=climber(level=5, room=True)) is None


def test_dawn_is_owed_to_a_sleeper_who_has_not_been_back():
    """Yesterday's dead are alive this morning, whether or not they have logged in to be told."""
    dead_yesterday = climber(level=5, alive=False, hp=0)
    assert rules.why_not_rob(climber(level=5), dead_yesterday, **{**ASLEEP, "days_since_played": 1}) is None
    foe = rules.sleeper_as_foe(dead_yesterday, "bob", days_since_played=1)
    assert foe.hp == data.MAX_HP[4]
    assert dead_yesterday.hp == 0 and not dead_yesterday.alive            # the real one is untouched


def test_one_nights_rent_does_not_shelter_you_for_ever():
    assert rules.is_sheltered(True, 0) and rules.is_sheltered(True, 1)
    assert not rules.is_sheltered(True, 2) and not rules.is_sheltered(False, 0)
    roomed = climber(level=5, room=True)
    assert rules.why_not_rob(climber(level=5), roomed, **{**ASLEEP, "days_since_played": 1}) == "sheltered"
    assert rules.why_not_rob(climber(level=5), roomed, **{**ASLEEP, "days_since_played": 2}) is None


def test_a_sleeper_fights_with_their_own_arm_and_armour():
    them = climber(level=6, weapon=7, armour=5, hp=40, strength_gift=4, purse=9999)
    foe = rules.sleeper_as_foe(them, "bob", 0)
    assert (foe.name, foe.kind, foe.hp) == ("bob", rules.CLIMBER, 40)
    assert foe.attack == rules.attack_power(them) and foe.guard == rules.guard_power(them)
    assert foe.xp == data.REF_XP[5] * 2 and foe.drachmae == 0             # the purse is never invented


def test_what_a_robbery_costs_each_side():
    victim = climber(purse=800, vault=5000, xp=1000, hp=7, fights_left=9)
    assert rules.apply_robbed(victim) == (800, 50)
    assert (victim.purse, victim.vault, victim.xp) == (0, 5000, 950)
    assert victim.alive and victim.hp == 7 and victim.fights_left == 9     # never a day

    sleeper = climber(purse=10, xp=0)
    assert rules.apply_defended(sleeper, 340, robber_level=4) == data.REF_XP[3]
    assert (sleeper.purse, sleeper.xp) == (350, data.REF_XP[3])


def test_the_key():
    c = climber(level=3, purse=10**6)
    price = rules.key_price(c)
    assert price == round(data.REF_DRACHMAE[2] * 20)
    assert rules.apply_key(c) == price and c.key and c.purse == 10**6 - price
    with pytest.raises(ValueError):
        rules.apply_key(c)
    with pytest.raises(ValueError):
        rules.apply_key(climber(purse=0))
    rules.apply_dawn(c)
    assert not c.key


# ---------------------------------------------------------------------------
# Through the routes
# ---------------------------------------------------------------------------

async def _settle_in(user_id, days_ago=10, minutes_idle=60, **attrs):
    """Make a climber an old hand who stopped playing a while ago."""
    db = await get_db()
    await db.execute(
        "UPDATE climb_players SET created_at = datetime('now', ?), last_seen = datetime('now', ?) WHERE user_id = ?",
        (f"-{days_ago} days", f"-{minutes_idle} minutes", user_id),
    )
    await db.commit()
    if attrs:
        player = await store.load(user_id)
        for key, value in attrs.items():
            setattr(player.climber, key, value)
        await store.save(player)
        await db.execute("UPDATE climb_players SET last_seen = datetime('now', ?) WHERE user_id = ?",
                         (f"-{minutes_idle} minutes", user_id))
        await db.commit()


@pytest.fixture
async def bob(alice):
    user = await auth.register_user("bob", "password123")
    await store.create(user["id"], rules.new_climber(data.TORCH), DAY_ONE, [])
    return user


@pytest.mark.asyncio
async def test_the_camp_lists_only_those_who_can_be_robbed(alice, bob, dice):
    names = {}
    for name in ("awake", "newcomer", "roomed", "lowly", "dead"):
        names[name] = await auth.register_user(name, "password123")
        await store.create(names[name]["id"], rules.new_climber(data.SPEAR), DAY_ONE, [])
    await _settle_in(bob["id"], level=5)
    await _settle_in(names["awake"]["id"], minutes_idle=2, level=5)
    await _settle_in(names["newcomer"]["id"], days_ago=1, level=5)
    await _settle_in(names["roomed"]["id"], level=5, room=True)
    await _settle_in(names["lowly"]["id"], level=2)
    await _settle_in(names["dead"]["id"], level=5, alive=False, hp=0)

    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], level=5)
        await act(client, "go:camp")
        html = unescape((await client.get(PAGE)).text)
        assert offered(html) == [f"rob:{bob['id']}", "go:agora"]
        assert "bob, Climber, asleep beside the Olive Branch, in the Wool Cloak." in html and "3 left tonight" in html
        for hidden in ("awake", "newcomer", "roomed", "lowly", "dead"):
            assert f"Rob {hidden}" not in html

        # Not on the list means not robbable, whatever the form says.
        dice()
        for name in names:
            await act(client, f"rob:{names[name]['id']}")
        await act(client, f"rob:{alice['id']}")
        await act(client, "rob:99999")
        assert (await store.load(alice["id"])).fight is None


@pytest.mark.asyncio
async def test_a_robbery_won(alice, bob, dice):
    await _settle_in(bob["id"], purse=500, vault=9000, xp=200, hp=4)
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], weapon=12)
        await act(client, "go:camp")
        dice(chance=[NO_AMBUSH])
        await act(client, f"rob:{bob['id']}")

        player = await store.load(alice["id"])
        assert player.fight.foe.name == "bob" and player.fight.target_id == bob["id"]
        assert player.climber.duels_left == 2
        html = unescape((await client.get(PAGE)).text)
        assert "bob wakes." in html and offered(html) == ["fight:attack", "fight:fury", "fight:run"]

        dice(chance=[PLAIN], rolls=["max"])
        await act(client, "fight:attack")

        robber = (await store.load(alice["id"])).climber
        assert robber.purse == 60 + 500 and robber.xp == data.REF_XP[0] * 2
        html = unescape((await client.get(PAGE)).text)
        assert "The purse is yours: 500 drachmae." in html and "The Camp" in html
        assert offered(html) == ["go:agora"]                              # once per victim per day

        await act(client, "go:agora")
        await act(client, "go:herald")
        assert "bob" in (await client.get(PAGE)).text and "robbed" in (await client.get(PAGE)).text.lower()

    victim = await store.load(bob["id"])
    assert (victim.climber.purse, victim.climber.vault, victim.climber.xp) == (0, 9000, 190)
    assert victim.climber.alive and victim.climber.hp == 4 and victim.climber.fights_left == 15
    assert victim.mail == [text.MAIL_ROBBED.format(name="alice", drachmae=500, xp=10)]


@pytest.mark.asyncio
async def test_the_victim_finds_the_note_even_after_dawn(alice, bob, dice, fixed_day):
    await _settle_in(bob["id"], purse=500)
    async with await client_for(alice["id"]) as a:
        await begin(a)
        await tweak(alice["id"], weapon=12)
        await act(a, "go:camp")
        dice(chance=[NO_AMBUSH])
        await act(a, f"rob:{bob['id']}")
        dice(chance=[PLAIN], rolls=["max"])
        await act(a, "fight:attack")

    fixed_day["today"] = DAY_ONE + timedelta(days=1)
    async with await client_for(bob["id"]) as b:
        html = unescape((await b.get(PAGE)).text)
        assert "While you slept, alice robbed you: 500 drachmae gone" in html
        assert html.index("While you slept") < html.index("Dawn.")
        assert "While you slept" in unescape((await b.get(PAGE)).text)     # still there on reload...
        await act(b, "go:vault")
        assert "While you slept" not in (await b.get(PAGE)).text          # ...until they do something
    assert (await store.load(bob["id"])).mail == []


@pytest.mark.asyncio
async def test_coin_cannot_be_duplicated_by_banking_mid_robbery(alice, bob, dice):
    """The exploit a snapshot would allow: A attacks B, B banks, A still collects B's old purse."""
    await _settle_in(bob["id"], purse=500)
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await begin(a)
        await tweak(alice["id"], weapon=12)
        await act(a, "go:camp")
        dice(chance=[NO_AMBUSH])
        await act(a, f"rob:{bob['id']}")

        await act(b, "go:vault")                                          # bob wakes up, as players do
        await act(b, "vault:deposit_all")

        dice(chance=[PLAIN], rolls=["max"])
        await act(a, "fight:attack")
        html = unescape((await a.get(PAGE)).text)

    robber, victim = (await store.load(alice["id"])).climber, await store.load(bob["id"])
    assert robber.purse == 60 and "The purse is empty." in html
    assert (victim.climber.purse, victim.climber.vault) == (0, 500)
    assert robber.purse + robber.vault + victim.climber.purse + victim.climber.vault == 60 + 500
    assert "found an empty purse" in victim.mail[0]


@pytest.mark.asyncio
async def test_a_robbery_lost(alice, bob, dice):
    await _settle_in(bob["id"], level=2, weapon=12, armour=12, purse=5, xp=0)
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], hp=2, purse=77, xp=100)
        await act(client, "go:camp")
        dice(chance=[NO_AMBUSH])
        await act(client, f"rob:{bob['id']}")
        dice(chance=[PLAIN], rolls=["min", "max"])
        await act(client, "fight:attack")
        html = unescape((await client.get(PAGE)).text)

    robber = (await store.load(alice["id"])).climber
    assert not robber.alive and robber.purse == 0 and robber.xp == 90
    assert "bob was better than they looked asleep." in html and "Dead until dawn" in html

    victim = await store.load(bob["id"])
    assert victim.climber.purse == 5 + 77 and victim.climber.xp == data.REF_XP[0]
    assert victim.mail == [text.MAIL_DEFENDED.format(name="alice", drachmae=77, xp=data.REF_XP[0])]
    assert [line for _, lines in await store.news(DAY_ONE) for line in lines
            if "technically asleep" in line]


@pytest.mark.asyncio
async def test_running_from_a_robbery_still_uses_the_attempt(alice, bob, dice):
    await _settle_in(bob["id"], purse=500)
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:camp")
        dice(chance=[NO_AMBUSH])
        await act(client, f"rob:{bob['id']}")
        dice(chance=[0.0])
        await act(client, "fight:run")
        html = unescape((await client.get(PAGE)).text)
    assert text.ROB_FLED in html and offered(html) == ["go:agora"]
    assert (await store.load(alice["id"])).climber.duels_left == 2
    assert (await store.load(bob["id"])).climber.purse == 500 and (await store.load(bob["id"])).mail == []


@pytest.mark.asyncio
async def test_three_attempts_a_night(alice, bob, dice):
    await _settle_in(bob["id"])
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], duels_left=0)
        await act(client, "go:camp")
        html = unescape((await client.get(PAGE)).text)
    assert text.CAMP_SPENT in html and offered(html) == ["go:agora"]


@pytest.mark.asyncio
async def test_nikandros_key_opens_one_door(alice, bob, dice):
    await _settle_in(bob["id"], room=True, purse=900)
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], purse=1000, weapon=12)
        await act(client, "go:camp")
        assert offered((await client.get(PAGE)).text) == ["go:agora"]

        await act(client, "go:agora")
        await act(client, "go:lethe")
        html = unescape((await client.get(PAGE)).text)
        assert "for 440 drachmae" in html and "key" in offered(html)
        await act(client, "key")
        assert (await store.load(alice["id"])).climber.purse == 560
        assert "key" not in offered((await client.get(PAGE)).text)

        await act(client, "go:agora")
        await act(client, "go:camp")
        html = unescape((await client.get(PAGE)).text)
        assert text.CAMP_KEY in html and "bob, Climber, asleep upstairs at the Lethe House, with the Olive Branch" in html

        dice(chance=[NO_AMBUSH])
        await act(client, f"rob:{bob['id']}")
        assert "The key turns." in unescape((await client.get(PAGE)).text)
        assert not (await store.load(alice["id"])).climber.key              # one door
        dice(chance=[PLAIN], rolls=["max"])
        await act(client, "fight:attack")
    assert (await store.load(alice["id"])).climber.purse == 560 + 900


@pytest.mark.asyncio
async def test_the_stele_and_the_fire_say_where_people_sleep(alice, bob, dice):
    await _settle_in(bob["id"], room=True, level=4, weapon=5, armour=3)
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:stele")
        html = unescape((await client.get(PAGE)).text)
        assert "in a room" in html and "at the Camp" in html

        await tweak(alice["id"], fire_known=True)
        await act(client, "go:agora")
        await act(client, "go:slopes")
        await act(client, "go:fire")
        await act(client, "go:others")
        html = unescape((await client.get(PAGE)).text)
        assert "We see where they sleep." in html
        row = html.split("<td>bob ")[1].split("</tr>")[0]
        assert "Hoplite's Xiphos" in row and "Linen Cuirass" in row and "in a room" in row
        assert "<td>alice " not in html                                    # you know where you sleep
        assert offered(html) == ["go:fire"]


@pytest.mark.asyncio
async def test_deleting_a_user_clears_the_robbery_log(alice, bob, dice):
    admin = await auth.get_user(1)
    await store.note_robbery(DAY_ONE, alice["id"], bob["id"])
    await store.note_robbery(DAY_ONE, bob["id"], alice["id"])
    await auth.delete_user(bob["id"], reassign_channels_to=admin["id"])
    db = await get_db()
    assert (await (await db.execute("SELECT COUNT(*) FROM climb_robberies")).fetchone())[0] == 0

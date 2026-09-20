"""The Long Climb, step 7: courtship. The consent rules are tests, not comments."""

from datetime import timedelta
from html import unescape

import pytest

from lib import auth
from lib.climb import data, rules, scenes, store, text
from lib.db import get_db
from tests.helpers import client_for
from tests.test_climb_routes import DAY_ONE, PAGE, act, begin, offered, tweak
from tests.test_climb_routes import alice, dice, fixed_day  # noqa: F401  (fixtures)
from tests.test_climb_rules import Dice, climber
from tests.test_climb_camp import ASLEEP, _settle_in

WIN, LOSE, NO_CHARM, CHARM = 0.0, 0.99, 0.99, 0.0


# ---------------------------------------------------------------------------
# The regulars: rules
# ---------------------------------------------------------------------------

def test_hearts_start_closed_and_free():
    c = rules.new_climber(data.SPEAR)
    assert (c.heart, c.courtship, c.wed, c.open_heart) == ("", 0, False, False)


def test_each_step_needs_more_charm_and_more_charm_helps():
    assert data.COURTSHIP_CHARM == tuple(sorted(data.COURTSHIP_CHARM)) and len(data.COURTSHIP_CHARM) == 8
    assert rules.why_not_court(climber(charm=0), "kalliste") == "charm"
    assert rules.why_not_court(climber(charm=1), "kalliste") is None
    assert rules.court_chance(climber(charm=1), 1) == 0.50
    assert rules.court_chance(climber(charm=5), 1) == pytest.approx(0.70)
    assert rules.court_chance(climber(charm=99), 1) == 0.95
    with pytest.raises(ValueError):
        rules.why_not_court(climber(), "brontes")


def test_courting_a_regular_step_by_step():
    c = climber(level=3, charm=30, purse=10_000)
    first = rules.apply_courtship(Dice(chance=[WIN, NO_CHARM]), c, "theron")
    assert (first.step, first.won, first.xp) == (1, True, data.REF_XP[2] * 2)
    assert (c.heart, c.courtship, c.xp) == ("npc:theron", 1, first.xp) and c.courted_today
    assert rules.why_not_court(c, "theron") == "today"

    rules.apply_dawn(c)
    lost = rules.apply_courtship(Dice(chance=[LOSE]), c, "theron")
    assert not lost.won and c.courtship == 1                  # no progress, and no penalty
    rules.apply_dawn(c)
    assert rules.why_not_court(c, "kalliste") == "other"       # one at a time

    charmed = rules.apply_courtship(Dice(chance=[WIN, CHARM]), c, "theron")
    assert charmed.charmed and c.charm == 31


def test_the_gift_costs_money_win_or_lose():
    c = climber(level=2, charm=30, courtship=4, heart="npc:kalliste", purse=0)
    assert rules.why_not_court(c, "kalliste") == "gift"
    c.purse = 1000
    rules.apply_courtship(Dice(chance=[LOSE]), c, "kalliste")
    assert c.purse == 1000 - rules.gift_price(c) and c.courtship == 4


def test_marrying_a_regular_and_what_it_brings():
    c = climber(level=4, charm=30, courtship=7, heart="npc:kalliste", purse=0)
    result = rules.apply_courtship(Dice(chance=[WIN, NO_CHARM]), c, "kalliste")
    assert result.married and c.wed and c.courtship == 8
    assert rules.why_not_court(c, "theron") == "today"        # one move a day, even that one
    rules.apply_dawn(c)
    assert rules.why_not_court(c, "theron") == "wed" and rules.why_not_court(c, "kalliste") == "wed"
    c.purse = 0

    assert rules.apply_spouse_dawn(c) == ("gift", data.REF_DRACHMAE[3]) and c.purse == data.REF_DRACHMAE[3]
    rules.apply_ascent(c)
    assert c.wed and c.heart == "npc:kalliste"                # the heart survives the mountain

    rules.apply_parting(c)
    assert (c.heart, c.wed, c.courtship, c.charm) == ("", False, 0, 28)
    with pytest.raises(ValueError):
        rules.apply_parting(c)
    assert rules.apply_spouse_dawn(c) is None


# ---------------------------------------------------------------------------
# Other climbers: rules
# ---------------------------------------------------------------------------

def test_flirting_needs_both_hearts_open():
    assert rules.why_not_flirt(climber(), them_open=True) == "closed"
    assert rules.why_not_flirt(climber(open_heart=True), them_open=False) == "their_door"
    assert rules.why_not_flirt(climber(open_heart=True), them_open=True) is None
    assert rules.why_not_flirt(climber(open_heart=True, flirted_today=True), True) == "today"
    assert rules.why_not_flirt(climber(open_heart=True, wed=True, heart="player:9"), True) == "wed"


def test_affinity_only_grows_when_attention_is_returned():
    assert not rules.flirt_counts(None, None)                  # my first, unanswered
    assert rules.flirt_counts(None, "2026-10-01")              # my answer to theirs
    assert rules.flirt_counts("2026-10-01", "2026-10-01")      # they answered the day I flirted
    assert not rules.flirt_counts("2026-10-02", "2026-10-01")  # I keep on; they have not replied since
    assert rules.flirt_counts("2026-10-02", "2026-10-03")


def test_proposing_needs_affinity_charm_and_two_free_hearts():
    ready = climber(open_heart=True, charm=5)
    assert rules.can_propose(ready, 5, their_heart_free=True)
    assert not rules.can_propose(ready, 4, True)
    assert not rules.can_propose(climber(open_heart=True, charm=4), 5, True)
    assert not rules.can_propose(ready, 5, their_heart_free=False)
    assert not rules.can_propose(climber(charm=5), 5, True)                  # closed heart
    assert not rules.can_propose(climber(open_heart=True, charm=5, wed=True, heart="npc:theron"), 5, True)


def test_spouses_cannot_rob_each_other_and_bring_climbs_at_dawn():
    assert rules.why_not_rob(climber(level=5), climber(level=5), **ASLEEP, married=True) == "spouse"
    c = climber(charm=9)
    rules.apply_wedding(c, 42)
    assert rules.spouse_id(c) == 42 and rules.courting(c) is None
    with pytest.raises(ValueError):
        rules.apply_wedding(c, 43)
    assert rules.apply_spouse_dawn(c, spouse_played_yesterday=False) is None
    assert rules.apply_spouse_dawn(c, spouse_played_yesterday=True) == ("fights", 2) and c.fights_left == 17


# ---------------------------------------------------------------------------
# The corner table, through the routes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_courting_theron_through_the_site(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await act(client, "go:lethe")
        await act(client, "go:corner")
        html = unescape((await client.get(PAGE)).text)
        assert text.COURT_FRESH in html and "you would need Charm 1. You have 0." in html
        assert offered(html) == ["go:hearts", "go:lethe"]

        await tweak(alice["id"], charm=3)
        assert offered((await client.get(PAGE)).text) == ["court:kalliste", "court:theron", "go:hearts", "go:lethe"]

        dice(chance=[WIN, NO_CHARM])
        await act(client, "court:theron")
        html = unescape((await client.get(PAGE)).text)
        assert "knocks over the salt" in html and "XP" in html
        assert text.COURT_TOMORROW in html and offered(html) == ["part", "go:hearts", "go:lethe"]

        fixed_day["today"] += timedelta(days=1)
        await client.get(PAGE)
        await act(client, "go:lethe")
        await act(client, "go:corner")
        html = unescape((await client.get(PAGE)).text)
        assert "With Theron you have got as far as: catch their eye. Next: stand them a cup of wine (Charm 2)." in html
        assert offered(html) == ["court:theron", "part", "go:hearts", "go:lethe"]       # not Kalliste: one at a time

        dice(chance=[LOSE])
        await act(client, "court:theron")
        assert "goes on talking to the table" in unescape((await client.get(PAGE)).text)

        await act(client, "part")
        c = (await store.load(alice["id"])).climber
        assert (c.heart, c.courtship, c.charm) == ("", 0, 1)


@pytest.mark.asyncio
async def test_marrying_a_regular_makes_the_news_and_brings_a_gift_at_dawn(alice, dice, fixed_day):
    async with await client_for(alice["id"]) as client:
        await begin(client)
        await tweak(alice["id"], charm=40, courtship=7, heart="npc:kalliste")
        await act(client, "go:lethe")
        await act(client, "go:corner")
        dice(chance=[WIN, NO_CHARM])
        await act(client, "court:kalliste")
        html = unescape((await client.get(PAGE)).text)
        assert "I decided at the river" in html and "married at the festival fire" in html

        fixed_day["today"] += timedelta(days=1)
        html = unescape((await client.get(PAGE)).text)
        assert "Kalliste left 22 drachmae by the bed" in html
        await act(client, "go:herald")
        assert "alice and Kalliste were married" in unescape((await client.get(PAGE)).text)


# ---------------------------------------------------------------------------
# Other climbers, through the routes
# ---------------------------------------------------------------------------

@pytest.fixture
async def bob(alice):
    user = await auth.register_user("bob", "password123")
    await store.create(user["id"], rules.new_climber(data.TORCH), DAY_ONE, [])
    return user


async def _to_hearts(client):
    await act(client, "go:agora") if False else None
    await act(client, "go:lethe")
    await act(client, "go:corner")
    await act(client, "go:hearts")


async def _open(user_id, **attrs):
    player = await store.load(user_id)
    player.climber.open_heart = True
    for key, value in attrs.items():
        setattr(player.climber, key, value)
    await store.save(player)


@pytest.mark.asyncio
async def test_nobody_can_flirt_with_a_closed_heart_or_from_one(alice, bob, dice):
    """Opt-in, default off, in both directions."""
    async with await client_for(alice["id"]) as a:
        await begin(a)
        await _to_hearts(a)
        html = unescape((await a.get(PAGE)).text)
        assert text.HEART_CLOSED in html and "bob" not in html
        assert offered(html) == ["heart:open", "go:corner"]
        await act(a, f"suitor:{bob['id']}")                   # not listed, so not reachable
        assert (await store.load(alice["id"])).scene == "hearts"

        await act(a, "heart:open")
        html = unescape((await a.get(PAGE)).text)
        assert text.NOBODY_OPEN in html and "bob" not in html  # bob has not opted in
        await act(a, f"suitor:{bob['id']}")
        assert (await store.load(alice["id"])).scene == "hearts"

        await _open(bob["id"])
        html = unescape((await a.get(PAGE)).text)
        assert "(1) bob, Climber, in The Foothills." in html
        await act(a, "heart:close")
        assert "bob" not in (await a.get(PAGE)).text
    assert (await store.load(bob["id"])).mail == []


@pytest.mark.asyncio
async def test_a_flirt_carries_no_words_and_arrives_as_a_note(alice, bob, dice):
    await _open(bob["id"])
    async with await client_for(alice["id"]) as a:
        await begin(a)
        await _open(alice["id"])
        await _to_hearts(a)
        await act(a, f"suitor:{bob['id']}")
        html = unescape((await a.get(PAGE)).text)
        assert offered(html) == ["flirt", "door:shut", "go:hearts"]
        assert 'name="words"' not in html and 'name="amount"' not in html       # nothing to type

        turn = (await store.load(alice["id"])).turn
        await a.post(f"{PAGE}/act", data={"action": "flirt", "turn": turn, "words": "u up?", "amount": 5})
        html = unescape((await a.get(PAGE)).text)
        assert "flirt" not in offered(html)                                      # one a day

    victim = await store.load(bob["id"])
    assert victim.mail == [text.MAIL_FLIRT.format(name="alice")] and "u up" not in str(victim.mail)
    assert (await store.bonds(alice["id"]))[bob["id"]].affinity == 0             # unanswered


@pytest.mark.asyncio
async def test_closing_the_door_is_silent(alice, bob, dice, fixed_day):
    await _open(bob["id"])
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await begin(a)
        await _open(alice["id"])
        await _to_hearts(a)
        await act(a, f"suitor:{bob['id']}")
        await act(a, "flirt")

        await _to_hearts(b)
        await act(b, f"suitor:{alice['id']}")
        assert "They have flirted with you." in unescape((await b.get(PAGE)).text)
        await act(b, "door:shut")
        assert "They will not be told." in unescape((await b.get(PAGE)).text)
        mail_before = list((await store.load(bob["id"])).mail)

        fixed_day["today"] += timedelta(days=1)
        await a.get(PAGE)
        await _to_hearts(a)
        await act(a, f"suitor:{bob['id']}")
        before = unescape((await a.get(PAGE)).text)
        assert "flirt" in offered(before)                                        # alice sees nothing different
        await act(a, "flirt")
        after = unescape((await a.get(PAGE)).text)
        assert text.FLIRTED.format(name="bob") in after                          # and is told the usual thing

        assert (await store.load(bob["id"])).mail == mail_before                 # nothing arrived
        assert (await store.bonds(bob["id"]))[alice["id"]].affinity == 0

        # bob's list no longer says she flirted, but he can still find her to reopen the door.
        await b.get(PAGE)                                     # a new day: bob wakes in the Agora
        await _to_hearts(b)
        html = unescape((await b.get(PAGE)).text)
        assert "alice" in html and "They have flirted with you." not in html
        await act(b, f"suitor:{alice['id']}")
        assert offered((await b.get(PAGE)).text) == ["door:open", "go:hearts"]


async def _build_affinity(a, b, alice_id, bob_id, fixed_day, rounds):
    for _ in range(rounds):
        for client, other in ((a, bob_id), (b, alice_id)):
            await client.get(PAGE)
            await _to_hearts(client)
            await act(client, f"suitor:{other}")
            await act(client, "flirt")
        fixed_day["today"] += timedelta(days=1)


@pytest.mark.asyncio
async def test_from_flirting_to_married_to_divorced(alice, bob, dice, fixed_day):
    await _open(bob["id"], charm=6)
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await begin(a)
        await _open(alice["id"], charm=6)
        await _build_affinity(a, b, alice["id"], bob["id"], fixed_day, rounds=3)
        affinity = (await store.bonds(alice["id"]))[bob["id"]].affinity
        assert affinity == 5                                  # every flirt but the very first was an answer

        await a.get(PAGE)
        await _to_hearts(a)
        await act(a, f"suitor:{bob['id']}")
        html = unescape((await a.get(PAGE)).text)
        assert "5 out of the 5" in html and "propose" in offered(html)
        await act(a, "propose")
        assert "propose" not in offered((await a.get(PAGE)).text)

        html = unescape((await b.get(PAGE)).text)
        assert "alice has asked you to marry them" in html
        await _to_hearts(b)
        assert "They have asked you to marry them." in unescape((await b.get(PAGE)).text)
        await act(b, f"suitor:{alice['id']}")
        assert {"accept", "decline"} <= set(offered((await b.get(PAGE)).text))
        await act(b, "accept")

        bob_c, alice_p = (await store.load(bob["id"])).climber, await store.load(alice["id"])
        assert rules.spouse_id(bob_c) == alice["id"] and rules.spouse_id(alice_p.climber) == bob["id"]
        assert "bob said yes." in str(alice_p.mail)
        assert [l for _, ls in await store.news(fixed_day["today"]) for l in ls if "bob and alice were married" in l]

        # Married: neither can rob the other, and each brings the other climbs at dawn.
        await _settle_in(alice["id"])
        await act(b, "go:hearts")
        await act(b, "go:corner"); await act(b, "go:lethe"); await act(b, "go:agora"); await act(b, "go:camp")
        assert f"rob:{alice['id']}" not in offered((await b.get(PAGE)).text)

        fixed_day["today"] += timedelta(days=1)
        html = unescape((await b.get(PAGE)).text)
        assert "alice was on the mountain yesterday" in html
        assert (await store.load(bob["id"])).climber.fights_left == 17

        await _to_hearts(b)
        await act(b, f"suitor:{alice['id']}")
        assert offered((await b.get(PAGE)).text) == ["divorce", "go:hearts"]
        await act(b, "divorce")

    bob_c, alice_p = (await store.load(bob["id"])).climber, await store.load(alice["id"])
    assert (bob_c.heart, bob_c.wed, bob_c.charm) == ("", False, 4)
    assert (alice_p.climber.heart, alice_p.climber.wed, alice_p.climber.charm) == ("", False, 6)
    assert "bob has ended your marriage." in str(alice_p.mail)
    assert alice["id"] not in await store.bonds(bob["id"])


@pytest.mark.asyncio
async def test_a_proposal_can_be_declined(alice, bob, dice):
    await store.create(alice["id"], rules.new_climber(data.SPEAR), DAY_ONE, [])
    await _open(bob["id"])
    await store.set_proposal(alice["id"], bob["id"], alice["id"])
    async with await client_for(bob["id"]) as b:
        await _to_hearts(b)
        await act(b, f"suitor:{alice['id']}")
        await act(b, "decline")
    assert (await store.bonds(bob["id"]))[alice["id"]].proposal_from is None
    assert not (await store.load(bob["id"])).climber.wed


@pytest.mark.asyncio
async def test_you_cannot_accept_for_someone_who_married_elsewhere(alice, bob, dice):
    await store.create(alice["id"], rules.new_climber(data.SPEAR), DAY_ONE, [])
    await store.set_proposal(alice["id"], bob["id"], alice["id"])
    await tweak(alice["id"], heart="npc:theron", wed=True)
    async with await client_for(bob["id"]) as b:
        await _to_hearts(b)
        await act(b, f"suitor:{alice['id']}")
        assert offered((await b.get(PAGE)).text) == ["decline", "door:shut", "go:hearts"]
        await act(b, "accept")
    assert not (await store.load(bob["id"])).climber.wed


@pytest.mark.asyncio
async def test_deleting_a_user_frees_their_spouse_and_clears_hearts(alice, bob, dice):
    admin = await auth.get_user(1)
    await store.create(alice["id"], rules.new_climber(data.SPEAR), DAY_ONE, [])
    await tweak(alice["id"], heart=f"player:{bob['id']}", wed=True)
    await store.note_flirt(alice["id"], bob["id"], DAY_ONE, True)
    await store.set_door(alice["id"], bob["id"], True)
    await auth.delete_user(bob["id"], reassign_channels_to=admin["id"])

    c = (await store.load(alice["id"])).climber
    assert (c.heart, c.wed) == ("", False)
    db = await get_db()
    for table in ("climb_hearts", "climb_doors"):
        assert (await (await db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone())[0] == 0

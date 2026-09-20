"""Mille Bornes against the CPU, driven through the HTTP routes.

Hands and the deck are stacked by hand so every turn is deterministic. The
deck is a stack: ``deck.pop()`` takes from the end, the CPU draws first on
its turn, then the human draws.
"""

import pytest

from lib import auth, mille
from lib.db import get_db
from tests.helpers import anon_client, client_for
from tests.test_mille_rules import (
    ACCIDENT, ACE, D, END_OF_LIMIT, GASOLINE, REPAIRS, RIGHT_OF_WAY, ROLL, STOP,
)

PAGE = "/games/mille"


def stack(uid, human, cpu, deck, **human_attrs):
    """Start a game and replace the random deal with known cards."""
    game = mille.new_game(uid)
    game.human.hand, game.cpu.hand, game.deck = list(human), list(cpu), list(deck)
    for key, value in human_attrs.items():
        setattr(game.human, key, value)
    return game


def state_of(html: str) -> str:
    markers = [
        ("Game Lobby", "lobby"), ("Challenge Sent", "waiting_invite"),
        ("Play it as a Coup", "coup_fourre"), ("Game Over", "game_over"),
        ("Your Hand", "active"), ("to play...", "pvp_waiting"),
    ]
    return next((state for text, state in markers if text in html), "unknown")


async def _scores(user_id):
    db = await get_db()
    cursor = await db.execute(
        "SELECT score, opponent, won, game FROM game_scores WHERE user_id = ? ORDER BY id", (user_id,)
    )
    return [dict(row) for row in await cursor.fetchall()]


@pytest.fixture
async def alice():
    await auth.register_user("admin", "password123")
    return await auth.register_user("alice", "password123")


# ---------------------------------------------------------------------------
# Getting in
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_games_require_login():
    async with anon_client() as client:
        for path in ("/games", PAGE):
            resp = await client.get(path)
            assert resp.status_code == 302 and resp.headers["location"] == "/"


@pytest.mark.asyncio
async def test_games_index_and_legacy_redirect(alice):
    async with await client_for(alice["id"]) as client:
        index = await client.get("/games")
        assert "Mille Bornes" in index.text and 'href="/games/mille"' in index.text
        legacy = await client.get("/mille")
        assert legacy.status_code == 302 and legacy.headers["location"] == PAGE


@pytest.mark.asyncio
async def test_lobby_then_new_game(alice):
    async with await client_for(alice["id"]) as client:
        assert state_of((await client.get(PAGE)).text) == "lobby"

        resp = await client.post(f"{PAGE}/new")
        assert resp.status_code == 302 and resp.headers["location"] == PAGE
        first = mille.get_game(alice["id"])
        assert first is not None
        assert state_of((await client.get(PAGE)).text) == "active"

        await client.post(f"{PAGE}/new")
        assert mille.get_game(alice["id"]) is not first


@pytest.mark.asyncio
async def test_new_game_cancels_outgoing_invite_but_not_during_pvp(alice):
    mille.create_invite(alice["id"], "alice", 99, "bob")
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/new")
        assert mille.get_invite_from(alice["id"]) is None

        mille.remove_game(alice["id"])
        mille.new_pvp_game(alice["id"], "alice", 99, "bob")
        await client.post(f"{PAGE}/new")
        assert mille.get_game(alice["id"]) is None


@pytest.mark.asyncio
async def test_actions_without_a_game_are_harmless(alice):
    async with await client_for(alice["id"]) as client:
        for path, data in (("play", {"card_index": 0}), ("discard", {"card_index": 0}), ("coup", {"accept": "yes"})):
            resp = await client.post(f"{PAGE}/{path}", data=data)
            assert resp.status_code == 302
    assert mille.get_game(alice["id"]) is None


# ---------------------------------------------------------------------------
# A turn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_play_runs_cpu_turn_then_draws(alice):
    game = stack(
        alice["id"],
        human=[ROLL, D(100)], cpu=[D(25)],
        deck=[D(50), GASOLINE, ROLL],   # CPU draws ROLL, human draws GASOLINE
    )
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})

    assert game.human.rolling
    assert game.human.hand == [D(100), GASOLINE]
    assert game.cpu.rolling and game.cpu.hand == [D(25)]
    assert game.deck == [D(50)]
    assert game.messages == ["You plays Roll and starts moving!", "CPU plays Roll and starts moving!"]


@pytest.mark.asyncio
async def test_illegal_card_is_refused_and_costs_nothing(alice):
    game = stack(alice["id"], human=[D(100), ROLL], cpu=[ROLL], deck=[D(25), D(50)])
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})   # not rolling yet
        html = (await client.get(PAGE)).text

    assert game.human.miles == 0 and game.human.hand == [D(100), ROLL]
    assert game.cpu.hand == [ROLL] and len(game.deck) == 2          # CPU did not move
    assert "Can&#39;t play 100 mi right now." in html or "Can't play 100 mi right now." in html


@pytest.mark.asyncio
@pytest.mark.parametrize("index", [-1, 2, 999])
async def test_out_of_range_index_is_ignored(alice, index):
    game = stack(alice["id"], human=[ROLL, D(25)], cpu=[ROLL], deck=[D(50), D(75)])
    async with await client_for(alice["id"]) as client:
        for action in ("play", "discard"):
            resp = await client.post(f"{PAGE}/{action}", data={"card_index": index})
            assert resp.status_code == 302
    assert game.human.hand == [ROLL, D(25)] and len(game.deck) == 2


@pytest.mark.asyncio
async def test_non_numeric_index_is_a_validation_error_not_a_crash(alice):
    stack(alice["id"], human=[ROLL], cpu=[ROLL], deck=[D(50)])
    async with await client_for(alice["id"]) as client:
        resp = await client.post(f"{PAGE}/play", data={"card_index": "abc"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_discard(alice):
    game = stack(alice["id"], human=[D(200), ROLL], cpu=[D(25)], deck=[D(50), D(75), ACCIDENT])
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/discard", data={"card_index": 0})

    assert game.human.hand == [ROLL, D(75)]
    assert game.messages[0] == "You discard 200 mi."
    # CPU drew the Accident but the human is not moving, so it could only discard.
    assert game.messages[1] == "CPU discards a card."
    assert len(game.cpu.hand) == 1


@pytest.mark.asyncio
async def test_no_draw_once_the_deck_is_empty(alice):
    game = stack(alice["id"], human=[ROLL, D(25)], cpu=[ROLL, D(25)], deck=[])
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
    assert game.human.hand == [D(25)]
    assert game.cpu.hand == [D(25)] and game.cpu.rolling


@pytest.mark.asyncio
async def test_page_marks_which_cards_are_playable(alice):
    stack(alice["id"], human=[ROLL, D(100), ACE], cpu=[ROLL], deck=[D(25)])
    async with await client_for(alice["id"]) as client:
        html = (await client.get(PAGE)).text
    # Roll and the safety can be played; the distance card cannot yet.
    assert html.count(f'action="{PAGE}/play"') == 2
    assert html.count(f'action="{PAGE}/discard"') == 3


# ---------------------------------------------------------------------------
# Coup fourré
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cpu_answers_a_hazard_with_coup_fourre(alice):
    game = stack(
        alice["id"], human=[ACCIDENT, D(25)], cpu=[ACE, D(50)], deck=[D(75), D(25), D(100)],
    )
    game.cpu.rolling = True
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})

    assert game.cpu.coups == 1 and game.cpu.safeties == ["Driving Ace"]
    assert game.cpu.hazard is None
    assert "CPU plays Coup Fourre: Driving Ace!" in game.messages
    # Unharmed, it went on to drive the 100 it drew.
    assert game.cpu.miles == 100


async def _cpu_plays_accident_on(alice_id, client, extra_human=()):
    """Human is moving and holds Driving Ace; the CPU's only move is an Accident."""
    game = stack(
        alice_id,
        human=[D(25), ACE, *extra_human], cpu=[D(50)],
        deck=[D(75), D(100), ACCIDENT],      # CPU draws the Accident
        rolling=True,
    )
    await client.post(f"{PAGE}/play", data={"card_index": 0})
    return game


@pytest.mark.asyncio
async def test_human_is_offered_coup_fourre_and_play_is_paused(alice):
    async with await client_for(alice["id"]) as client:
        game = await _cpu_plays_accident_on(alice["id"], client)

        assert game.coup_fourre_pending == "Accident"
        assert game.human.hazard == "Accident"
        assert game.human.hand == [ACE]                  # no draw while the question is open
        html = (await client.get(PAGE)).text
        assert state_of(html) == "coup_fourre" and "Driving Ace" in html

        await client.post(f"{PAGE}/play", data={"card_index": 0})
        await client.post(f"{PAGE}/discard", data={"card_index": 0})
        assert game.human.hand == [ACE] and game.coup_fourre_pending == "Accident"


@pytest.mark.asyncio
async def test_accepting_coup_fourre(alice):
    async with await client_for(alice["id"]) as client:
        game = await _cpu_plays_accident_on(alice["id"], client)
        await client.post(f"{PAGE}/coup", data={"accept": "yes"})

        assert game.coup_fourre_pending is None
        assert game.human.coups == 1 and game.human.safeties == ["Driving Ace"]
        assert game.human.hazard is None and game.human.can_move
        assert game.human.hand == [D(100)]               # drew, and it is the human's turn
        assert game.cpu.hand == [D(50)]                  # CPU did not get another move
        assert state_of((await client.get(PAGE)).text) == "active"


@pytest.mark.asyncio
async def test_declining_coup_fourre_keeps_the_hazard(alice):
    async with await client_for(alice["id"]) as client:
        game = await _cpu_plays_accident_on(alice["id"], client)
        await client.post(f"{PAGE}/coup", data={"accept": "no"})

    assert game.coup_fourre_pending is None
    assert game.human.hazard == "Accident" and game.human.coups == 0
    assert game.human.hand == [ACE, D(100)]
    assert game.cpu.hand == [D(50)]


@pytest.mark.asyncio
async def test_stop_and_speed_limit_are_both_answered_by_right_of_way(alice):
    game = stack(
        alice["id"], human=[D(25), RIGHT_OF_WAY], cpu=[D(50)], deck=[D(75), D(100), STOP], rolling=True,
    )
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
        assert game.coup_fourre_pending == "Stop"
        await client.post(f"{PAGE}/coup", data={"accept": "yes"})
    assert game.human.safeties == ["Right of Way"] and game.human.can_move


# ---------------------------------------------------------------------------
# Ending the game
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaching_1000_wins_immediately_and_is_scored_once(alice):
    game = stack(alice["id"], human=[D(100), D(25)], cpu=[ROLL], deck=[D(50), D(75)], rolling=True, miles=900)
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})

        assert game.winner == "You"
        assert game.cpu.hand == [ROLL] and len(game.deck) == 2      # nothing happens after the win
        assert await _scores(alice["id"]) == []                       # saved when the result is shown

        html = (await client.get(PAGE)).text
        assert state_of(html) == "game_over"
        for line in ("Trip complete", "Safe trip", "Shutout", "You wins!"):
            assert line in html
        expected = 1000 + 400 + 300 + 500
        assert await _scores(alice["id"]) == [{"score": expected, "opponent": "CPU", "won": 1, "game": "mille"}]

        # Seeing the result again returns to the lobby without saving twice.
        assert state_of((await client.get(PAGE)).text) == "lobby"
        assert mille.get_game(alice["id"]) is None
        assert len(await _scores(alice["id"])) == 1

        # Further moves on a finished game do nothing.
        await client.post(f"{PAGE}/play", data={"card_index": 0})


@pytest.mark.asyncio
async def test_cpu_can_win(alice):
    game = stack(alice["id"], human=[D(25), D(50)], cpu=[D(100)], deck=[D(75), END_OF_LIMIT], miles=250)
    game.cpu.rolling, game.cpu.miles = True, 900
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/discard", data={"card_index": 0})
        assert game.winner == "CPU"
        assert game.human.hand == [D(50)]                # no draw after the game ended
        html = (await client.get(PAGE)).text

    assert state_of(html) == "game_over" and "CPU wins!" in html
    assert await _scores(alice["id"]) == [{"score": 250, "opponent": "CPU", "won": 0, "game": "mille"}]


@pytest.mark.asyncio
async def test_cards_running_out_ends_the_game_on_points(alice):
    """Human is out of cards with the deck gone: the CPU plays out its hand, then scores decide."""
    game = stack(alice["id"], human=[D(25)], cpu=[D(100), D(50)], deck=[], rolling=True, miles=500)
    game.cpu.rolling, game.cpu.miles = True, 100
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
        assert game.winner is None and game.human.hand == [] and game.cpu.hand == [D(50)]

        html = (await client.get(PAGE)).text

    assert game.cpu.hand == [] and game.cpu.miles == 250
    assert game.winner == "You"
    assert state_of(html) == "game_over"
    # No trip bonus: nobody reached 1000.
    assert await _scores(alice["id"]) == [{"score": 525, "opponent": "CPU", "won": 1, "game": "mille"}]


@pytest.mark.asyncio
async def test_tie_on_points_goes_to_the_human(alice):
    game = stack(alice["id"], human=[D(25)], cpu=[], deck=[], rolling=True, miles=75)
    game.cpu.miles = 100
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
    assert game.winner == "You"


@pytest.mark.asyncio
async def test_cpu_with_no_cards_just_passes(alice):
    game = stack(alice["id"], human=[ROLL, D(25), D(50)], cpu=[], deck=[])
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
        await client.post(f"{PAGE}/play", data={"card_index": 0})
    assert game.human.miles == 25 and game.winner is None


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_high_scores_show_best_score_and_record(alice):
    admin = await auth.get_user(1)
    await mille.save_score(alice["id"], 800, "CPU", True)
    await mille.save_score(alice["id"], 2200, "CPU", True)
    await mille.save_score(alice["id"], 150, "CPU", False)
    await mille.save_score(admin["id"], 900, "alice", False)
    await mille.save_score(admin["id"], 5000, "CPU", True, game="othergame")

    rows = await mille.get_high_scores()
    assert rows == [
        {"username": "alice", "best_score": 2200, "games_played": 3, "wins": 2},
        {"username": "admin", "best_score": 900, "games_played": 1, "wins": 0},
    ]

    async with await client_for(alice["id"]) as client:
        html = (await client.get(PAGE)).text
    assert "High Scores" in html and "2200" in html and "2 / 1" in html and "5000" not in html


@pytest.mark.asyncio
async def test_finishing_a_game_counts_towards_file_access(alice):
    assert (await auth.check_file_access(alice))["has_game"] is False
    stack(alice["id"], human=[D(100)], cpu=[], deck=[], rolling=True, miles=900)
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
        await client.get(PAGE)
    assert (await auth.check_file_access(alice))["has_game"] is True


@pytest.mark.asyncio
async def test_games_are_private_to_their_player(alice):
    bob = await auth.register_user("bob", "password123")
    game = stack(alice["id"], human=[ROLL, D(25)], cpu=[ROLL], deck=[D(50), D(75)])
    async with await client_for(bob["id"]) as client:
        assert state_of((await client.get(PAGE)).text) == "lobby"
        await client.post(f"{PAGE}/play", data={"card_index": 0})
    assert game.human.hand == [ROLL, D(25)] and not game.human.rolling


@pytest.mark.asyncio
async def test_cpu_wins_on_points_after_playing_out_its_hand(alice):
    """The CPU's leftover hand includes a card it can only discard."""
    game = stack(alice["id"], human=[D(25)], cpu=[D(100), REPAIRS], deck=[], rolling=True)
    game.cpu.rolling, game.cpu.miles = True, 400
    async with await client_for(alice["id"]) as client:
        await client.post(f"{PAGE}/play", data={"card_index": 0})
        html = (await client.get(PAGE)).text

    assert game.cpu.hand == [] and game.cpu.miles == 500
    assert "CPU discards a card." in game.messages
    assert game.winner == "CPU" and "CPU wins!" in html
    assert await _scores(alice["id"]) == [{"score": 25, "opponent": "CPU", "won": 0, "game": "mille"}]

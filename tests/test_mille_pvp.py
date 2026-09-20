"""Mille Bornes player-vs-player: invitations, turn order, coup fourré, endings."""

import pytest

from lib import auth, mille
from tests.helpers import client_for
from tests.test_mille_routes import PAGE, _scores, state_of
from tests.test_mille_rules import ACCIDENT, ACE, D, ROLL


@pytest.fixture
async def players():
    await auth.register_user("admin", "password123")
    alice = await auth.register_user("alice", "password123")
    bob = await auth.register_user("bob", "password123")
    return alice, bob


def pvp_state(html: str) -> str:
    if "Game Over" in html:
        return "pvp_game_over"
    return state_of(html)


def stack(alice, bob, hand1, hand2, deck, turn=None):
    """Start alice (player 1) vs bob with known cards."""
    game = mille.new_pvp_game(alice["id"], "alice", bob["id"], "bob")
    game.player1.hand, game.player2.hand, game.deck = list(hand1), list(hand2), list(deck)
    if turn is not None:
        game.current_turn = turn["id"]
    return game


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invite_accept_starts_a_game(players):
    alice, bob = players
    mille.new_game(alice["id"])
    mille.remove_game(alice["id"])
    mille.new_game(bob["id"])          # bob is idling in a CPU game? then he cannot be invited

    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        assert mille.get_invite_from(alice["id"]) is None
        assert "already in a game" in (await a.get(PAGE)).text

        mille.remove_game(bob["id"])
        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        waiting = (await a.get(PAGE)).text
        assert state_of(waiting) == "waiting_invite" and "bob" in waiting

        lobby = (await b.get(PAGE)).text
        assert "Incoming Challenge" in lobby and "alice" in lobby

        await b.post(f"{PAGE}/invite/accept", data={"from_user_id": alice["id"]})

        game = mille.get_pvp_game(alice["id"])
        assert game is not None and game is mille.get_pvp_game(bob["id"])
        assert mille.get_invite_from(alice["id"]) is None
        assert (game.player1.name, game.player2.name) == ("alice", "bob")
        assert game.current_turn == alice["id"]          # the challenger moves first
        assert state_of((await a.get(PAGE)).text) == "active"
        assert state_of((await b.get(PAGE)).text) == "pvp_waiting"


@pytest.mark.asyncio
async def test_accepting_abandons_both_players_cpu_games(players):
    alice, bob = players
    mille.create_invite(alice["id"], "alice", bob["id"], "bob")
    mille.new_game(alice["id"])
    mille.new_game(bob["id"])
    async with await client_for(bob["id"]) as b:
        await b.post(f"{PAGE}/invite/accept", data={"from_user_id": alice["id"]})
    assert mille.get_game(alice["id"]) is None and mille.get_game(bob["id"]) is None
    assert mille.get_pvp_game(bob["id"]) is not None


@pytest.mark.asyncio
async def test_decline_and_cancel(players):
    alice, bob = players
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        await b.post(f"{PAGE}/invite/decline", data={"from_user_id": alice["id"]})
        assert mille.get_invite_from(alice["id"]) is None
        html = (await a.get(PAGE)).text
        assert "bob declined your challenge." in html
        assert "declined" not in (await a.get(PAGE)).text          # shown once

        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        await a.post(f"{PAGE}/invite/cancel")
        assert mille.get_invite_to(bob["id"]) is None
        assert "Incoming Challenge" not in (await b.get(PAGE)).text


@pytest.mark.asyncio
async def test_unanswered_invite_expires(players, monkeypatch):
    alice, bob = players
    now = [5_000.0]
    monkeypatch.setattr(mille.time, "time", lambda: now[0])
    async with await client_for(alice["id"]) as a:
        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        assert "Expires in 60s" in (await a.get(PAGE)).text
        now[0] += 45
        assert "Expires in 15s" in (await a.get(PAGE)).text
        now[0] += 20
        html = (await a.get(PAGE)).text
    assert state_of(html) == "lobby" and "bob did not respond" in html


@pytest.mark.asyncio
async def test_a_new_invite_replaces_the_previous_one(players):
    alice, bob = players
    carol = await auth.register_user("carol", "password123")
    async with await client_for(alice["id"]) as a:
        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        await a.post(f"{PAGE}/invite", data={"to_user_id": carol["id"]})
    assert mille.get_invite_to(bob["id"]) is None
    assert mille.get_invite_to(carol["id"]).from_user_id == alice["id"]


@pytest.mark.asyncio
async def test_invites_that_must_be_refused(players):
    alice, bob = players
    async with await client_for(alice["id"]) as a:
        # Playing yourself would let one person post any score they like.
        await a.post(f"{PAGE}/invite", data={"to_user_id": alice["id"]})
        assert mille.get_invite_from(alice["id"]) is None

        await a.post(f"{PAGE}/invite", data={"to_user_id": 9999})
        assert mille.get_invite_from(alice["id"]) is None

        mille.new_game(alice["id"])                      # busy people do not send invites
        await a.post(f"{PAGE}/invite", data={"to_user_id": bob["id"]})
        assert mille.get_invite_from(alice["id"]) is None


@pytest.mark.asyncio
async def test_only_the_invited_player_can_answer(players):
    alice, bob = players
    carol = await auth.register_user("carol", "password123")
    mille.create_invite(alice["id"], "alice", bob["id"], "bob")
    async with await client_for(carol["id"]) as c:
        await c.post(f"{PAGE}/invite/accept", data={"from_user_id": alice["id"]})
        await c.post(f"{PAGE}/invite/decline", data={"from_user_id": alice["id"]})
    assert mille.get_invite_from(alice["id"]) is not None
    assert mille.get_pvp_game(carol["id"]) is None and mille.get_pvp_game(alice["id"]) is None


@pytest.mark.asyncio
async def test_cannot_accept_when_either_side_is_already_playing(players):
    alice, bob = players
    carol = await auth.register_user("carol", "password123")
    mille.create_invite(alice["id"], "alice", bob["id"], "bob")
    existing = mille.new_pvp_game(alice["id"], "alice", carol["id"], "carol")
    async with await client_for(bob["id"]) as b:
        await b.post(f"{PAGE}/invite/accept", data={"from_user_id": alice["id"]})
    assert mille.get_pvp_game(bob["id"]) is None
    assert mille.get_pvp_game(alice["id"]) is existing
    assert mille.get_invite_from(alice["id"]) is None


@pytest.mark.asyncio
async def test_lobby_lists_only_available_opponents(players):
    alice, bob = players
    carol = await auth.register_user("carol", "password123")
    dave = await auth.register_user("dave", "password123")
    for user in (bob, carol, dave):
        await auth.update_last_seen(user["id"])
    mille.new_game(carol["id"])
    mille.create_invite(dave["id"], "dave", 9999, "nobody")

    async with await client_for(alice["id"]) as a:
        html = (await a.get(PAGE)).text
    section = html.split("Online Players")[1]
    assert "bob" in section
    assert "carol" not in section and "dave" not in section and "alice" not in section


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_play_passes_the_turn_and_draws_for_the_opponent(players):
    alice, bob = players
    game = stack(alice, bob, [ROLL, D(25)], [D(50)], deck=[D(75), D(100)])
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})

        assert game.player1.rolling and game.player1.hand == [D(25)]
        assert game.current_turn == bob["id"]
        assert game.player2.hand == [D(50), D(100)]
        assert game.messages == ["alice plays Roll and starts moving!"]
        assert state_of((await a.get(PAGE)).text) == "pvp_waiting"
        assert state_of((await b.get(PAGE)).text) == "active"


@pytest.mark.asyncio
async def test_discard_passes_the_turn(players):
    alice, bob = players
    game = stack(alice, bob, [D(200), D(25)], [D(50)], deck=[D(75)])
    async with await client_for(alice["id"]) as a:
        await a.post(f"{PAGE}/pvp/discard", data={"card_index": 0})
    assert game.player1.hand == [D(25)]
    assert game.current_turn == bob["id"] and game.player2.hand == [D(50), D(75)]
    assert game.messages == ["alice discards a card."]      # does not reveal which


@pytest.mark.asyncio
async def test_out_of_turn_illegal_and_out_of_range_moves_change_nothing(players):
    alice, bob = players
    game = stack(alice, bob, [D(100), ROLL], [ROLL], deck=[D(75), D(25)])
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await b.post(f"{PAGE}/pvp/play", data={"card_index": 0})        # not bob's turn
        await b.post(f"{PAGE}/pvp/discard", data={"card_index": 0})
        assert game.player2.hand == [ROLL] and not game.player2.rolling

        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})        # cannot drive yet
        assert game.messages == ["Can't play 100 mi right now."]
        for index in (-1, 2):
            await a.post(f"{PAGE}/pvp/play", data={"card_index": index})
            await a.post(f"{PAGE}/pvp/discard", data={"card_index": index})

    assert game.current_turn == alice["id"]
    assert game.player1.hand == [D(100), ROLL] and len(game.deck) == 2


@pytest.mark.asyncio
async def test_outsiders_cannot_touch_a_game(players):
    alice, bob = players
    carol = await auth.register_user("carol", "password123")
    game = stack(alice, bob, [ROLL], [ROLL], deck=[D(75)])
    async with await client_for(carol["id"]) as c:
        for path, data in (("play", {"card_index": 0}), ("discard", {"card_index": 0}),
                           ("coup", {"accept": "yes"}), ("quit", {})):
            assert (await c.post(f"{PAGE}/pvp/{path}", data=data)).status_code == 302
    assert mille.get_pvp_game(alice["id"]) is game and game.winner is None
    assert game.player1.hand == [ROLL]


# ---------------------------------------------------------------------------
# Coup fourré
# ---------------------------------------------------------------------------

async def _alice_hits_bob(alice, bob, client):
    game = stack(alice, bob, [ACCIDENT, D(25)], [ACE, D(50)], deck=[D(75), D(100)])
    game.player1.rolling = game.player2.rolling = True
    await client.post(f"{PAGE}/pvp/play", data={"card_index": 0})
    return game


@pytest.mark.asyncio
async def test_hazard_on_a_player_holding_the_safety_pauses_for_their_answer(players):
    alice, bob = players
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        game = await _alice_hits_bob(alice, bob, a)

        assert game.coup_fourre_pending == bob["id"] and game.coup_fourre_hazard == "Accident"
        assert game.player2.hazard == "Accident"
        assert game.player2.hand == [ACE, D(50)]                 # nobody draws yet
        assert pvp_state((await b.get(PAGE)).text) == "coup_fourre"
        assert pvp_state((await a.get(PAGE)).text) == "pvp_waiting"

        # Neither side can move until it is answered, and only bob may answer.
        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})
        await b.post(f"{PAGE}/pvp/play", data={"card_index": 1})
        await a.post(f"{PAGE}/pvp/coup", data={"accept": "yes"})
        assert game.coup_fourre_pending == bob["id"]
        assert game.player1.hand == [D(25)] and game.player2.hand == [ACE, D(50)]


@pytest.mark.asyncio
async def test_accepting_coup_fourre_takes_the_turn(players):
    alice, bob = players
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        game = await _alice_hits_bob(alice, bob, a)
        await b.post(f"{PAGE}/pvp/coup", data={"accept": "yes"})

    assert game.coup_fourre_pending is None and game.coup_fourre_hazard is None
    assert game.player2.coups == 1 and game.player2.safeties == ["Driving Ace"]
    assert game.player2.hazard is None and game.player2.can_move
    assert game.current_turn == bob["id"]
    assert game.player2.hand == [D(50), D(100)]
    assert "bob plays Coup Fourre: Driving Ace!" in game.messages


@pytest.mark.asyncio
async def test_declining_coup_fourre_still_gives_the_victim_their_turn(players):
    """The attacker has had their move; declining must not hand them another."""
    alice, bob = players
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        game = await _alice_hits_bob(alice, bob, a)
        await b.post(f"{PAGE}/pvp/coup", data={"accept": "no"})

    assert game.player2.hazard == "Accident" and game.player2.coups == 0
    assert game.current_turn == bob["id"]
    assert game.player2.hand == [ACE, D(50), D(100)]
    assert game.player1.hand == [D(25)]


# ---------------------------------------------------------------------------
# Endings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_winning_is_shown_to_both_players_and_scored_once(players):
    alice, bob = players
    game = stack(alice, bob, [D(100), D(25)], [D(50)], deck=[D(75)])
    game.player1.rolling, game.player1.miles, game.player2.miles = True, 900, 300

    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})
        assert game.winner == "alice"
        assert game.player2.hand == [D(50)]                       # no draw after the end

        # The winner looks twice before the loser has looked at all.
        assert pvp_state((await a.get(PAGE)).text) == "pvp_game_over"
        assert pvp_state((await a.get(PAGE)).text) == "lobby"

        html = (await b.get(PAGE)).text
        assert pvp_state(html) == "pvp_game_over" and "alice wins!" in html
        assert pvp_state((await b.get(PAGE)).text) == "lobby"

    assert await _scores(alice["id"]) == [{"score": 1000 + 400 + 300, "opponent": "bob", "won": 1, "game": "mille"}]
    assert await _scores(bob["id"]) == [{"score": 300, "opponent": "alice", "won": 0, "game": "mille"}]
    assert mille.get_pvp_game(alice["id"]) is None and mille.get_pvp_game(bob["id"]) is None
    assert mille._pvp_games == {}


@pytest.mark.asyncio
async def test_back_to_lobby_does_not_hide_the_result_from_the_other_player(players):
    alice, bob = players
    game = stack(alice, bob, [D(100)], [D(50)], deck=[D(75)])
    game.player1.rolling, game.player1.miles = True, 900
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})
        await a.get(PAGE)
        await a.post(f"{PAGE}/pvp/quit")                           # the "Back to Lobby" button
        assert pvp_state((await a.get(PAGE)).text) == "lobby"
        assert pvp_state((await b.get(PAGE)).text) == "pvp_game_over"


@pytest.mark.asyncio
async def test_forfeit_ends_the_game_for_both_and_tells_the_opponent(players):
    alice, bob = players
    stack(alice, bob, [ROLL], [ROLL], deck=[D(75)])
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/pvp/quit")
        assert mille.get_pvp_game(alice["id"]) is None and mille.get_pvp_game(bob["id"]) is None
        html = (await b.get(PAGE)).text
        assert pvp_state(html) == "lobby" and "alice forfeited the game. You win!" in html
        assert "forfeited" not in (await a.get(PAGE)).text
    # As the code stands a forfeit records no result for either player.
    assert await _scores(alice["id"]) == [] and await _scores(bob["id"]) == []


@pytest.mark.asyncio
async def test_a_player_with_no_cards_is_skipped_rather_than_stalling_the_game(players):
    """Deck gone, bob already out of cards: alice must be able to finish her hand."""
    alice, bob = players
    game = stack(alice, bob, [D(25), D(50)], [], deck=[])
    game.player1.rolling = True
    async with await client_for(alice["id"]) as a:
        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})
        assert game.winner is None
        assert game.current_turn == alice["id"]
        assert state_of((await a.get(PAGE)).text) == "active"

        await a.post(f"{PAGE}/pvp/discard", data={"card_index": 0})
    assert game.winner == "alice"                                   # 25 miles to 0, on points


@pytest.mark.asyncio
async def test_cards_running_out_ends_on_points_with_ties_to_player_one(players):
    alice, bob = players
    game = stack(alice, bob, [D(25)], [], deck=[])
    game.player2.miles = 500
    async with await client_for(alice["id"]) as a:
        await a.post(f"{PAGE}/pvp/discard", data={"card_index": 0})
    assert game.winner == "bob"

    mille.remove_pvp_game(game.game_id)
    game = stack(alice, bob, [D(25)], [], deck=[])
    game.player1.miles = game.player2.miles = 200
    async with await client_for(alice["id"]) as a:
        await a.post(f"{PAGE}/pvp/discard", data={"card_index": 0})
    assert game.winner == "alice"


@pytest.mark.asyncio
async def test_coup_fourre_with_your_last_card_hands_play_back(players):
    """Deck gone and the safety was bob's only card: alice plays on rather than the game stalling."""
    alice, bob = players
    game = stack(alice, bob, [ACCIDENT, D(25)], [ACE], deck=[])
    game.player1.rolling = game.player2.rolling = True
    async with await client_for(alice["id"]) as a, await client_for(bob["id"]) as b:
        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})
        await b.post(f"{PAGE}/pvp/coup", data={"accept": "yes"})
        assert game.player2.coups == 1 and game.player2.hand == []
        assert game.winner is None and game.current_turn == alice["id"]

        await a.post(f"{PAGE}/pvp/play", data={"card_index": 0})
    # Both hands empty: bob's safety (100) and coup fourré (300) beat alice's 25 miles.
    assert game.winner == "bob"


def test_leaving_a_finished_game_one_player_at_a_time():
    game = mille.new_pvp_game(1, "alice", 2, "bob")
    mille.leave_pvp_game(1)
    assert mille.get_pvp_game(1) is None
    assert mille.get_pvp_game(2) is game             # still there for bob
    mille.leave_pvp_game(1)                          # leaving twice is harmless
    mille.leave_pvp_game(2)
    assert mille.get_pvp_game(2) is None and mille._pvp_games == {}


@pytest.mark.asyncio
async def test_player_two_wins_by_reaching_1000(players):
    alice, bob = players
    game = stack(alice, bob, [D(25)], [D(100)], deck=[D(75)], turn=bob)
    game.player2.rolling, game.player2.miles = True, 900
    async with await client_for(bob["id"]) as b:
        await b.post(f"{PAGE}/pvp/play", data={"card_index": 0})
        html = (await b.get(PAGE)).text
    # On his own result page bob is "You".
    assert game.winner == "bob" and "You wins!" in html and "Trip complete" in html


@pytest.mark.asyncio
async def test_lobby_hides_players_who_are_in_a_pvp_game(players):
    alice, bob = players
    carol = await auth.register_user("carol", "password123")
    dave = await auth.register_user("dave", "password123")
    for user in (bob, carol, dave):
        await auth.update_last_seen(user["id"])
    mille.new_pvp_game(bob["id"], "bob", carol["id"], "carol")
    async with await client_for(alice["id"]) as a:
        section = (await a.get(PAGE)).text.split("Online Players")[1]
    assert "dave" in section and "bob" not in section and "carol" not in section

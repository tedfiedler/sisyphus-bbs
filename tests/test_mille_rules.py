"""Mille Bornes rules engine: what may be played, what it does, scoring, and the CPU's choices."""

from collections import Counter

import pytest

from lib import mille
from lib.mille import (
    Player, apply_coup_fourre, build_deck, calc_score, can_play, card_name,
    cpu_choose, do_play,
)

ACCIDENT, OUT_OF_GAS, FLAT = ("hazard", "Accident"), ("hazard", "Out of Gas"), ("hazard", "Flat Tire")
STOP, SPEED_LIMIT = ("hazard", "Stop"), ("hazard", "Speed Limit")
ROLL, END_OF_LIMIT = ("remedy", "Roll"), ("remedy", "End of Limit")
REPAIRS, GASOLINE, SPARE = ("remedy", "Repairs"), ("remedy", "Gasoline"), ("remedy", "Spare Tire")
ACE, TANK, PUNCTURE, RIGHT_OF_WAY = (
    ("safety", "Driving Ace"), ("safety", "Extra Tank"),
    ("safety", "Puncture-Proof"), ("safety", "Right of Way"),
)


def D(miles):
    return ("distance", miles)


def player(name="P", **attrs):
    p = Player(name)
    for key, value in attrs.items():
        setattr(p, key, value)
    return p


# ---------------------------------------------------------------------------
# Deck and dealing
# ---------------------------------------------------------------------------

def test_deck_composition():
    deck = build_deck()
    counts = Counter(deck)
    assert len(deck) == 106
    assert counts[D(25)] == counts[D(50)] == counts[D(75)] == 10
    assert counts[D(100)] == 12 and counts[D(200)] == 4
    assert counts[ROLL] == 14
    assert counts[STOP] == 5 and counts[SPEED_LIMIT] == 4
    assert counts[ACCIDENT] == counts[OUT_OF_GAS] == counts[FLAT] == 3
    for remedy in (REPAIRS, GASOLINE, SPARE, END_OF_LIMIT):
        assert counts[remedy] == 6
    for safety in (ACE, TANK, PUNCTURE, RIGHT_OF_WAY):
        assert counts[safety] == 1


def test_deck_is_shuffled():
    assert build_deck() != build_deck()


def test_every_hazard_has_a_remedy_and_a_safety_in_the_deck():
    cards = set(build_deck())
    for hazard, remedy in mille.REMEDY_FOR.items():
        assert ("hazard", hazard) in cards and ("remedy", remedy) in cards
        assert ("safety", mille.SAFETY_FOR[hazard]) in cards


def test_new_game_deals_seven_to_human_six_to_cpu():
    game = mille.new_game(1)
    assert len(game.human.hand) == 7 and len(game.cpu.hand) == 6
    assert len(game.deck) == 106 - 13
    assert Counter(game.deck + game.human.hand + game.cpu.hand) == Counter(build_deck())
    assert mille.get_game(1) is game
    assert game.winner is None and game.coup_fourre_pending is None


def test_new_game_replaces_the_old_one_and_games_are_per_user():
    first = mille.new_game(1)
    other = mille.new_game(2)
    second = mille.new_game(1)
    assert mille.get_game(1) is second is not first
    assert mille.get_game(2) is other
    mille.remove_game(1)
    assert mille.get_game(1) is None and mille.get_game(2) is other
    mille.remove_game(1)  # removing twice is harmless


def test_card_name():
    assert card_name(D(75)) == "75 mi"
    assert card_name(ROLL) == "Roll"


# ---------------------------------------------------------------------------
# can_play
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("attrs, card, expected", [
    # Distance needs a green light...
    ({}, D(25), False),
    ({"rolling": True}, D(25), True),
    ({"rolling": True, "hazard": "Accident"}, D(25), False),
    # ...which Right of Way provides permanently, but not through a hazard.
    ({"safeties": ["Right of Way"]}, D(100), True),
    ({"safeties": ["Right of Way"], "hazard": "Flat Tire"}, D(100), False),
    # Speed limit caps at 50.
    ({"rolling": True, "speed_limited": True}, D(50), True),
    ({"rolling": True, "speed_limited": True}, D(75), False),
    ({"rolling": True, "speed_limited": True, "safeties": ["Right of Way"]}, D(200), True),
    # At most two 200s per game.
    ({"rolling": True, "count_200": 1}, D(200), True),
    ({"rolling": True, "count_200": 2}, D(200), False),
    ({"rolling": True, "count_200": 2}, D(100), True),
    # Must land on 1000 exactly.
    ({"rolling": True, "miles": 950}, D(50), True),
    ({"rolling": True, "miles": 950}, D(75), False),
    ({"rolling": True, "miles": 1000}, D(25), False),
])
def test_can_play_distance(attrs, card, expected):
    assert can_play(card, player(**attrs), player("Opp")) is expected


@pytest.mark.parametrize("attrs, card, expected", [
    ({}, ROLL, True),
    ({"rolling": True}, ROLL, False),
    ({"hazard": "Accident"}, ROLL, False),           # fix the car first
    ({"safeties": ["Right of Way"]}, ROLL, False),   # never needed
    ({"speed_limited": True}, END_OF_LIMIT, True),
    ({}, END_OF_LIMIT, False),
    ({"speed_limited": True, "safeties": ["Right of Way"]}, END_OF_LIMIT, False),
    ({"hazard": "Accident"}, REPAIRS, True),
    ({"hazard": "Accident"}, GASOLINE, False),
    ({"hazard": "Out of Gas"}, GASOLINE, True),
    ({"hazard": "Flat Tire"}, SPARE, True),
    ({}, REPAIRS, False),
])
def test_can_play_remedy(attrs, card, expected):
    assert can_play(card, player(**attrs), player("Opp")) is expected


@pytest.mark.parametrize("opp_attrs, card, expected", [
    # Breakdowns only land on a car that is moving and not already broken.
    ({"rolling": True}, ACCIDENT, True),
    ({}, ACCIDENT, False),
    ({"rolling": True, "hazard": "Flat Tire"}, ACCIDENT, False),
    ({"rolling": True, "safeties": ["Driving Ace"]}, ACCIDENT, False),
    ({"rolling": True, "safeties": ["Driving Ace"]}, OUT_OF_GAS, True),
    ({"rolling": True, "safeties": ["Extra Tank"]}, OUT_OF_GAS, False),
    ({"rolling": True, "safeties": ["Puncture-Proof"]}, FLAT, False),
    ({"safeties": ["Right of Way"]}, ACCIDENT, True),   # moving by right of way
    # Stop needs a moving target without Right of Way.
    ({"rolling": True}, STOP, True),
    ({}, STOP, False),
    ({"rolling": True, "safeties": ["Right of Way"]}, STOP, False),
    # Speed Limit can be laid on a stationary car, but not twice.
    ({}, SPEED_LIMIT, True),
    ({"speed_limited": True}, SPEED_LIMIT, False),
    ({"safeties": ["Right of Way"]}, SPEED_LIMIT, False),
])
def test_can_play_hazard(opp_attrs, card, expected):
    assert can_play(card, player(), player("Opp", **opp_attrs)) is expected


@pytest.mark.parametrize("safety", [ACE, TANK, PUNCTURE, RIGHT_OF_WAY])
def test_safeties_are_always_playable(safety):
    assert can_play(safety, player(hazard="Accident"), player("Opp"))
    assert can_play(safety, player(rolling=True), player("Opp"))


def test_unknown_card_type_is_never_playable():
    assert can_play(("joker", "?"), player(rolling=True), player("Opp")) is False


# ---------------------------------------------------------------------------
# do_play
# ---------------------------------------------------------------------------

def test_distance_adds_miles_and_counts_200s():
    me = player(rolling=True, miles=100)
    assert do_play(D(200), me, player("Opp")) == "P drives 200 mi! (300 total)"
    assert (me.miles, me.count_200) == (300, 1)
    do_play(D(75), me, player("Opp"))
    assert (me.miles, me.count_200) == (375, 1)


def test_roll_and_end_of_limit():
    me = player(speed_limited=True)
    do_play(ROLL, me, player("Opp"))
    assert me.rolling and me.speed_limited
    do_play(END_OF_LIMIT, me, player("Opp"))
    assert me.rolling and not me.speed_limited


@pytest.mark.parametrize("hazard, remedy", [(ACCIDENT, REPAIRS), (OUT_OF_GAS, GASOLINE), (FLAT, SPARE)])
def test_breakdown_then_remedy_then_roll(hazard, remedy):
    attacker, victim = player("A"), player("V", rolling=True)
    assert do_play(hazard, attacker, victim) == f"A plays {hazard[1]} on V!"
    assert victim.hazard == hazard[1] and not victim.rolling and not victim.can_move

    do_play(remedy, victim, attacker)
    # Repaired, but still needs a Roll before driving again.
    assert victim.hazard is None and not victim.can_move
    assert can_play(ROLL, victim, attacker)
    do_play(ROLL, victim, attacker)
    assert victim.can_move


def test_remedy_with_right_of_way_needs_no_roll():
    victim = player("V", hazard="Accident", safeties=["Right of Way"])
    do_play(REPAIRS, victim, player("A"))
    assert victim.can_move


def test_stop_and_speed_limit():
    victim = player("V", rolling=True)
    do_play(STOP, player("A"), victim)
    assert not victim.rolling and victim.hazard is None
    do_play(SPEED_LIMIT, player("A"), victim)
    assert victim.speed_limited


@pytest.mark.parametrize("safety, hazard", [(ACE, "Accident"), (TANK, "Out of Gas"), (PUNCTURE, "Flat Tire")])
def test_safety_clears_its_own_hazard_only(safety, hazard):
    me = player(hazard=hazard)
    assert do_play(safety, me, player("Opp")) == f"P plays {safety[1]}!"
    assert me.hazard is None and safety[1] in me.safeties

    other = "Flat Tire" if hazard != "Flat Tire" else "Accident"
    unlucky = player(hazard=other)
    do_play(safety, unlucky, player("Opp"))
    assert unlucky.hazard == other


def test_right_of_way_starts_the_car_and_lifts_the_limit():
    me = player(speed_limited=True)
    do_play(RIGHT_OF_WAY, me, player("Opp"))
    assert me.rolling and not me.speed_limited and me.can_move


def test_messages_address_the_human_player_in_the_second_person():
    """ "You play", never "You plays"; and the CPU does things "on you", not "on You"."""
    you = player("You", second_person=True, rolling=True)
    cpu = player("CPU", rolling=True)

    assert do_play(ROLL, player("You", second_person=True), cpu) == "You play Roll and start moving!"
    assert do_play(D(100), you, cpu) == "You drive 100 mi! (100 total)"
    assert do_play(ACE, you, cpu) == "You play Driving Ace!"
    assert do_play(ACCIDENT, you, cpu) == "You play Accident on CPU!"
    assert do_play(STOP, cpu, you) == "CPU plays Stop on you!"

    you.hazard, you.speed_limited = "Flat Tire", True
    assert do_play(SPARE, you, cpu) == "You play Spare Tire - hazard cleared!"
    assert do_play(END_OF_LIMIT, you, cpu) == "You play End of Limit!"


def test_named_players_are_described_in_the_third_person():
    alice, bob = player("alice"), player("bob", rolling=True)
    assert do_play(ROLL, alice, bob) == "alice plays Roll and starts moving!"
    assert do_play(D(25), alice, bob) == "alice drives 25 mi! (25 total)"
    assert do_play(ACCIDENT, alice, bob) == "alice plays Accident on bob!"


def test_a_user_who_is_literally_named_you_is_still_third_person_in_pvp():
    game = mille.new_pvp_game(1, "You", 2, "bob")
    assert do_play(ROLL, game.player1, game.player2) == "You plays Roll and starts moving!"
    assert mille.new_game(3).human.second_person is True


# ---------------------------------------------------------------------------
# Coup fourré
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hazard, safety", [
    (ACCIDENT, ACE), (OUT_OF_GAS, TANK), (FLAT, PUNCTURE), (STOP, RIGHT_OF_WAY), (SPEED_LIMIT, RIGHT_OF_WAY),
])
def test_coup_fourre_undoes_the_hazard(hazard, safety):
    attacker = player("A")
    victim = player("V", rolling=True, hand=[safety, D(25)])
    do_play(hazard, attacker, victim)

    apply_coup_fourre(victim, hazard[1])

    assert victim.hand == [D(25)]
    assert victim.safeties == [safety[1]]
    assert victim.coups == 1
    assert victim.hazard is None and victim.rolling and not victim.speed_limited
    assert victim.can_move


def test_coup_fourre_without_the_safety_in_hand_is_an_error():
    with pytest.raises(ValueError):
        apply_coup_fourre(player(rolling=True, hand=[D(25)]), "Accident")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def test_score_is_miles_when_nothing_else_happened():
    assert calc_score(player("A", miles=475), player("B", miles=600), "B") == 475


def test_safeties_and_coups():
    me = player("A", miles=300, safeties=["Driving Ace", "Extra Tank"], coups=1)
    assert calc_score(me, player("B", miles=50), None) == 300 + 200 + 300


def test_all_four_safeties_bonus():
    me = player("A", safeties=["Driving Ace", "Extra Tank", "Puncture-Proof", "Right of Way"])
    assert calc_score(me, player("B"), None) == 400 + 700


def test_trip_completed_safe_trip_and_shutout():
    winner = player("A", miles=1000)
    assert calc_score(winner, player("B", miles=25), "A") == 1000 + 400 + 300
    assert calc_score(winner, player("B", miles=0), "A") == 1000 + 400 + 300 + 500
    used_200 = player("A", miles=1000, count_200=2)
    assert calc_score(used_200, player("B", miles=25), "A") == 1000 + 400


def test_no_trip_bonus_for_loser_or_for_winning_short_of_1000():
    assert calc_score(player("A", miles=1000), player("B"), "B") == 1000
    # Won on points after the deck ran out, or by forfeit.
    assert calc_score(player("A", miles=900), player("B"), "A") == 900


# ---------------------------------------------------------------------------
# CPU decisions
# ---------------------------------------------------------------------------

def test_cpu_priority_order():
    opponent = player("Human", rolling=True)

    def choice(hand, **attrs):
        cpu = player("CPU", hand=hand, **attrs)
        action, index = cpu_choose(cpu, opponent)
        return action, hand[index]

    # safety > fix breakdown > Roll > distance > hazard > End of Limit
    assert choice([D(100), ACCIDENT, ACE], rolling=True) == ("play", ACE)
    assert choice([ROLL, REPAIRS, ACCIDENT], hazard="Accident") == ("play", REPAIRS)
    assert choice([ACCIDENT, D(100), ROLL]) == ("play", ROLL)
    assert choice([ACCIDENT, D(25), D(100), D(75)], rolling=True) == ("play", D(100))
    assert choice([END_OF_LIMIT, STOP], rolling=True, speed_limited=True) == ("play", STOP)
    assert choice([END_OF_LIMIT, D(75)], rolling=True, speed_limited=True) == ("play", END_OF_LIMIT)


def test_cpu_respects_speed_limit_when_picking_distance():
    cpu = player("CPU", rolling=True, speed_limited=True, hand=[D(200), D(50), D(25)])
    assert cpu_choose(cpu, player("Human")) == ("play", 1)


def test_cpu_discards_least_useful_card_when_stuck():
    human = player("Human")  # stationary: Stop and Accident cannot be played on them

    # An unplayable hazard goes before anything else...
    cpu = player("CPU", hazard="Flat Tire", hand=[D(100), ACCIDENT, REPAIRS])
    assert cpu_choose(cpu, human) == ("discard", 1)

    # ...then a dead 200 (two already played)...
    cpu = player("CPU", hazard="Flat Tire", count_200=2, hand=[D(25), D(200), REPAIRS])
    assert cpu_choose(cpu, human) == ("discard", 1)

    # ...then remedies it has no use for, then the smallest distance.
    cpu = player("CPU", hazard="Flat Tire", hand=[D(50), REPAIRS, D(25)])
    assert cpu_choose(cpu, human) == ("discard", 1)
    cpu = player("CPU", hazard="Flat Tire", hand=[D(50), D(25), D(75)])
    assert cpu_choose(cpu, human) == ("discard", 1)


def test_cpu_never_discards_a_safety_because_it_is_always_playable():
    cpu = player("CPU", hazard="Flat Tire", hand=[ACE])
    assert cpu_choose(cpu, player("Human")) == ("play", 0)


# ---------------------------------------------------------------------------
# Invites, flash messages, PvP bookkeeping
# ---------------------------------------------------------------------------

def test_invite_lifecycle():
    invite = mille.create_invite(1, "alice", 2, "bob")
    assert mille.get_invite_from(1) is invite
    assert mille.get_invite_to(2) is invite
    assert mille.get_invite_to(1) is None and mille.get_invite_from(2) is None

    replacement = mille.create_invite(1, "alice", 3, "carol")
    assert mille.get_invite_from(1) is replacement
    assert mille.get_invite_to(2) is None

    mille.cancel_invite(1)
    mille.cancel_invite(1)
    assert mille.get_invite_from(1) is None and mille.get_invite_to(3) is None


def test_invites_expire_and_tell_the_sender(monkeypatch):
    now = [1_000.0]
    monkeypatch.setattr(mille.time, "time", lambda: now[0])
    mille.create_invite(1, "alice", 2, "bob")

    now[0] += mille.INVITE_TIMEOUT - 1
    mille.expire_invites()
    assert mille.get_invite_from(1) is not None

    now[0] += 2
    mille.expire_invites()
    assert mille.get_invite_from(1) is None
    assert mille.pop_flash(1) == "bob did not respond to your challenge."
    assert mille.pop_flash(2) is None


def test_flash_is_one_shot():
    mille.set_flash(1, "first")
    mille.set_flash(1, "second")
    assert mille.pop_flash(1) == "second"
    assert mille.pop_flash(1) is None


def test_new_pvp_game():
    game = mille.new_pvp_game(1, "alice", 2, "bob")
    assert len(game.player1.hand) == 7 and len(game.player2.hand) == 6
    assert len(game.deck) == 93
    assert game.current_turn == 1
    assert mille.get_pvp_game(1) is game and mille.get_pvp_game(2) is game
    assert mille.get_pvp_game(3) is None

    me, opp, my_id, opp_id = mille.get_me_and_opponent(game, 2)
    assert (me.name, opp.name, my_id, opp_id) == ("bob", "alice", 2, 1)

    mille.remove_pvp_game(game.game_id)
    mille.remove_pvp_game(game.game_id)
    assert mille.get_pvp_game(1) is None and mille.get_pvp_game(2) is None

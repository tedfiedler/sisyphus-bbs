"""Mille Bornes — game logic for the web interface."""

import random
import time
import uuid
from dataclasses import dataclass, field

from lib.db import get_db

# Hazard -> Remedy
REMEDY_FOR = {
    "Accident": "Repairs",
    "Out of Gas": "Gasoline",
    "Flat Tire": "Spare Tire",
    "Stop": "Roll",
    "Speed Limit": "End of Limit",
}

# Hazard -> Safety
SAFETY_FOR = {
    "Accident": "Driving Ace",
    "Out of Gas": "Extra Tank",
    "Flat Tire": "Puncture-Proof",
    "Stop": "Right of Way",
    "Speed Limit": "Right of Way",
}


class Player:
    """Represent a Mille Bornes player with hand, miles, status effects, and safeties."""

    def __init__(self, name, second_person=False):
        """Initialize a player with an empty hand and default state.

        *second_person* marks the player the messages are addressed to (the
        human in a CPU game, shown as "You"). It is a flag rather than a
        check on the name because in PvP the name is a username, and
        somebody can register as "You".
        """
        self.name = name
        self.second_person = second_person
        self.hand = []
        self.miles = 0
        self.rolling = False
        self.hazard = None  # Accident, Out of Gas, Flat Tire, or None
        self.speed_limited = False
        self.safeties = []
        self.coups = 0
        self.count_200 = 0

    def verb(self, base):
        """Conjugate *base* for this player: "You play", "CPU plays"."""
        return base if self.second_person else f"{base}s"

    @property
    def as_object(self):
        """How a sentence refers to this player as its target: "on you", "on CPU"."""
        return "you" if self.second_person else self.name

    @property
    def can_move(self):
        """Return True if the player is able to play distance cards."""
        if self.hazard is not None:
            return False
        return self.rolling or "Right of Way" in self.safeties


def card_name(card):
    """Return a human-readable display name for a card tuple."""
    ctype, value = card
    return f"{value} mi" if ctype == "distance" else value


def build_deck():
    """Build and shuffle a standard 106-card Mille Bornes deck."""
    specs = [
        ("distance", 25, 10), ("distance", 50, 10), ("distance", 75, 10),
        ("distance", 100, 12), ("distance", 200, 4),
        ("hazard", "Accident", 3), ("hazard", "Out of Gas", 3),
        ("hazard", "Flat Tire", 3), ("hazard", "Speed Limit", 4),
        ("hazard", "Stop", 5),
        ("remedy", "Repairs", 6), ("remedy", "Gasoline", 6),
        ("remedy", "Spare Tire", 6), ("remedy", "End of Limit", 6),
        ("remedy", "Roll", 14),
        ("safety", "Driving Ace", 1), ("safety", "Extra Tank", 1),
        ("safety", "Puncture-Proof", 1), ("safety", "Right of Way", 1),
    ]
    deck = []
    for ctype, value, count in specs:
        deck.extend([(ctype, value)] * count)
    random.shuffle(deck)
    return deck


def can_play(card, player, opponent):
    """Return True if the given card can legally be played by the player."""
    ctype, value = card

    if ctype == "safety":
        return True

    if ctype == "distance":
        if not player.can_move:
            return False
        if player.speed_limited and "Right of Way" not in player.safeties and value > 50:
            return False
        if value == 200 and player.count_200 >= 2:
            return False
        if player.miles + value > 1000:
            return False
        return True

    if ctype == "remedy":
        if value == "Roll":
            return (not player.rolling and player.hazard is None
                    and "Right of Way" not in player.safeties)
        if value == "End of Limit":
            return player.speed_limited and "Right of Way" not in player.safeties
        hazard_map = {
            "Repairs": "Accident",
            "Gasoline": "Out of Gas",
            "Spare Tire": "Flat Tire",
        }
        return player.hazard == hazard_map.get(value)

    if ctype == "hazard":
        if value == "Speed Limit":
            return (not opponent.speed_limited
                    and "Right of Way" not in opponent.safeties)
        if value == "Stop":
            return (opponent.can_move
                    and "Right of Way" not in opponent.safeties)
        # Accident, Out of Gas, Flat Tire
        if not opponent.can_move or opponent.hazard is not None:
            return False
        return SAFETY_FOR.get(value) not in opponent.safeties

    return False


def do_play(card, player, opponent):
    """Execute a card play. Returns a complete sentence describing it."""
    ctype, value = card
    plays = f"{player.name} {player.verb('play')} {card_name(card)}"

    if ctype == "safety":
        player.safeties.append(value)
        if value == "Right of Way":
            player.rolling = True
            player.speed_limited = False
        elif value == "Driving Ace" and player.hazard == "Accident":
            player.hazard = None
        elif value == "Extra Tank" and player.hazard == "Out of Gas":
            player.hazard = None
        elif value == "Puncture-Proof" and player.hazard == "Flat Tire":
            player.hazard = None
        return f"{plays}!"

    if ctype == "distance":
        player.miles += value
        if value == 200:
            player.count_200 += 1
        return f"{player.name} {player.verb('drive')} {card_name(card)}! ({player.miles} total)"

    if ctype == "remedy":
        if value == "Roll":
            player.rolling = True
            return f"{plays} and {player.verb('start')} moving!"
        if value == "End of Limit":
            player.speed_limited = False
            return f"{plays}!"
        player.hazard = None
        player.rolling = False
        return f"{plays} - hazard cleared!"

    if ctype == "hazard":
        if value == "Speed Limit":
            opponent.speed_limited = True
        elif value == "Stop":
            opponent.rolling = False
        else:
            opponent.hazard = value
            opponent.rolling = False
        return f"{plays} on {opponent.as_object}!"

    return ""


def apply_coup_fourre(target, hazard_name):
    """Undo a hazard and play the matching safety as coup fourre."""
    safety = SAFETY_FOR[hazard_name]
    target.hand.remove(("safety", safety))
    target.safeties.append(safety)
    target.coups += 1
    # Undo hazard effects
    if hazard_name in ("Accident", "Out of Gas", "Flat Tire"):
        target.hazard = None
        target.rolling = True
    elif hazard_name == "Stop":
        target.rolling = True
    elif hazard_name == "Speed Limit":
        target.speed_limited = False
    # Right of Way extra effects
    if safety == "Right of Way":
        target.rolling = True
        target.speed_limited = False


def cpu_choose(cpu, opponent):
    """AI decision. Returns ("play"|"discard", card_index)."""
    playable = [(i, c) for i, c in enumerate(cpu.hand) if can_play(c, cpu, opponent)]

    if not playable:
        return ("discard", _worst_card(cpu, opponent))

    # Play safeties
    for i, c in playable:
        if c[0] == "safety":
            return ("play", i)

    # Fix our hazard
    for i, c in playable:
        if c[0] == "remedy" and c[1] not in ("Roll", "End of Limit"):
            return ("play", i)

    # Play Roll
    for i, c in playable:
        if c == ("remedy", "Roll"):
            return ("play", i)

    # Play distance (highest first)
    dist = [(i, c) for i, c in playable if c[0] == "distance"]
    if dist:
        dist.sort(key=lambda x: x[1][1], reverse=True)
        return ("play", dist[0][0])

    # Play hazards
    for i, c in playable:
        if c[0] == "hazard":
            return ("play", i)

    # End of Limit
    for i, c in playable:
        if c == ("remedy", "End of Limit"):
            return ("play", i)

    return ("play", playable[0][0])


def _worst_card(player, opponent):
    """Find index of least useful card to discard."""
    scores = []
    for i, (ctype, value) in enumerate(player.hand):
        if ctype == "safety":
            s = 1000
        elif ctype == "distance":
            s = value
            if value == 200 and player.count_200 >= 2:
                s = 0
        elif ctype == "remedy":
            s = 50 if can_play(("remedy", value), player, opponent) else 10
        elif ctype == "hazard":
            s = 30 if can_play(("hazard", value), player, opponent) else 0
        else:
            s = 0
        scores.append((s, i))
    scores.sort()
    return scores[0][1]


def calc_score(player, opponent, winner):
    """Calculate final score for a player including bonus points."""
    pts = player.miles
    pts += len(player.safeties) * 100
    if len(player.safeties) == 4:
        pts += 700
    pts += player.coups * 300
    if winner == player.name and player.miles == 1000:
        pts += 400
        if player.count_200 == 0:
            pts += 300
        if opponent.miles == 0:
            pts += 500
    return pts


# ---------------------------------------------------------------------------
# Web game state manager
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    """Hold the full state of a single-player (vs CPU) Mille Bornes game."""

    deck: list
    human: Player
    cpu: Player
    messages: list = field(default_factory=list)
    winner: str | None = None
    coup_fourre_pending: str | None = None  # hazard name if awaiting player decision
    score_saved: bool = False


_games: dict[int, GameState] = {}  # keyed by user_id


def new_game(user_id: int) -> GameState:
    """Create a new game for a user. Deals 7 to human (pre-draw), 6 to CPU."""
    deck = build_deck()
    human = Player("You", second_person=True)
    cpu = Player("CPU")
    for _ in range(6):
        human.hand.append(deck.pop())
        cpu.hand.append(deck.pop())
    # Pre-draw for human's first turn
    human.hand.append(deck.pop())
    game = GameState(deck=deck, human=human, cpu=cpu)
    _games[user_id] = game
    return game


def get_game(user_id: int) -> GameState | None:
    """Return the active single-player game for a user, or None."""
    return _games.get(user_id)


def remove_game(user_id: int) -> None:
    """Remove and discard the active single-player game for a user."""
    _games.pop(user_id, None)


# ---------------------------------------------------------------------------
# Invite system
# ---------------------------------------------------------------------------

INVITE_TIMEOUT = 60  # seconds

@dataclass
class GameInvite:
    """Represent a pending PvP game invitation between two users."""

    from_user_id: int
    from_username: str
    to_user_id: int
    to_username: str
    created_at: float  # time.time()


_invites: dict[int, GameInvite] = {}  # keyed by from_user_id
_flash: dict[int, str] = {}           # keyed by user_id, one-shot messages


def create_invite(from_id: int, from_name: str, to_id: int, to_name: str) -> GameInvite:
    """Create and store a new game invite, replacing any prior invite from the same user."""
    inv = GameInvite(from_user_id=from_id, from_username=from_name,
                     to_user_id=to_id, to_username=to_name,
                     created_at=time.time())
    _invites[from_id] = inv
    return inv


def get_invite_from(user_id: int) -> GameInvite | None:
    """Get outgoing invite sent by user_id."""
    return _invites.get(user_id)


def get_invite_to(user_id: int) -> GameInvite | None:
    """Get first incoming invite addressed to user_id."""
    for inv in _invites.values():
        if inv.to_user_id == user_id:
            return inv
    return None


def cancel_invite(from_id: int) -> None:
    """Cancel an outgoing invite by the sender's user ID."""
    _invites.pop(from_id, None)


def set_flash(user_id: int, message: str) -> None:
    """Store a one-shot flash message for a user, shown on their next page load."""
    _flash[user_id] = message


def pop_flash(user_id: int) -> str | None:
    """Return and remove the flash message for a user, or None if absent."""
    return _flash.pop(user_id, None)


def expire_invites() -> None:
    """Remove invites older than INVITE_TIMEOUT seconds, flash the sender."""
    now = time.time()
    expired = [fid for fid, inv in _invites.items()
               if now - inv.created_at > INVITE_TIMEOUT]
    for fid in expired:
        inv = _invites.pop(fid)
        _flash[inv.from_user_id] = f"{inv.to_username} did not respond to your challenge."


# ---------------------------------------------------------------------------
# PvP game state
# ---------------------------------------------------------------------------

@dataclass
class PvpGameState:
    """Hold the full state of a player-vs-player Mille Bornes game."""

    game_id: str
    deck: list
    player1: Player
    player2: Player
    player1_id: int
    player2_id: int
    current_turn: int  # user_id of active player
    messages: list = field(default_factory=list)
    winner: str | None = None
    coup_fourre_pending: int | None = None    # user_id who can respond
    coup_fourre_hazard: str | None = None     # hazard name
    score_saved: bool = False
    seen_game_over: set = field(default_factory=set)  # user_ids who have seen the results


_pvp_games: dict[str, PvpGameState] = {}  # game_id -> state
_user_pvp: dict[int, str] = {}            # user_id -> game_id


def new_pvp_game(p1_id: int, p1_name: str, p2_id: int, p2_name: str) -> PvpGameState:
    """Create a new PvP game. Player 1 goes first (pre-draws)."""
    deck = build_deck()
    player1 = Player(p1_name)
    player2 = Player(p2_name)
    for _ in range(6):
        player1.hand.append(deck.pop())
        player2.hand.append(deck.pop())
    # Pre-draw for player1's first turn
    player1.hand.append(deck.pop())
    gid = uuid.uuid4().hex[:12]
    game = PvpGameState(
        game_id=gid, deck=deck,
        player1=player1, player2=player2,
        player1_id=p1_id, player2_id=p2_id,
        current_turn=p1_id,
    )
    _pvp_games[gid] = game
    _user_pvp[p1_id] = gid
    _user_pvp[p2_id] = gid
    return game


def get_pvp_game(user_id: int) -> PvpGameState | None:
    """Return the active PvP game for a user, or None."""
    gid = _user_pvp.get(user_id)
    if gid is None:
        return None
    return _pvp_games.get(gid)


def remove_pvp_game(game_id: str) -> None:
    """Remove a PvP game and unlink both players from it."""
    game = _pvp_games.pop(game_id, None)
    if game:
        _user_pvp.pop(game.player1_id, None)
        _user_pvp.pop(game.player2_id, None)


def leave_pvp_game(user_id: int) -> None:
    """Unlink one player from their PvP game; drop the game once nobody is left.

    Used after a finished game so that one player returning to the lobby
    does not take the result screen away from the other.
    """
    gid = _user_pvp.pop(user_id, None)
    if gid is not None and gid not in _user_pvp.values():
        _pvp_games.pop(gid, None)


def get_me_and_opponent(game: PvpGameState, user_id: int) -> tuple[Player, Player, int, int]:
    """Return (my_player, their_player, my_id, their_id)."""
    if user_id == game.player1_id:
        return game.player1, game.player2, game.player1_id, game.player2_id
    return game.player2, game.player1, game.player2_id, game.player1_id


# ---------------------------------------------------------------------------
# Score persistence
# ---------------------------------------------------------------------------

async def save_score(user_id: int, score: int, opponent: str, won: bool, game: str = "mille"):
    """Persist a game score to the database."""
    db = await get_db()
    await db.execute(
        "INSERT INTO game_scores (user_id, score, opponent, won, game) VALUES (?, ?, ?, ?, ?)",
        (user_id, score, opponent, int(won), game),
    )
    await db.commit()


async def get_high_scores(game: str = "mille") -> list[dict]:
    """Return the best score for each player, ordered by score descending."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT u.username,
                  MAX(gs.score) AS best_score,
                  COUNT(*) AS games_played,
                  SUM(gs.won) AS wins
           FROM game_scores gs
           JOIN users u ON gs.user_id = u.id
           WHERE gs.game = ?
           GROUP BY gs.user_id
           ORDER BY best_score DESC""",
        (game,),
    )
    return [dict(r) for r in await cursor.fetchall()]

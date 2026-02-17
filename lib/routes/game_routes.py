"""Mille Bornes card game routes: CPU games, PvP games, and the invite system.

Handles the full lifecycle of Mille Bornes games including creating new
games, playing/discarding cards, coup fourre responses, PvP invitations,
and score persistence.
"""

import time

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth
from lib.deps import require_user
from lib.web_server import templates, _add_globals
from lib.mille import (
    SAFETY_FOR, card_name, can_play, do_play,
    apply_coup_fourre, cpu_choose, calc_score,
    new_game, get_game, remove_game,
    # Invite system
    create_invite, get_invite_from, get_invite_to, cancel_invite,
    set_flash, pop_flash, expire_invites, INVITE_TIMEOUT,
    # PvP
    new_pvp_game, get_pvp_game, remove_pvp_game, get_me_and_opponent,
    # Scores
    save_score, get_high_scores,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# CPU game helpers (unchanged)
# ---------------------------------------------------------------------------

def _check_game_over(game):
    """Set game.winner if a win/end condition is met."""
    if game.human.miles >= 1000:
        game.winner = game.human.name
    elif game.cpu.miles >= 1000:
        game.winner = game.cpu.name
    elif not game.deck and not game.human.hand and not game.cpu.hand:
        h = calc_score(game.human, game.cpu, None)
        c = calc_score(game.cpu, game.human, None)
        if h >= c:
            game.winner = game.human.name
        else:
            game.winner = game.cpu.name


def _run_cpu_turn(game):
    """Draw for CPU, choose + execute action, handle coup fourre."""
    if game.winner:
        return
    if not game.cpu.hand and not game.deck:
        return

    if game.deck:
        game.cpu.hand.append(game.deck.pop())

    if not game.cpu.hand:
        return

    action, idx = cpu_choose(game.cpu, game.human)
    card = game.cpu.hand[idx]

    if action == "play":
        game.cpu.hand.pop(idx)
        msg = do_play(card, game.cpu, game.human)
        game.messages.append(f"CPU {msg}")

        if card[0] == "hazard":
            safety = SAFETY_FOR[card[1]]
            if ("safety", safety) in game.cpu.hand:
                pass
            if ("safety", safety) in game.human.hand:
                game.coup_fourre_pending = card[1]
                return
    else:
        game.cpu.hand.pop(idx)
        game.messages.append("CPU discards a card.")

    _check_game_over(game)


def _auto_advance_cpu(game):
    """Run remaining CPU turns when the human has no cards and the deck is empty."""
    while (not game.winner
           and not game.human.hand
           and not game.deck
           and game.cpu.hand):
        action, idx = cpu_choose(game.cpu, game.human)
        card = game.cpu.hand[idx]
        if action == "play":
            game.cpu.hand.pop(idx)
            msg = do_play(card, game.cpu, game.human)
            game.messages.append(f"CPU {msg}")
        else:
            game.cpu.hand.pop(idx)
            game.messages.append("CPU discards a card.")
        _check_game_over(game)


# ---------------------------------------------------------------------------
# PvP helpers
# ---------------------------------------------------------------------------

def _check_pvp_game_over(game):
    """Set game.winner if either PvP player has reached 1000 miles or both are out of cards."""
    if game.player1.miles >= 1000:
        game.winner = game.player1.name
    elif game.player2.miles >= 1000:
        game.winner = game.player2.name
    elif not game.deck and not game.player1.hand and not game.player2.hand:
        s1 = calc_score(game.player1, game.player2, None)
        s2 = calc_score(game.player2, game.player1, None)
        if s1 >= s2:
            game.winner = game.player1.name
        else:
            game.winner = game.player2.name


# ---------------------------------------------------------------------------
# GET /mille — unified entry point
# ---------------------------------------------------------------------------

@router.get("/mille", response_class=HTMLResponse)
async def mille_page(request: Request, user: dict = Depends(require_user)):
    """Render the appropriate Mille Bornes view based on the user's current game state.

    Priority order: active PvP game, active CPU game, outgoing invite, lobby.
    """
    uid = user["id"]

    # Expire stale invites on every page load
    expire_invites()

    flash = pop_flash(uid)

    # --- Priority 1: PvP game in progress ---
    pvp = get_pvp_game(uid)
    if pvp:
        me, opp, my_id, opp_id = get_me_and_opponent(pvp, uid)

        if pvp.winner:
            my_score = calc_score(me, opp, pvp.winner)
            opp_score = calc_score(opp, me, pvp.winner)
            if not pvp.score_saved:
                pvp.score_saved = True
                await save_score(pvp.player1_id, calc_score(pvp.player1, pvp.player2, pvp.winner), pvp.player2.name, pvp.winner == pvp.player1.name)
                await save_score(pvp.player2_id, calc_score(pvp.player2, pvp.player1, pvp.winner), pvp.player1.name, pvp.winner == pvp.player2.name)
            return templates.TemplateResponse(
                "mille.html",
                _add_globals(request, {
                    "user": user,
                    "state": "pvp_game_over",
                    "game": pvp,
                    "me": me, "opp": opp,
                    "my_score": my_score, "opp_score": opp_score,
                }),
            )

        if pvp.coup_fourre_pending == uid:
            safety = SAFETY_FOR[pvp.coup_fourre_hazard]
            return templates.TemplateResponse(
                "mille.html",
                _add_globals(request, {
                    "user": user,
                    "state": "pvp_coup_fourre",
                    "game": pvp,
                    "me": me, "opp": opp,
                    "coup_fourre_safety": safety,
                }),
            )

        if pvp.current_turn == uid and pvp.coup_fourre_pending is None:
            playable = [can_play(c, me, opp) for c in me.hand]
            return templates.TemplateResponse(
                "mille.html",
                _add_globals(request, {
                    "user": user,
                    "state": "pvp_active",
                    "game": pvp,
                    "me": me, "opp": opp,
                    "playable": playable,
                }),
            )

        # Opponent's turn — read-only waiting
        return templates.TemplateResponse(
            "mille.html",
            _add_globals(request, {
                "user": user,
                "state": "pvp_waiting",
                "game": pvp,
                "me": me, "opp": opp,
            }),
        )

    # --- Priority 2: CPU game in progress ---
    game = get_game(uid)
    if game:
        if not game.human.hand and not game.deck and not game.winner:
            _auto_advance_cpu(game)
            _check_game_over(game)

        if game.winner:
            human_score = calc_score(game.human, game.cpu, game.winner)
            cpu_score = calc_score(game.cpu, game.human, game.winner)
            if not game.score_saved:
                game.score_saved = True
                await save_score(uid, human_score, "CPU", game.winner == game.human.name)
            return templates.TemplateResponse(
                "mille.html",
                _add_globals(request, {
                    "user": user,
                    "state": "game_over",
                    "game": game,
                    "human_score": human_score,
                    "cpu_score": cpu_score,
                }),
            )

        if game.coup_fourre_pending:
            safety = SAFETY_FOR[game.coup_fourre_pending]
            return templates.TemplateResponse(
                "mille.html",
                _add_globals(request, {
                    "user": user,
                    "state": "coup_fourre",
                    "game": game,
                    "coup_fourre_safety": safety,
                }),
            )

        playable = [
            can_play(card, game.human, game.cpu)
            for card in game.human.hand
        ]
        return templates.TemplateResponse(
            "mille.html",
            _add_globals(request, {
                "user": user,
                "state": "active",
                "game": game,
                "playable": playable,
            }),
        )

    # --- Priority 3: Outgoing invite waiting ---
    outgoing = get_invite_from(uid)
    if outgoing:
        elapsed = time.time() - outgoing.created_at
        remaining = max(0, int(INVITE_TIMEOUT - elapsed))
        return templates.TemplateResponse(
            "mille.html",
            _add_globals(request, {
                "user": user,
                "state": "waiting_invite",
                "invite": outgoing,
                "remaining": remaining,
                "flash": flash,
            }),
        )

    # --- Priority 4: Lobby ---
    online = await auth.list_online_users()
    # Filter out self, users in a PvP game, users in a CPU game, users with pending invites
    available = []
    for u in online:
        if u["id"] == uid:
            continue
        if get_pvp_game(u["id"]):
            continue
        if get_game(u["id"]):
            continue
        if get_invite_from(u["id"]):
            continue
        available.append(u)

    incoming = get_invite_to(uid)
    high_scores = await get_high_scores()

    return templates.TemplateResponse(
        "mille.html",
        _add_globals(request, {
            "user": user,
            "state": "lobby",
            "online_users": available,
            "incoming_invite": incoming,
            "flash": flash,
            "high_scores": high_scores,
        }),
    )


# ---------------------------------------------------------------------------
# CPU game routes (unchanged)
# ---------------------------------------------------------------------------

@router.post("/mille/new")
async def mille_new(request: Request, user: dict = Depends(require_user)):
    """Start a new CPU game. Cancel any pending invite and remove old games."""
    uid = user["id"]
    # Don't allow starting CPU game while in PvP
    if get_pvp_game(uid):
        return RedirectResponse("/mille", status_code=302)
    # Cancel any pending invite
    cancel_invite(uid)
    remove_game(uid)
    new_game(uid)
    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/play")
async def mille_play(
    request: Request,
    card_index: int = Form(),
    user: dict = Depends(require_user),
):
    """Play a card from the human player's hand in a CPU game."""
    game = get_game(user["id"])
    if not game or game.winner or game.coup_fourre_pending:
        return RedirectResponse("/mille", status_code=302)

    if card_index < 0 or card_index >= len(game.human.hand):
        return RedirectResponse("/mille", status_code=302)

    card = game.human.hand[card_index]
    if not can_play(card, game.human, game.cpu):
        game.messages = [f"Can't play {card_name(card)} right now."]
        return RedirectResponse("/mille", status_code=302)

    game.human.hand.pop(card_index)
    msg = do_play(card, game.human, game.cpu)
    game.messages = [f"You {msg}"]

    if card[0] == "hazard":
        safety = SAFETY_FOR[card[1]]
        if ("safety", safety) in game.cpu.hand:
            apply_coup_fourre(game.cpu, card[1])
            game.messages.append(f"CPU plays Coup Fourre: {safety}!")

    _check_game_over(game)

    if not game.winner:
        _run_cpu_turn(game)

    if not game.winner and not game.coup_fourre_pending and game.deck:
        game.human.hand.append(game.deck.pop())

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/discard")
async def mille_discard(
    request: Request,
    card_index: int = Form(),
    user: dict = Depends(require_user),
):
    """Discard a card from the human player's hand in a CPU game."""
    game = get_game(user["id"])
    if not game or game.winner or game.coup_fourre_pending:
        return RedirectResponse("/mille", status_code=302)

    if card_index < 0 or card_index >= len(game.human.hand):
        return RedirectResponse("/mille", status_code=302)

    card = game.human.hand.pop(card_index)
    game.messages = [f"You discard {card_name(card)}."]

    _check_game_over(game)

    if not game.winner:
        _run_cpu_turn(game)

    if not game.winner and not game.coup_fourre_pending and game.deck:
        game.human.hand.append(game.deck.pop())

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/coup")
async def mille_coup(
    request: Request,
    accept: str = Form(),
    user: dict = Depends(require_user),
):
    """Accept or decline a coup fourre opportunity in a CPU game."""
    game = get_game(user["id"])
    if not game or not game.coup_fourre_pending:
        return RedirectResponse("/mille", status_code=302)

    hazard_name = game.coup_fourre_pending
    game.coup_fourre_pending = None

    if accept == "yes":
        safety = SAFETY_FOR[hazard_name]
        apply_coup_fourre(game.human, hazard_name)
        game.messages.append(f"You play Coup Fourre: {safety}!")

    _check_game_over(game)

    if not game.winner and game.deck:
        game.human.hand.append(game.deck.pop())

    return RedirectResponse("/mille", status_code=302)


# ---------------------------------------------------------------------------
# Invite routes
# ---------------------------------------------------------------------------

@router.post("/mille/invite")
async def mille_invite(
    request: Request,
    to_user_id: int = Form(),
    user: dict = Depends(require_user),
):
    """Send a PvP game invitation to another online user."""
    uid = user["id"]
    # Can't invite while in a game
    if get_pvp_game(uid) or get_game(uid):
        return RedirectResponse("/mille", status_code=302)

    # Target must not be in a game or have a pending outgoing invite
    if get_pvp_game(to_user_id) or get_game(to_user_id):
        set_flash(uid, "That player is already in a game.")
        return RedirectResponse("/mille", status_code=302)

    # Cancel any existing outgoing invite from this user
    cancel_invite(uid)

    target = await auth.get_user(to_user_id)
    if not target:
        return RedirectResponse("/mille", status_code=302)

    create_invite(uid, user["username"], to_user_id, target["username"])
    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/invite/cancel")
async def mille_invite_cancel(request: Request, user: dict = Depends(require_user)):
    """Cancel the current user's outgoing PvP invitation."""
    cancel_invite(user["id"])
    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/invite/accept")
async def mille_invite_accept(
    request: Request,
    from_user_id: int = Form(),
    user: dict = Depends(require_user),
):
    """Accept an incoming PvP invitation and start a new PvP game."""
    uid = user["id"]
    inv = get_invite_from(from_user_id)
    if not inv or inv.to_user_id != uid:
        return RedirectResponse("/mille", status_code=302)

    # Don't accept if either player is already in a game
    if get_pvp_game(uid) or get_pvp_game(from_user_id):
        cancel_invite(from_user_id)
        return RedirectResponse("/mille", status_code=302)

    # Remove any CPU games either player has
    remove_game(uid)
    remove_game(from_user_id)

    # Create PvP game — inviter is player1 (goes first)
    cancel_invite(from_user_id)
    new_pvp_game(from_user_id, inv.from_username, uid, inv.to_username)
    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/invite/decline")
async def mille_invite_decline(
    request: Request,
    from_user_id: int = Form(),
    user: dict = Depends(require_user),
):
    """Decline an incoming PvP invitation and notify the sender."""
    uid = user["id"]
    inv = get_invite_from(from_user_id)
    if not inv or inv.to_user_id != uid:
        return RedirectResponse("/mille", status_code=302)

    cancel_invite(from_user_id)
    set_flash(from_user_id, f"{user['username']} declined your challenge.")
    return RedirectResponse("/mille", status_code=302)


# ---------------------------------------------------------------------------
# PvP game routes
# ---------------------------------------------------------------------------

@router.post("/mille/pvp/play")
async def mille_pvp_play(
    request: Request,
    card_index: int = Form(),
    user: dict = Depends(require_user),
):
    """Play a card in a PvP game. Only the active player may act."""
    uid = user["id"]
    pvp = get_pvp_game(uid)
    if not pvp or pvp.winner or pvp.current_turn != uid or pvp.coup_fourre_pending:
        return RedirectResponse("/mille", status_code=302)

    me, opp, my_id, opp_id = get_me_and_opponent(pvp, uid)

    if card_index < 0 or card_index >= len(me.hand):
        return RedirectResponse("/mille", status_code=302)

    card = me.hand[card_index]
    if not can_play(card, me, opp):
        pvp.messages = [f"Can't play {card_name(card)} right now."]
        return RedirectResponse("/mille", status_code=302)

    me.hand.pop(card_index)
    msg = do_play(card, me, opp)
    pvp.messages = [f"{me.name} {msg}"]

    _check_pvp_game_over(pvp)

    if not pvp.winner and card[0] == "hazard":
        safety = SAFETY_FOR[card[1]]
        if ("safety", safety) in opp.hand:
            pvp.coup_fourre_pending = opp_id
            pvp.coup_fourre_hazard = card[1]
            return RedirectResponse("/mille", status_code=302)

    # Switch turns and draw for next player
    if not pvp.winner:
        pvp.current_turn = opp_id
        if pvp.deck:
            opp.hand.append(pvp.deck.pop())

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/pvp/discard")
async def mille_pvp_discard(
    request: Request,
    card_index: int = Form(),
    user: dict = Depends(require_user),
):
    """Discard a card in a PvP game. Only the active player may act."""
    uid = user["id"]
    pvp = get_pvp_game(uid)
    if not pvp or pvp.winner or pvp.current_turn != uid or pvp.coup_fourre_pending:
        return RedirectResponse("/mille", status_code=302)

    me, opp, my_id, opp_id = get_me_and_opponent(pvp, uid)

    if card_index < 0 or card_index >= len(me.hand):
        return RedirectResponse("/mille", status_code=302)

    card = me.hand.pop(card_index)
    pvp.messages = [f"{me.name} discards a card."]

    _check_pvp_game_over(pvp)

    if not pvp.winner:
        pvp.current_turn = opp_id
        if pvp.deck:
            opp.hand.append(pvp.deck.pop())

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/pvp/coup")
async def mille_pvp_coup(
    request: Request,
    accept: str = Form(),
    user: dict = Depends(require_user),
):
    """Accept or decline a coup fourre opportunity in a PvP game."""
    uid = user["id"]
    pvp = get_pvp_game(uid)
    if not pvp or pvp.coup_fourre_pending != uid:
        return RedirectResponse("/mille", status_code=302)

    me, opp, my_id, opp_id = get_me_and_opponent(pvp, uid)
    hazard_name = pvp.coup_fourre_hazard
    pvp.coup_fourre_pending = None
    pvp.coup_fourre_hazard = None

    if accept == "yes":
        safety = SAFETY_FOR[hazard_name]
        apply_coup_fourre(me, hazard_name)
        pvp.messages.append(f"{me.name} plays Coup Fourre: {safety}!")
        # Coup fourre: the player who played it gets the turn and draws
        pvp.current_turn = my_id
        if pvp.deck:
            me.hand.append(pvp.deck.pop())
    else:
        # Declined — turn passes to opponent (the one who played the hazard)
        pvp.current_turn = opp_id
        if pvp.deck:
            opp.hand.append(pvp.deck.pop())

    _check_pvp_game_over(pvp)

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/pvp/quit")
async def mille_pvp_quit(request: Request, user: dict = Depends(require_user)):
    """Forfeit the current PvP game. The opponent wins by default."""
    uid = user["id"]
    pvp = get_pvp_game(uid)
    if not pvp:
        return RedirectResponse("/mille", status_code=302)

    if not pvp.winner:
        me, opp, my_id, opp_id = get_me_and_opponent(pvp, uid)
        set_flash(opp_id, f"{me.name} forfeited the game. You win!")
        pvp.winner = opp.name

    remove_pvp_game(pvp.game_id)
    return RedirectResponse("/mille", status_code=302)

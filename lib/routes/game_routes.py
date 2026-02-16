from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from lib.deps import require_user
from lib.web_server import templates, _add_globals
from lib.mille import (
    SAFETY_FOR, card_name, can_play, do_play,
    apply_coup_fourre, cpu_choose, calc_score,
    new_game, get_game, remove_game,
)

router = APIRouter()


def _check_game_over(game):
    """Set game.winner if a win/end condition is met."""
    if game.human.miles >= 1000:
        game.winner = game.human.name
    elif game.cpu.miles >= 1000:
        game.winner = game.cpu.name
    elif not game.deck and not game.human.hand and not game.cpu.hand:
        # No cards left anywhere — compare scores
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

        # CPU plays a hazard — check for player coup fourre opportunity
        if card[0] == "hazard":
            safety = SAFETY_FOR[card[1]]
            if ("safety", safety) in game.cpu.hand:
                # CPU auto-plays its own coup fourre (shouldn't happen here,
                # but just in case the logic were ever to target itself)
                pass
            if ("safety", safety) in game.human.hand:
                game.coup_fourre_pending = card[1]
                return  # pause for player decision
    else:
        game.cpu.hand.pop(idx)
        game.messages.append("CPU discards a card.")

    _check_game_over(game)


def _auto_advance_cpu(game):
    """When human has no cards but CPU still does, run CPU turns to finish."""
    while (not game.winner
           and not game.human.hand
           and not game.deck
           and game.cpu.hand):
        # CPU needs to play out remaining cards
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


@router.get("/mille", response_class=HTMLResponse)
async def mille_page(request: Request, user: dict = Depends(require_user)):
    game = get_game(user["id"])

    if not game:
        return templates.TemplateResponse(
            "mille.html",
            _add_globals(request, {"user": user, "state": "no_game"}),
        )

    # Auto-advance if human is out of cards but game isn't over
    if not game.human.hand and not game.deck and not game.winner:
        _auto_advance_cpu(game)
        _check_game_over(game)

    if game.winner:
        human_score = calc_score(game.human, game.cpu, game.winner)
        cpu_score = calc_score(game.cpu, game.human, game.winner)
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

    # Normal active game
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


@router.post("/mille/new")
async def mille_new(request: Request, user: dict = Depends(require_user)):
    remove_game(user["id"])
    new_game(user["id"])
    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/play")
async def mille_play(
    request: Request,
    card_index: int = Form(),
    user: dict = Depends(require_user),
):
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

    # Check CPU coup fourre
    if card[0] == "hazard":
        safety = SAFETY_FOR[card[1]]
        if ("safety", safety) in game.cpu.hand:
            apply_coup_fourre(game.cpu, card[1])
            game.messages.append(f"CPU plays Coup Fourre: {safety}!")

    _check_game_over(game)

    if not game.winner:
        _run_cpu_turn(game)

    # Draw for human's next turn (if game not over and deck has cards)
    if not game.winner and not game.coup_fourre_pending and game.deck:
        game.human.hand.append(game.deck.pop())

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/discard")
async def mille_discard(
    request: Request,
    card_index: int = Form(),
    user: dict = Depends(require_user),
):
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

    # Draw for human's next turn
    if not game.winner and not game.coup_fourre_pending and game.deck:
        game.human.hand.append(game.deck.pop())

    return RedirectResponse("/mille", status_code=302)


@router.post("/mille/coup")
async def mille_coup(
    request: Request,
    accept: str = Form(),
    user: dict = Depends(require_user),
):
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

    # Draw for human's next turn
    if not game.winner and game.deck:
        game.human.hand.append(game.deck.pop())

    return RedirectResponse("/mille", status_code=302)

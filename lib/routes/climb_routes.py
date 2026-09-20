"""The Long Climb: one page, one action endpoint.

``GET /games/climb`` shows the player's current screen and never changes
anything that matters (it applies dawn if a new day has begun, nothing else),
so reloading cannot re-roll a result. ``POST /games/climb/act`` performs one
action from that screen. All game logic is in ``lib.climb``.
"""

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from lib.climb import clock, data, scenes, store, text
from lib.deps import require_user
from lib.templating import templates, _add_globals

router = APIRouter()

PAGE = "/games/climb"

# Unpredictable on purpose: nobody should be able to guess the next roll.
rng = secrets.SystemRandom()


def _back() -> RedirectResponse:
    return RedirectResponse(PAGE, status_code=303)


@router.get(PAGE, response_class=HTMLResponse)
async def climb_page(request: Request, user: dict = Depends(require_user)):
    """Render whatever screen the player is on."""
    player = await store.load(user["id"])
    if player is not None and scenes.dawn(player, clock.today()):
        # Lost the race to another tab? Then that tab applied dawn; reload it.
        if not await store.save(player):
            player = await store.load(user["id"])

    if player is None:
        context = {"screen": scenes.welcome(), "status": None, "notice": [], "turn": 0}
    else:
        context = {
            "screen": scenes.screen(player), "status": scenes.status(player),
            "notice": player.notice, "turn": player.turn,
        }
    return templates.TemplateResponse(
        "climb.html",
        _add_globals(request, {"user": user, "game_title": text.TITLE, "credit": data.CREDIT, **context}),
    )


@router.post(f"{PAGE}/act")
async def climb_act(
    request: Request,
    action: str = Form(max_length=40),
    turn: int = Form(0, ge=0),
    amount: int = Form(0, ge=0, le=10**12),
    user: dict = Depends(require_user),
):
    """Perform one action. Anything stale, repeated, or not on offer is ignored."""
    player = await store.load(user["id"])
    today = clock.today()

    if player is None:
        try:
            climber, notice = scenes.begin(action)
        except scenes.NotOffered:
            return _back()
        await store.create(user["id"], climber, today, notice)
        return _back()

    # A form from an earlier screen (double-click, second tab, back button).
    if turn != player.turn:
        return _back()
    # A form from before midnight: the day has turned, so yesterday's choice is void.
    if scenes.dawn(player, today):
        await store.save(player)
        return _back()

    try:
        scenes.act(rng, player, action, amount)
    except scenes.NotOffered:
        return _back()
    await store.save(player)
    return _back()

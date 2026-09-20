"""The Long Climb: one page, one action endpoint.

``GET /games/climb`` shows the player's current screen and never changes
anything that matters (it applies dawn if a new day has begun, nothing else),
so reloading cannot re-roll a result. ``POST /games/climb/act`` performs one
action from that screen. All game logic is in ``lib.climb``.
"""

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from lib.climb import clock, data, rules, scenes, store, text
from lib.deps import require_admin, require_user
from lib.templating import templates, _add_globals

router = APIRouter()

PAGE = "/games/climb"

# Unpredictable on purpose: nobody should be able to guess the next roll.
rng = secrets.SystemRandom()


def _back() -> RedirectResponse:
    return RedirectResponse(PAGE, status_code=303)


def _day_label(day, today) -> str:
    age = (today - day).days
    return "Today" if age == 0 else "Yesterday" if age == 1 else day.strftime("%A")


def _news_line(kind: str, username: str, detail: str, player: store.Player) -> str:
    """Stentor's wording for something a climber did. Variants rotate with the turn."""
    variants = text.NEWS[kind]
    c = player.climber
    return variants[player.turn % len(variants)].format(
        name=username, band=data.BANDS[c.level - 1],
        detail=c.ascents if kind == scenes.ASCENDED else detail,
    )


async def _tell_the_town(user: dict, player: store.Player, today) -> None:
    """Act on what just happened, once the save that made it real has succeeded."""
    for kind, detail in player.happenings:
        if kind == scenes.WROTE:
            await store.add_wall_line(user["id"], detail)
            continue
        if kind in (scenes.LEVEL_GAINED, scenes.ASCENDED):
            await store.record_score(
                user["id"], rules.renown(player.climber), detail, won=kind == scenes.ASCENDED,
            )
        await store.add_news(today, user["id"], _news_line(kind, user["username"], detail, player))


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
        if player.scene == scenes.STELE and player.climber.alive:
            context["stele"] = [
                {**row, "title": rules.title(row["ascents"]), "band": data.BANDS[row["level"] - 1],
                 "calling": data.CALLINGS[row["calling"]][0]}
                for row in await store.rankings()
            ]
            context["stele_empty"] = text.STELE_EMPTY
        elif player.scene == scenes.HERALD and player.climber.alive:
            today = clock.today()
            await store.ensure_daily_line(today, text.DAILY[today.toordinal() % len(text.DAILY)])
            context["news"] = [(_day_label(day, today), lines) for day, lines in await store.news(today)]
            context["news_quiet"] = text.HERALD_QUIET
        elif player.scene == scenes.WALL and player.climber.alive:
            context["wall"] = await store.wall_lines()
            context["wall_empty"] = text.WALL_EMPTY
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
    words: str = Form("", max_length=400),
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
        created = await store.create(user["id"], climber, today, notice)
        if created is not None:
            await store.add_news(today, user["id"], _news_line(scenes.ARRIVED, user["username"], "", created))
        return _back()

    # A form from an earlier screen (double-click, second tab, back button).
    if turn != player.turn:
        return _back()
    # A form from before midnight: the day has turned, so yesterday's choice is void.
    if scenes.dawn(player, today):
        await store.save(player)
        return _back()

    try:
        scenes.act(rng, player, action, amount, words)
    except scenes.NotOffered:
        return _back()
    if await store.save(player):
        await _tell_the_town(user, player, today)
    return _back()


# ---------------------------------------------------------------------------
# Sysop tools
# ---------------------------------------------------------------------------

@router.post(f"{PAGE}/admin/wall/{{line_id}}/delete")
async def climb_admin_wall_delete(line_id: int, user: dict = Depends(require_admin)):
    """Remove one line from the tavern wall."""
    await store.delete_wall_line(line_id)
    return _back()


@router.post(f"{PAGE}/admin/reset/{{user_id}}")
async def climb_admin_reset(user_id: int, user: dict = Depends(require_admin)):
    """Delete a climber outright; their owner may start again from nothing."""
    await store.delete(user_id)
    return _back()

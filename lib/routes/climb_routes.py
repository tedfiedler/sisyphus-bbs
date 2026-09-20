"""The Long Climb: one page, one action endpoint.

``GET /games/climb`` shows the player's current screen and never changes
anything that matters (it applies dawn if a new day has begun, nothing else),
so reloading cannot re-roll a result. ``POST /games/climb/act`` performs one
action from that screen. All game logic is in ``lib.climb``.
"""

import secrets
from datetime import date

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


async def _camp(player: store.Player, today) -> list[scenes.Target]:
    """The sleepers this player could rob right now, strongest first."""
    targets = []
    for sleeper in await store.sleepers(player.user_id, today):
        them = sleeper.player
        away = (today - them.last_day).days
        reason = rules.why_not_rob(
            player.climber, them.climber, days_since_played=away,
            minutes_since_seen=sleeper.minutes_since_seen,
            days_since_joined=sleeper.days_since_joined, already_today=sleeper.already_today,
        )
        if reason is None:
            targets.append(scenes.Target(
                user_id=sleeper.user_id, name=sleeper.username,
                foe=rules.sleeper_as_foe(them.climber, sleeper.username, away),
                title=rules.title(them.climber.ascents),
                band=data.BANDS[min(them.climber.weapon, them.climber.armour) - 1],
                in_room=rules.is_sheltered(them.climber.room, away),
            ))
    targets.sort(key=lambda t: (-t.foe.xp, t.name.lower()))
    return targets[:data.CAMP_LIST_LENGTH]


async def _settle_robbery(user: dict, player: store.Player, kind: str, detail: dict) -> None:
    """Move the coin between the two climbers' real rows.

    The victim is debited first and the robber credited only with what was
    actually taken, so a victim who banked their purse mid-fight loses nothing
    and nothing is created. If the process died between the two writes, coin
    would be lost, never duplicated.
    """
    name = user["username"]
    if kind == scenes.ROBBED:
        def debit(victim: store.Player):
            taken, lost_xp = rules.apply_robbed(victim.climber)
            note = text.MAIL_ROBBED if taken else text.MAIL_ROBBED_EMPTY
            victim.mail.append(note.format(name=name, drachmae=taken, xp=lost_xp))
            return taken

        taken = await store.change(detail["victim"], debit) or 0

        def credit(robber: store.Player):
            robber.climber.purse += taken
            line = text.ROBBED_THEM if taken else text.ROBBED_NOTHING
            robber.notice.append(line.format(name=detail["name"], drachmae=taken))

        await store.change(user["id"], credit)
    else:
        def reward(victim: store.Player):
            xp = rules.apply_defended(victim.climber, detail["purse"], detail["level"])
            victim.mail.append(text.MAIL_DEFENDED.format(name=name, drachmae=detail["purse"], xp=xp))

        await store.change(detail["victim"], reward)


async def _tell_the_town(user: dict, player: store.Player, today) -> None:
    """Act on what just happened, once the save that made it real has succeeded."""
    for kind, detail in player.happenings:
        if kind == scenes.WROTE:
            await store.add_wall_line(user["id"], detail)
            continue
        if kind == scenes.ATTEMPTED:
            await store.note_robbery(today, user["id"], detail)
            continue
        if kind in (scenes.ROBBED, scenes.FELL_TO):
            await _settle_robbery(user, player, kind, detail)
            detail = detail["name"]
        if kind in (scenes.LEVEL_GAINED, scenes.ASCENDED):
            await store.record_score(
                user["id"], rules.renown(player.climber), detail, won=kind == scenes.ASCENDED,
            )
        await store.add_news(today, user["id"], _news_line(kind, user["username"], detail, player))


@router.get(PAGE, response_class=HTMLResponse)
async def climb_page(request: Request, user: dict = Depends(require_user)):
    """Render whatever screen the player is on."""
    player = await store.load(user["id"])
    if player is not None:
        changed = scenes.dawn(player, clock.today())
        if player.mail:
            # What happened while they were away, shown once, above the day's first words.
            player.notice, player.mail, changed = player.mail + player.notice, [], True
        # Lost the race to another tab? Then that tab did this; show its result.
        if changed and not await store.save(player):
            player = await store.load(user["id"])

    if player is None:
        context = {"screen": scenes.welcome(), "status": None, "notice": [], "turn": 0}
    else:
        today = clock.today()
        camp = await _camp(player, today) if player.scene == scenes.CAMP and player.climber.alive else None
        context = {
            "screen": scenes.screen(player, camp), "status": scenes.status(player),
            "notice": player.notice, "turn": player.turn,
        }
        if player.scene in (scenes.STELE, scenes.OTHERS) and player.climber.alive:
            rows = [
                {**row, "title": rules.title(row["ascents"]), "band": data.BANDS[row["level"] - 1],
                 "calling": data.CALLINGS[row["calling"]][0],
                 "weapon": data.WEAPONS[row["weapon"] - 1], "armour": data.ARMOURS[row["armour"] - 1],
                 "sheltered": rules.is_sheltered(
                     bool(row["room"]), (today - date.fromisoformat(row["last_day"])).days)}
                for row in await store.rankings()
            ]
            if player.scene == scenes.STELE:
                context["stele"], context["stele_empty"] = rows, text.STELE_EMPTY
            else:
                context["others"] = [row for row in rows if row["user_id"] != user["id"]]
                context["others_empty"] = text.OTHERS_EMPTY
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

    camp = await _camp(player, today) if player.scene == scenes.CAMP else None
    try:
        scenes.act(rng, player, action, amount, words, camp)
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

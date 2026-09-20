"""Persistence for The Long Climb.

One row per player. The rules work on plain dataclasses; this module turns
them into JSON and back, and is the only place that knows the table exists.
"""

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta

from lib.climb import data, rules
from lib.db import get_db

AGORA = "agora"


@dataclass
class Player:
    user_id: int
    climber: rules.Climber
    turn: int = 0
    scene: str = AGORA
    fight: rules.Fight | None = None
    event: str | None = None            # a Slopes event waiting for the climber's choice
    notice: list[str] = field(default_factory=list)      # what the last action looked like
    # Things that happened to this climber while they were away (robbed in the
    # night, defended in their sleep). Unlike `notice`, this survives dawn; the
    # page moves it into `notice` the next time they look.
    mail: list[str] = field(default_factory=list)
    last_day: date | None = None
    # Things the rest of the BBS should hear about (a level gained, an ascent).
    # Filled by scenes.act, acted on by the route once the save has succeeded,
    # never stored.
    happenings: list[tuple[str, str]] = field(default_factory=list)


def _known(cls, values: dict) -> dict:
    """Drop keys a newer or older version of the dataclass does not have."""
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in values.items() if k in names}


def _fight_to_json(fight: rules.Fight | None) -> str | None:
    if fight is None:
        return None
    blob = asdict(fight)
    blob["outcome"] = fight.outcome.value
    return json.dumps(blob)


def _fight_from_json(text: str | None) -> rules.Fight | None:
    if not text:
        return None
    blob = json.loads(text)
    foe = rules.Foe(**_known(rules.Foe, blob.pop("foe")))
    blob["outcome"] = rules.Outcome(blob["outcome"])
    blob["events"] = [tuple(event) for event in blob.get("events", [])]
    return rules.Fight(foe=foe, **_known(rules.Fight, blob))


def _from_row(row) -> Player:
    return Player(
        user_id=row["user_id"],
        turn=row["turn"],
        climber=rules.Climber(**_known(rules.Climber, json.loads(row["climber"]))),
        scene=row["scene"],
        fight=_fight_from_json(row["fight"]),
        event=row["event"],
        notice=json.loads(row["notice"]),
        mail=json.loads(row["mail"]),
        last_day=date.fromisoformat(row["last_day"]),
    )


async def load(user_id: int) -> Player | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM climb_players WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return _from_row(row) if row else None


async def create(user_id: int, climber: rules.Climber, today: date, notice: list[str]) -> Player | None:
    """Insert a new player. Returns None if this user already has a climber."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT OR IGNORE INTO climb_players (user_id, climber, notice, last_day)
           VALUES (?, ?, ?, ?)""",
        (user_id, json.dumps(asdict(climber)), json.dumps(notice), today.isoformat()),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    return await load(user_id)


async def save(player: Player) -> bool:
    """Write the player back if nobody else has since; returns False when stale.

    The ``turn`` the player was loaded with must still be the row's turn. A
    double-click, a second tab, or a resubmitted form loses that race and
    changes nothing. One statement, so it is also safe on the shared
    connection.
    """
    db = await get_db()
    cursor = await db.execute(
        """UPDATE climb_players
           SET climber = ?, scene = ?, fight = ?, event = ?, notice = ?, mail = ?, last_day = ?,
               turn = turn + 1, last_seen = CURRENT_TIMESTAMP
           WHERE user_id = ? AND turn = ?""",
        (
            json.dumps(asdict(player.climber)), player.scene, _fight_to_json(player.fight),
            player.event, json.dumps(player.notice), json.dumps(player.mail), player.last_day.isoformat(),
            player.user_id, player.turn,
        ),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return False
    player.turn += 1
    return True


IDLE_DAYS = data.IDLE_DAYS


async def rankings(limit: int = 25) -> list[dict]:
    """The Stele: climbers seen in the last fortnight, most accomplished first."""
    db = await get_db()
    cursor = await db.execute(
        f"""SELECT u.id AS user_id, u.username,
                   json_extract(p.climber, '$.ascents') AS ascents,
                   json_extract(p.climber, '$.level') AS level,
                   json_extract(p.climber, '$.xp') AS xp,
                   json_extract(p.climber, '$.calling') AS calling,
                   json_extract(p.climber, '$.alive') AS alive,
                   json_extract(p.climber, '$.room') AS room,
                   json_extract(p.climber, '$.weapon') AS weapon,
                   json_extract(p.climber, '$.armour') AS armour,
                   p.last_day
            FROM climb_players p JOIN users u ON u.id = p.user_id
            WHERE p.last_seen >= datetime('now', '-{IDLE_DAYS} days')
            ORDER BY ascents DESC, level DESC, xp DESC, u.username COLLATE NOCASE
            LIMIT ?""",
        (limit,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def record_score(user_id: int, score: int, opponent: str, won: bool) -> None:
    """Write to the BBS-wide score table, which is what 'has played a game' reads."""
    db = await get_db()
    await db.execute(
        "INSERT INTO game_scores (user_id, game, score, opponent, won) VALUES (?, 'climb', ?, ?, ?)",
        (user_id, score, opponent, int(won)),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# The Camp
# ---------------------------------------------------------------------------

@dataclass
class Sleeper:
    """Another climber, as the Camp list needs to see them."""

    user_id: int
    username: str
    player: Player
    minutes_since_seen: float
    days_since_joined: float
    already_today: bool


async def sleepers(attacker_id: int, today: date) -> list[Sleeper]:
    """Every other climber, with what is needed to decide whether they can be robbed."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT p.*, u.username,
                  (julianday('now') - julianday(p.last_seen)) * 1440.0 AS minutes_since_seen,
                  julianday('now') - julianday(p.created_at) AS days_since_joined,
                  EXISTS (SELECT 1 FROM climb_robberies r
                          WHERE r.day = ? AND r.attacker_id = ? AND r.victim_id = p.user_id) AS already_today
           FROM climb_players p JOIN users u ON u.id = p.user_id
           WHERE p.user_id != ?""",
        (today.isoformat(), attacker_id, attacker_id),
    )
    return [
        Sleeper(
            user_id=row["user_id"], username=row["username"], player=_from_row(row),
            minutes_since_seen=row["minutes_since_seen"], days_since_joined=row["days_since_joined"],
            already_today=bool(row["already_today"]),
        )
        for row in await cursor.fetchall()
    ]


async def note_robbery(day: date, attacker_id: int, victim_id: int) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO climb_robberies (day, attacker_id, victim_id) VALUES (?, ?, ?)",
        (day.isoformat(), attacker_id, victim_id),
    )
    await db.execute("DELETE FROM climb_robberies WHERE day < ?", (day.isoformat(),))
    await db.commit()


async def change(user_id: int, mutate) -> object:
    """Load a player, apply ``mutate(player)``, and save, retrying if they moved meanwhile.

    For the one case where a request changes somebody else's row. Returns
    whatever ``mutate`` returned on the attempt that was saved, or None if the
    player is gone.
    """
    for _ in range(6):
        player = await load(user_id)
        if player is None:
            return None
        result = mutate(player)
        if await save(player):
            return result
    raise RuntimeError(f"could not update climber {user_id}: too much contention")


# ---------------------------------------------------------------------------
# The Herald
# ---------------------------------------------------------------------------

async def add_news(day: date, user_id: int | None, line: str) -> None:
    """Post a line, and let anything older than the Herald remembers fall off."""
    db = await get_db()
    await db.execute(
        "INSERT INTO climb_news (day, user_id, line) VALUES (?, ?, ?)", (day.isoformat(), user_id, line)
    )
    oldest = day - timedelta(days=data.NEWS_DAYS - 1)
    await db.execute("DELETE FROM climb_news WHERE day < ?", (oldest.isoformat(),))
    await db.commit()


async def ensure_daily_line(day: date, line: str) -> None:
    """The town's own line for the day, written by whoever looks first."""
    db = await get_db()
    await db.execute(
        """INSERT INTO climb_news (day, user_id, line)
           SELECT ?, NULL, ?
           WHERE NOT EXISTS (SELECT 1 FROM climb_news WHERE day = ? AND user_id IS NULL)""",
        (day.isoformat(), line, day.isoformat()),
    )
    await db.commit()


async def news(today: date) -> list[tuple[date, list[str]]]:
    """Recent news, newest day first; within a day, the town's line then events in order."""
    db = await get_db()
    oldest = today - timedelta(days=data.NEWS_DAYS - 1)
    cursor = await db.execute(
        """SELECT day, line FROM climb_news WHERE day >= ? AND day <= ?
           ORDER BY day DESC, user_id IS NOT NULL, id""",
        (oldest.isoformat(), today.isoformat()),
    )
    days: dict[str, list[str]] = {}
    for row in await cursor.fetchall():
        days.setdefault(row["day"], []).append(row["line"])
    return [(date.fromisoformat(day), lines) for day, lines in days.items()]


# ---------------------------------------------------------------------------
# The tavern wall
# ---------------------------------------------------------------------------

async def wall_lines() -> list[dict]:
    """The most recent lines, oldest first, as they would read down a wall."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT w.id, w.line, u.username FROM climb_wall w JOIN users u ON u.id = w.user_id
           ORDER BY w.id DESC LIMIT ?""",
        (data.WALL_LINES_SHOWN,),
    )
    return [dict(row) for row in reversed(await cursor.fetchall())]


async def add_wall_line(user_id: int, line: str) -> None:
    db = await get_db()
    await db.execute("INSERT INTO climb_wall (user_id, line) VALUES (?, ?)", (user_id, line))
    await db.commit()


async def delete_wall_line(line_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM climb_wall WHERE id = ?", (line_id,))
    await db.commit()


async def delete(user_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM climb_players WHERE user_id = ?", (user_id,))
    await db.commit()

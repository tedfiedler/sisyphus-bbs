"""Persistence for The Long Climb.

One row per player. The rules work on plain dataclasses; this module turns
them into JSON and back, and is the only place that knows the table exists.
"""

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date

from lib.climb import rules
from lib.db import get_db

AGORA = "agora"


@dataclass
class Player:
    user_id: int
    climber: rules.Climber
    turn: int = 0
    scene: str = AGORA
    fight: rules.Fight | None = None
    notice: list[str] = field(default_factory=list)      # what the last action looked like
    last_day: date | None = None


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
        notice=json.loads(row["notice"]),
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
           SET climber = ?, scene = ?, fight = ?, notice = ?, last_day = ?,
               turn = turn + 1, last_seen = CURRENT_TIMESTAMP
           WHERE user_id = ? AND turn = ?""",
        (
            json.dumps(asdict(player.climber)), player.scene, _fight_to_json(player.fight),
            json.dumps(player.notice), player.last_day.isoformat(),
            player.user_id, player.turn,
        ),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return False
    player.turn += 1
    return True


async def delete(user_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM climb_players WHERE user_id = ?", (user_id,))
    await db.commit()

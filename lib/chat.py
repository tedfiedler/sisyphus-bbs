"""Real-time chat infrastructure: pub/sub messaging, channel CRUD, and DM helpers."""

import asyncio
import re
from datetime import datetime, timezone

from lib.db import get_db


class ChatManager:
    """Manage pub/sub message delivery and persistence for chat channels."""

    def __init__(self):
        """Initialize the subscriber registry."""
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, channel: str = "lobby") -> asyncio.Queue:
        """Create and return a new message queue subscribed to the given channel."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(q)
        return q

    def unsubscribe(self, channel: str, queue: asyncio.Queue):
        """Remove a queue from a channel's subscriber list."""
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(queue)
            except ValueError:
                pass

    async def broadcast(self, channel: str, username: str, message: str):
        """Persist a message and deliver it to all subscribers of the channel."""
        msg_id = await self._store_message(channel, username, message)
        payload = {
            "id": msg_id,
            "username": username,
            "message": message,
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for q in self._subscribers.get(channel, []):
            await q.put(payload)

    async def _store_message(self, channel: str, username: str, message: str) -> int | None:
        """Save a chat message to the database and return its row ID, or None if the user is unknown."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        if row:
            insert_cursor = await db.execute(
                "INSERT INTO chat_messages (user_id, channel, message) VALUES (?, ?, ?)",
                (row["id"], channel, message),
            )
            await db.commit()
            return insert_cursor.lastrowid
        return None

    async def broadcast_all(self, username: str, message: str):
        """Send an announcement to every connected user across all channels."""
        payload = {
            "type": "announcement",
            "username": username,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        seen: set[int] = set()
        for queues in self._subscribers.values():
            for q in queues:
                qid = id(q)
                if qid not in seen:
                    seen.add(qid)
                    await q.put(payload)

    async def recent_messages(self, channel: str = "lobby", limit: int = 50) -> list[dict]:
        """Fetch the most recent messages for a channel, ordered oldest-first."""
        db = await get_db()
        cursor = await db.execute(
            """SELECT cm.*, u.username
               FROM chat_messages cm JOIN users u ON cm.user_id = u.id
               WHERE cm.channel = ?
               ORDER BY cm.id DESC LIMIT ?""",
            (channel, limit),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        rows.reverse()
        return rows


async def delete_message(message_id: int):
    """Delete a single chat message by its ID."""
    db = await get_db()
    await db.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
    await db.commit()


# --- Channel management ---

async def create_channel(name: str, description: str, created_by: int) -> dict:
    """Insert a new chat channel and return its id, name, and description."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO chat_channels (name, description, created_by) VALUES (?, ?, ?)",
        (name, description, created_by),
    )
    await db.commit()
    return {"id": cursor.lastrowid, "name": name, "description": description}


async def list_channels() -> list[dict]:
    """Return all chat channels ordered alphabetically by name."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM chat_channels ORDER BY name"
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_channel(name: str) -> dict | None:
    """Look up a chat channel by name, returning its data or None if not found."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM chat_channels WHERE name = ?", (name,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_channel(channel_name: str):
    """Delete a channel and all of its messages."""
    db = await get_db()
    await db.execute("DELETE FROM chat_messages WHERE channel = ?", (channel_name,))
    await db.execute("DELETE FROM chat_channels WHERE name = ?", (channel_name,))
    await db.commit()


# --- DM helpers ---

_DM_RE = re.compile(r"^dm:(\d+):(\d+)$")


def dm_channel_name(user_id_a: int, user_id_b: int) -> str:
    """Build a canonical DM channel name from two user IDs, sorted low-to-high."""
    lo, hi = sorted((user_id_a, user_id_b))
    return f"dm:{lo}:{hi}"


def is_dm_channel(channel: str) -> bool:
    """Return True if the channel name matches the DM naming pattern."""
    return _DM_RE.match(channel) is not None


def dm_participant_ids(channel: str) -> tuple[int, int] | None:
    """Extract the two participant user IDs from a DM channel name, or return None if invalid."""
    m = _DM_RE.match(channel)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


async def list_dm_channels_for_user(user_id: int) -> list[dict]:
    """Return DM channels this user participates in, with the other user's info."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT DISTINCT channel FROM chat_messages
           WHERE channel LIKE 'dm:%' AND (
               channel LIKE '%:' || ? || ':%' OR
               channel LIKE 'dm:' || ? || ':%' OR
               channel LIKE '%:' || ?
           )
           ORDER BY channel""",
        (user_id, user_id, user_id),
    )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        ch = row["channel"]
        ids = dm_participant_ids(ch)
        if ids and user_id in ids:
            other_id = ids[0] if ids[1] == user_id else ids[1]
            user_cursor = await db.execute(
                "SELECT id, username FROM users WHERE id = ?", (other_id,)
            )
            other = await user_cursor.fetchone()
            if other:
                results.append({"channel": ch, "other_user": dict(other)})
    return results


async def validate_channel(channel: str, user_id: int) -> str | None:
    """Return None if valid, or an error message string."""
    if channel == "lobby":
        return None
    if is_dm_channel(channel):
        ids = dm_participant_ids(channel)
        if ids is None:
            return "Invalid DM channel"
        if user_id not in ids:
            return "You are not a participant in this DM"
        return None
    # Named channel — must exist in db
    ch = await get_channel(channel)
    if ch is None:
        return "Channel does not exist"
    return None


chat_manager = ChatManager()

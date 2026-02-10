import asyncio
from datetime import datetime, timezone

from db import get_db


class ChatManager:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, channel: str = "lobby") -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(q)
        return q

    def unsubscribe(self, channel: str, queue: asyncio.Queue):
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(queue)
            except ValueError:
                pass

    async def broadcast(self, channel: str, username: str, message: str):
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

    async def recent_messages(self, channel: str = "lobby", limit: int = 50) -> list[dict]:
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
    db = await get_db()
    await db.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
    await db.commit()


chat_manager = ChatManager()

"""Session table upkeep and the indexes the hot queries rely on."""

from datetime import datetime, timedelta, timezone

import pytest

from lib import auth
from lib.db import get_db


async def _session_count() -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM sessions")
    return (await cursor.fetchone())["cnt"]


async def _insert_expired(user_id: int, count: int):
    db = await get_db()
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for i in range(count):
        await db.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, f"stale-{i}", stale),
        )
    await db.commit()


@pytest.mark.asyncio
async def test_expired_sessions_are_swept_on_login():
    """The table used to grow forever; expired rows were only filtered on read."""
    user = await auth.register_user("alice", "password123")
    await _insert_expired(user["id"], 20)
    assert await _session_count() == 20

    await auth.create_session(user["id"])

    assert await _session_count() == 1


@pytest.mark.asyncio
async def test_sweep_keeps_live_sessions():
    user = await auth.register_user("alice", "password123")
    live = await auth.create_session(user["id"])
    await _insert_expired(user["id"], 5)

    await auth.delete_expired_sessions()

    assert await _session_count() == 1
    assert await auth.get_user_by_token(live) is not None


@pytest.mark.asyncio
async def test_delete_expired_sessions_reports_how_many_went():
    user = await auth.register_user("alice", "password123")
    await _insert_expired(user["id"], 7)
    assert await auth.delete_expired_sessions() == 7
    assert await auth.delete_expired_sessions() == 0


@pytest.mark.asyncio
async def test_expired_token_still_rejected():
    user = await auth.register_user("alice", "password123")
    await _insert_expired(user["id"], 1)
    assert await auth.get_user_by_token("stale-0") is None


@pytest.mark.asyncio
async def test_hot_query_indexes_exist():
    db = await get_db()
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    names = {row["name"] for row in await cursor.fetchall()}
    for expected in (
        "idx_posts_thread", "idx_threads_board", "idx_post_likes_post",
        "idx_chat_messages_channel", "idx_sessions_expires",
    ):
        assert expected in names, f"missing index {expected}"


@pytest.mark.asyncio
async def test_thread_post_lookup_uses_its_index():
    """Confirm the planner actually picks the index up."""
    db = await get_db()
    cursor = await db.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM posts WHERE thread_id = 1"
    )
    plan = " ".join(str(row["detail"]) for row in await cursor.fetchall())
    assert "idx_posts_thread" in plan, plan

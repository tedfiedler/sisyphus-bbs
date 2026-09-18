"""Authorization regressions: DM channel access and file-section gating."""

from datetime import datetime, timedelta, timezone

import pytest

from lib import auth
from lib import boards
from lib.chat import chat_manager, dm_channel_name
from lib.db import get_db
from tests.helpers import client_for


@pytest.mark.asyncio
async def test_dm_page_hides_conversations_from_non_participants():
    """A third party must not read a DM channel through the chat page."""
    alice = await auth.register_user("alice", "password123")
    bob = await auth.register_user("bob", "password123")
    mallory = await auth.register_user("mallory", "password123")

    channel = dm_channel_name(alice["id"], bob["id"])
    await chat_manager.broadcast(channel, "alice", "SECRET-PIN-4242")

    async with await client_for(mallory["id"]) as client:
        resp = await client.get(f"/chat?channel={channel}", follow_redirects=False)

    assert resp.status_code == 303
    assert "SECRET-PIN-4242" not in resp.text


@pytest.mark.asyncio
async def test_dm_page_allows_participants():
    """Both participants can still read their own conversation."""
    alice = await auth.register_user("alice", "password123")
    bob = await auth.register_user("bob", "password123")

    channel = dm_channel_name(alice["id"], bob["id"])
    await chat_manager.broadcast(channel, "alice", "dinner at eight")

    for participant in (alice, bob):
        async with await client_for(participant["id"]) as client:
            resp = await client.get(f"/chat?channel={channel}", follow_redirects=False)
        assert resp.status_code == 200
        assert "dinner at eight" in resp.text


@pytest.mark.asyncio
async def test_dm_page_does_not_clear_unread_for_non_participants():
    """Reading someone else's DM must not mark it seen on their behalf."""
    alice = await auth.register_user("alice", "password123")
    bob = await auth.register_user("bob", "password123")
    mallory = await auth.register_user("mallory", "password123")

    channel = dm_channel_name(alice["id"], bob["id"])
    await chat_manager.broadcast(channel, "alice", "hello bob")

    async with await client_for(mallory["id"]) as client:
        await client.get(f"/chat?channel={channel}", follow_redirects=False)

    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM dm_channel_seen WHERE channel = ?", (channel,)
    )
    assert (await cursor.fetchone())["cnt"] == 0


@pytest.mark.asyncio
async def test_unknown_channel_is_rejected():
    """A channel that does not exist redirects rather than rendering empty."""
    await auth.register_user("admin", "password123")
    user = await auth.register_user("regular", "password123")

    async with await client_for(user["id"]) as client:
        resp = await client.get("/chat?channel=nope", follow_redirects=False)

    assert resp.status_code == 303


async def _make_eligible(user_id: int, liker_id: int):
    """Satisfy every documented file-access criterion for the user."""
    db = await get_db()
    await db.execute("UPDATE users SET file_upload_allowed = 1 WHERE id = ?", (user_id,))
    utc_today = datetime.now(timezone.utc).date()
    for day in range(5):
        await db.execute(
            "INSERT OR IGNORE INTO login_days (user_id, login_date) VALUES (?, ?)",
            (user_id, (utc_today - timedelta(days=day)).isoformat()),
        )
    board_id = await boards.create_board("general")
    thread_id = await boards.create_thread(board_id, "hi", user_id, "body")
    post_id = (await boards.list_posts(thread_id))[0]["id"]
    await boards.toggle_like(post_id, liker_id)
    await db.execute(
        "INSERT INTO game_scores (user_id, score, opponent, won) VALUES (?, 500, 'CPU', 1)",
        (user_id,),
    )
    await db.commit()


@pytest.mark.asyncio
async def test_eligible_user_is_granted_file_access_from_session_dict():
    """check_file_access must not depend on keys the session dict omits."""
    admin = await auth.register_user("admin", "password123")
    regular = await auth.register_user("regular", "password123")
    await _make_eligible(regular["id"], admin["id"])

    token = await auth.create_session(regular["id"])
    session_user = await auth.get_user_by_token(token)
    assert "file_upload_allowed" not in session_user

    access = await auth.check_file_access(session_user)
    assert access["admin_approved"] is True
    assert access["allowed"] is True


@pytest.mark.asyncio
async def test_eligible_user_can_open_files_page():
    """The gating fix is reachable through the real route."""
    admin = await auth.register_user("admin", "password123")
    regular = await auth.register_user("regular", "password123")
    await _make_eligible(regular["id"], admin["id"])

    async with await client_for(regular["id"]) as client:
        resp = await client.get("/files", follow_redirects=False)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unapproved_user_is_denied_file_access():
    """Revoking approval alone is enough to deny access."""
    admin = await auth.register_user("admin", "password123")
    regular = await auth.register_user("regular", "password123")
    await _make_eligible(regular["id"], admin["id"])

    db = await get_db()
    await db.execute(
        "UPDATE users SET file_upload_allowed = 0 WHERE id = ?", (regular["id"],)
    )
    await db.commit()

    async with await client_for(regular["id"]) as client:
        resp = await client.get("/files", follow_redirects=False)

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_records_a_streak_of_one():
    """A fresh login must count toward the streak on the day it happens."""
    await auth.register_user("solo", "password123")
    user = await auth.authenticate("solo", "password123")
    assert await auth.get_login_streak(user["id"]) == 1

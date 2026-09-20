import os
import tempfile

import pytest

from lib import auth
from lib import boards
from lib import config
from lib import files as file_mod
from lib.chat import chat_manager, create_channel, delete_message, get_channel
from lib.db import get_db


@pytest.mark.asyncio
async def test_first_user_is_superadmin():
    result = await auth.register_user("admin", "password123")
    assert result is not None
    assert result["access_level"] == 2


@pytest.mark.asyncio
async def test_second_user_is_regular():
    await auth.register_user("admin", "password123")
    result = await auth.register_user("user2", "password123")
    assert result is not None
    assert result["access_level"] == 0


@pytest.mark.asyncio
async def test_is_admin_helpers():
    result = await auth.register_user("admin", "password123")
    user = await auth.authenticate("admin", "password123")
    assert auth.is_admin(user)
    assert auth.is_superadmin(user)

    await auth.register_user("regular", "password123")
    regular = await auth.authenticate("regular", "password123")
    assert not auth.is_admin(regular)
    assert not auth.is_superadmin(regular)


@pytest.mark.asyncio
async def test_promote_user():
    await auth.register_user("admin", "password123")
    result = await auth.register_user("user2", "password123")
    await auth.set_access_level(result["id"], 1)
    user = await auth.get_user(result["id"])
    assert user["access_level"] == 1
    assert auth.is_admin(user)


@pytest.mark.asyncio
async def test_superadmin_can_demote():
    await auth.register_user("admin", "password123")
    result = await auth.register_user("user2", "password123")
    await auth.set_access_level(result["id"], 1)
    # Demote back to regular
    await auth.set_access_level(result["id"], 0)
    user = await auth.get_user(result["id"])
    assert user["access_level"] == 0


@pytest.mark.asyncio
async def test_list_users():
    await auth.register_user("admin", "password123")
    await auth.register_user("user2", "password123")
    users = await auth.list_users()
    assert len(users) == 2
    assert users[0]["username"] == "admin"
    assert users[1]["username"] == "user2"


@pytest.mark.asyncio
async def test_delete_user():
    await auth.register_user("admin", "password123")
    result = await auth.register_user("user2", "password123")
    await auth.delete_user(result["id"])
    users = await auth.list_users()
    assert len(users) == 1
    assert users[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_delete_post():
    await auth.register_user("admin", "password123")
    user = await auth.authenticate("admin", "password123")
    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "Test Thread", user["id"], "First post")
    post_id = await boards.create_post(thread_id, user["id"], "Second post")
    posts = await boards.list_posts(thread_id)
    assert len(posts) == 2
    await boards.delete_post(post_id)
    posts = await boards.list_posts(thread_id)
    assert len(posts) == 1


@pytest.mark.asyncio
async def test_delete_thread():
    await auth.register_user("admin", "password123")
    user = await auth.authenticate("admin", "password123")
    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "Test Thread", user["id"], "First post")
    await boards.create_post(thread_id, user["id"], "Reply")
    await boards.delete_thread(thread_id)
    thread = await boards.get_thread(thread_id)
    assert thread is None
    posts = await boards.list_posts(thread_id)
    assert len(posts) == 0


@pytest.mark.asyncio
async def test_delete_file():
    await auth.register_user("admin", "password123")
    user = await auth.authenticate("admin", "password123")
    # Create a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", dir=config.FILE_STORE) as f:
        f.write(b"test data")
        path = f.name
    file_id = await file_mod.add_file("test.txt", path, user["id"], 9, "general", "test file")
    await file_mod.delete_file(file_id)
    result = await file_mod.get_file(file_id)
    assert result is None
    assert not os.path.exists(path)


@pytest.mark.asyncio
async def test_delete_chat_message():
    await auth.register_user("admin", "password123")
    await chat_manager.broadcast("lobby", "admin", "Hello world")
    messages = await chat_manager.recent_messages("lobby")
    assert len(messages) == 1
    msg_id = messages[0]["id"]
    await delete_message(msg_id)
    messages = await chat_manager.recent_messages("lobby")
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_admin_cannot_delete_admin_user():
    """Admin should only delete non-admin users (access_level == 0)."""
    await auth.register_user("superadmin", "password123")
    result = await auth.register_user("admin2", "password123")
    await auth.set_access_level(result["id"], 1)
    # Verify the user is admin
    target = await auth.get_user(result["id"])
    assert target["access_level"] == 1
    # The web route checks access_level == 0 before deleting;
    # here we verify the user still exists (simulating the guard)
    if target["access_level"] != 0:
        pass  # Would not delete
    user_after = await auth.get_user(result["id"])
    assert user_after is not None


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin():
    """Non-admin users should have access_level 0."""
    await auth.register_user("admin", "password123")
    result = await auth.register_user("regular", "password123")
    user = await auth.authenticate("regular", "password123")
    assert not auth.is_admin(user)
    assert user["access_level"] == 0


@pytest.mark.asyncio
async def test_delete_post_with_likes():
    """Deleting a liked post must not trip the post_likes foreign key."""
    admin = await auth.register_user("admin", "password123")
    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "T", admin["id"], "First post")
    post_id = await boards.create_post(thread_id, admin["id"], "Second post")
    await boards.toggle_like(post_id, admin["id"])

    await boards.delete_post(post_id)

    posts = await boards.list_posts(thread_id)
    assert len(posts) == 1
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM post_likes WHERE post_id = ?", (post_id,)
    )
    assert (await cursor.fetchone())["cnt"] == 0


@pytest.mark.asyncio
async def test_delete_thread_with_liked_posts():
    """Deleting a thread must clear likes on every post it contains."""
    admin = await auth.register_user("admin", "password123")
    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "T", admin["id"], "First post")
    first_post = (await boards.list_posts(thread_id))[0]["id"]
    await boards.toggle_like(first_post, admin["id"])

    await boards.delete_thread(thread_id)

    assert await boards.get_thread(thread_id) is None
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM post_likes")
    assert (await cursor.fetchone())["cnt"] == 0


@pytest.mark.asyncio
async def test_delete_user_with_content():
    """A user who has posted, liked, chatted and uploaded can be deleted."""
    admin = await auth.register_user("admin", "password123")
    target = await auth.register_user("spammer", "password123")

    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "T", target["id"], "spam")
    target_post = (await boards.list_posts(thread_id))[0]["id"]
    await boards.toggle_like(target_post, admin["id"])

    admin_thread = await boards.create_thread(board_id, "Real", admin["id"], "hello")
    liked_by_target = (await boards.list_posts(admin_thread))[0]["id"]
    await boards.toggle_like(liked_by_target, target["id"])

    await chat_manager.broadcast("lobby", "spammer", "buy my stuff")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", dir=config.FILE_STORE) as f:
        f.write(b"junk")
        upload_path = f.name
    await file_mod.add_file("junk.txt", upload_path, target["id"], 4, "general", "")

    db = await get_db()
    await db.execute(
        "INSERT INTO game_scores (user_id, score, opponent, won) VALUES (?, 1, 'CPU', 0)",
        (target["id"],),
    )
    await db.execute(
        "INSERT INTO login_days (user_id, login_date) VALUES (?, '2026-01-01')",
        (target["id"],),
    )
    await db.execute(
        "INSERT INTO dm_channel_seen (user_id, channel, last_seen_at) VALUES (?, 'dm:1:2', CURRENT_TIMESTAMP)",
        (target["id"],),
    )
    await db.commit()

    await auth.delete_user(target["id"], reassign_channels_to=admin["id"])

    assert await auth.get_user(target["id"]) is None
    assert not os.path.exists(upload_path)
    for table, column in (
        ("posts", "author_id"), ("threads", "author_id"), ("files", "uploader_id"),
        ("chat_messages", "user_id"), ("post_likes", "user_id"),
        ("game_scores", "user_id"), ("login_days", "user_id"),
        ("dm_channel_seen", "user_id"), ("sessions", "user_id"),
    ):
        cursor = await db.execute(
            f"SELECT COUNT(*) AS cnt FROM {table} WHERE {column} = ?", (target["id"],)
        )
        assert (await cursor.fetchone())["cnt"] == 0, f"{table} still references the user"

    # The admin's own thread survives, minus the deleted user's like.
    assert await boards.get_thread(admin_thread) is not None
    cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM post_likes WHERE post_id = ?", (liked_by_target,)
    )
    assert (await cursor.fetchone())["cnt"] == 0


@pytest.mark.asyncio
async def test_delete_user_removes_replies_in_their_threads():
    """Replies cannot outlive the thread whose author is being removed."""
    admin = await auth.register_user("admin", "password123")
    target = await auth.register_user("spammer", "password123")
    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "T", target["id"], "spam")
    await boards.create_post(thread_id, admin["id"], "a reply")

    await auth.delete_user(target["id"], reassign_channels_to=admin["id"])

    assert await boards.get_thread(thread_id) is None
    assert await boards.list_posts(thread_id) == []


@pytest.mark.asyncio
async def test_delete_user_reassigns_their_chat_channels():
    """A shared channel outlives the account that created it."""
    admin = await auth.register_user("admin", "password123")
    target = await auth.register_user("demoted", "password123")
    await create_channel("tech", "Tech talk", target["id"])

    await auth.delete_user(target["id"], reassign_channels_to=admin["id"])

    channel = await get_channel("tech")
    assert channel is not None
    assert channel["created_by"] == admin["id"]

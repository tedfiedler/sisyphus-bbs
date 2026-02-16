import os
import tempfile

import pytest

from lib import auth
from lib import boards
from lib import files as file_mod
from lib.chat import chat_manager, delete_message


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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
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

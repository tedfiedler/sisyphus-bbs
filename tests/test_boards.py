import pytest

import auth
import boards


@pytest.mark.asyncio
async def test_create_and_list_boards():
    board_id = await boards.create_board("General", "General discussion")
    assert board_id is not None

    board_list = await boards.list_boards()
    assert len(board_list) == 1
    assert board_list[0]["name"] == "General"


@pytest.mark.asyncio
async def test_get_board():
    board_id = await boards.create_board("Tech", "Technology talk")
    board = await boards.get_board(board_id)
    assert board is not None
    assert board["name"] == "Tech"
    assert board["description"] == "Technology talk"


@pytest.mark.asyncio
async def test_get_nonexistent_board():
    board = await boards.get_board(9999)
    assert board is None


@pytest.mark.asyncio
async def test_create_thread_and_posts():
    user = await auth.register_user("poster", "pass1234")
    board_id = await boards.create_board("Test Board")

    thread_id = await boards.create_thread(board_id, "Hello World", user["id"], "First post!")
    assert thread_id is not None

    thread = await boards.get_thread(thread_id)
    assert thread["subject"] == "Hello World"

    post_list = await boards.list_posts(thread_id)
    assert len(post_list) == 1
    assert post_list[0]["body"] == "First post!"


@pytest.mark.asyncio
async def test_reply_to_thread():
    user = await auth.register_user("poster", "pass1234")
    board_id = await boards.create_board("Test Board")
    thread_id = await boards.create_thread(board_id, "Topic", user["id"], "OP")

    await boards.create_post(thread_id, user["id"], "Reply 1")
    await boards.create_post(thread_id, user["id"], "Reply 2")

    post_list = await boards.list_posts(thread_id)
    assert len(post_list) == 3


@pytest.mark.asyncio
async def test_thread_list_ordering():
    user = await auth.register_user("poster", "pass1234")
    board_id = await boards.create_board("Test Board")

    await boards.create_thread(board_id, "Thread A", user["id"], "A")
    await boards.create_thread(board_id, "Thread B", user["id"], "B")

    thread_list = await boards.list_threads(board_id)
    assert len(thread_list) == 2

import asyncio

import pytest

import auth
from chat import ChatManager


@pytest.mark.asyncio
async def test_broadcast_and_subscribe():
    manager = ChatManager()
    await auth.register_user("chatter", "pass1234")

    queue = manager.subscribe("lobby")
    await manager.broadcast("lobby", "chatter", "Hello everyone!")

    msg = await asyncio.wait_for(queue.get(), timeout=2)
    assert msg["username"] == "chatter"
    assert msg["message"] == "Hello everyone!"
    assert msg["channel"] == "lobby"

    manager.unsubscribe("lobby", queue)


@pytest.mark.asyncio
async def test_multiple_subscribers():
    manager = ChatManager()
    await auth.register_user("user1", "pass1234")

    q1 = manager.subscribe("lobby")
    q2 = manager.subscribe("lobby")

    await manager.broadcast("lobby", "user1", "Broadcast test")

    msg1 = await asyncio.wait_for(q1.get(), timeout=2)
    msg2 = await asyncio.wait_for(q2.get(), timeout=2)
    assert msg1["message"] == "Broadcast test"
    assert msg2["message"] == "Broadcast test"

    manager.unsubscribe("lobby", q1)
    manager.unsubscribe("lobby", q2)


@pytest.mark.asyncio
async def test_channel_isolation():
    manager = ChatManager()
    await auth.register_user("user1", "pass1234")

    q_lobby = manager.subscribe("lobby")
    q_tech = manager.subscribe("tech")

    await manager.broadcast("tech", "user1", "Tech message")

    msg = await asyncio.wait_for(q_tech.get(), timeout=2)
    assert msg["message"] == "Tech message"

    assert q_lobby.empty()

    manager.unsubscribe("lobby", q_lobby)
    manager.unsubscribe("tech", q_tech)


@pytest.mark.asyncio
async def test_recent_messages():
    manager = ChatManager()
    await auth.register_user("chatter", "pass1234")

    await manager.broadcast("lobby", "chatter", "msg1")
    await manager.broadcast("lobby", "chatter", "msg2")
    await manager.broadcast("lobby", "chatter", "msg3")

    # Drain subscriber queues
    recent = await manager.recent_messages("lobby", 10)
    assert len(recent) == 3
    assert recent[0]["message"] == "msg1"
    assert recent[2]["message"] == "msg3"


@pytest.mark.asyncio
async def test_unsubscribe():
    manager = ChatManager()
    await auth.register_user("chatter", "pass1234")

    queue = manager.subscribe("lobby")
    manager.unsubscribe("lobby", queue)

    await manager.broadcast("lobby", "chatter", "After unsub")
    assert queue.empty()

"""Chat WebSocket lifecycle: task cleanup on disconnect and frame handling.

The app is driven as a raw ASGI callable rather than through TestClient so
the handler runs in this test's own event loop, where its background tasks
can be inspected directly.
"""

import asyncio
import json

import pytest

from lib import auth
from lib.chat import chat_manager
from lib.web_server import app


class WsDriver:
    """Minimal ASGI websocket peer for the /ws/chat endpoint."""

    def __init__(self, token: str):
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._from_app: asyncio.Queue = asyncio.Queue()
        self._scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": "/ws/chat",
            "raw_path": b"/ws/chat",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"cookie", f"session_token={token}".encode())],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "subprotocols": [],
            "state": {},
        }
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        self._task = asyncio.create_task(
            app(self._scope, self._to_app.get, self._from_app.put), name="asgi-app"
        )
        await self._to_app.put({"type": "websocket.connect"})
        accept = await self.next_frame()
        assert accept["type"] == "websocket.accept", accept
        return self

    async def __aexit__(self, *exc):
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self._task, timeout=5)

    async def next_frame(self) -> dict:
        return await asyncio.wait_for(self._from_app.get(), timeout=5)

    async def next_json(self) -> dict:
        frame = await self.next_frame()
        return json.loads(frame["text"])

    async def send_json(self, payload: dict):
        await self._to_app.put(
            {"type": "websocket.receive", "text": json.dumps(payload)}
        )

    async def send_raw(self, text: str):
        await self._to_app.put({"type": "websocket.receive", "text": text})


def _pending_since(baseline: set) -> set:
    """Return tasks that appeared after *baseline* and are still running.

    Deliberately identity-based rather than name-based: the previous
    implementation spawned its loops through asyncio.gather, which names
    tasks automatically, so a name filter would not have seen the leak.
    """
    return {t for t in asyncio.all_tasks() if t not in baseline and not t.done()}


@pytest.mark.asyncio
async def test_disconnect_leaves_no_background_tasks():
    """asyncio.gather used to strand _send on a queue nothing would feed."""
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    baseline = asyncio.all_tasks()
    async with WsDriver(token) as ws:
        assert (await ws.next_json())["type"] == "history"
        # the app task plus the three handler loops
        assert len(_pending_since(baseline)) >= 4

    await asyncio.sleep(0)
    assert _pending_since(baseline) == set()


@pytest.mark.asyncio
async def test_repeated_connections_do_not_accumulate_tasks():
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    baseline = asyncio.all_tasks()
    for _ in range(5):
        async with WsDriver(token) as ws:
            await ws.next_json()
        await asyncio.sleep(0)

    assert _pending_since(baseline) == set()


@pytest.mark.asyncio
async def test_disconnect_unsubscribes_from_the_channel():
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    async with WsDriver(token) as ws:
        await ws.next_json()
        assert len(chat_manager._subscribers.get("lobby", [])) == 1

    assert chat_manager._subscribers.get("lobby", []) == []


@pytest.mark.asyncio
async def test_malformed_frame_does_not_kill_the_connection():
    """A bad frame used to raise JSONDecodeError and tear the socket down."""
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    async with WsDriver(token) as ws:
        await ws.next_json()

        await ws.send_raw("this is not json")
        error = await ws.next_json()
        assert error["type"] == "error"

        await ws.send_raw('["a", "list"]')
        error = await ws.next_json()
        assert error["type"] == "error"

        # Still usable afterwards.
        await ws.send_json({"message": "still here"})
        echoed = await ws.next_json()
        assert echoed["message"] == "still here"


@pytest.mark.asyncio
async def test_oversized_message_is_reported_not_broadcast():
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    async with WsDriver(token) as ws:
        await ws.next_json()
        await ws.send_json({"message": "x" * 2001})
        error = await ws.next_json()
        assert error["type"] == "error"

    assert await chat_manager.recent_messages("lobby") == []


@pytest.mark.asyncio
async def test_disconnect_is_clean_under_a_real_asgi_server():
    """Guard the cancellation path against the ASGI server's own task group.

    The driver above calls the app directly, so it cannot see cancellation
    escaping into the surrounding structured-concurrency scope. Starlette's
    TestClient runs the app the way uvicorn does, which is where raw
    asyncio.Task cancellation surfaced as a CancelledError on teardown.
    """
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    def _connect_and_disconnect() -> str:
        # TestClient brings its own event loop, so let the app open its own
        # database connection inside it rather than reusing this loop's.
        from starlette.testclient import TestClient
        from lib import db

        outer, db._db = db._db, None
        try:
            client = TestClient(app)
            client.cookies.set("session_token", token)
            with client.websocket_connect("/ws/chat") as ws:
                ws.receive_json()
                ws.send_json({"message": "hello"})
                ws.receive_json()
            return "clean"
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            return f"{type(exc).__name__}: {exc}"
        finally:
            db._db = outer

    assert await asyncio.to_thread(_connect_and_disconnect) == "clean"

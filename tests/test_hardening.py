"""Regression tests for the second security-hardening pass.

Each test pins one gap that was open before: cross-site WebSocket hijacking,
sockets outliving their session, unbounded request bodies and chat queues,
username enumeration by timing, raw session tokens at rest, the superadmin
signup race, admin privilege edge cases, upload filename/overwrite handling,
and the response headers.
"""

import asyncio
import os

import pytest

from lib import auth, boards, config
from lib import files as file_mod
from lib.chat import chat_manager
from lib.db import close_db, get_db
from lib.models import UserCreate, validate
from lib.web_server import app
from tests.helpers import anon_client, client_for
from tests.test_websocket import WsDriver


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

def _driver(token: str, **headers: str) -> WsDriver:
    driver = WsDriver(token)
    driver._scope["headers"] += [(k.encode(), v.encode()) for k, v in headers.items()]
    return driver


async def _handshake(driver: WsDriver) -> dict:
    """Open the socket and return the app's first frame, without asserting on it."""
    task = asyncio.create_task(app(driver._scope, driver._to_app.get, driver._from_app.put))
    await driver._to_app.put({"type": "websocket.connect"})
    frame = await driver.next_frame()
    await driver._to_app.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(task, timeout=5)
    return frame


@pytest.mark.asyncio
async def test_websocket_refuses_cross_origin_handshake():
    """Another site's page must not be able to open the chat socket as the user."""
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    frame = await _handshake(_driver(token, host="bbs.example", origin="https://evil.example"))

    assert frame["type"] == "websocket.close", frame


@pytest.mark.asyncio
async def test_websocket_refuses_opaque_origin():
    """Sandboxed iframes and file:// pages send ``Origin: null``."""
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    frame = await _handshake(_driver(token, host="bbs.example", origin="null"))

    assert frame["type"] == "websocket.close", frame


@pytest.mark.asyncio
async def test_websocket_accepts_same_origin_and_configured_origins(monkeypatch):
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    frame = await _handshake(_driver(token, host="bbs.example:8000", origin="http://bbs.example:8000"))
    assert frame["type"] == "websocket.accept", frame

    monkeypatch.setattr(config, "ALLOWED_ORIGINS", frozenset({"https://chat.example"}), raising=False)
    frame = await _handshake(_driver(token, host="internal:8000", origin="https://chat.example"))
    assert frame["type"] == "websocket.accept", frame


@pytest.mark.asyncio
async def test_websocket_closes_once_session_is_gone(monkeypatch):
    """Logging out must end sockets opened earlier, not just future requests."""
    from lib.routes import chat_routes

    monkeypatch.setattr(chat_routes, "_PING_INTERVAL", 0.05, raising=False)
    # Pre-fix code slept on a literal 20; make that fast too so the test
    # fails on the missing check rather than on a timeout.
    real_sleep = asyncio.sleep
    monkeypatch.setattr(chat_routes.asyncio, "sleep", lambda _s: real_sleep(0.05))

    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    driver = WsDriver(token)
    driver._task = asyncio.create_task(app(driver._scope, driver._to_app.get, driver._from_app.put))
    await driver._to_app.put({"type": "websocket.connect"})
    assert (await driver.next_frame())["type"] == "websocket.accept"
    assert (await driver.next_json())["type"] == "history"

    await auth.delete_session(token)

    closed = None
    for _ in range(10):
        frame = await driver.next_frame()
        if frame["type"] == "websocket.close":
            closed = frame
            break
    await driver._to_app.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(driver._task, timeout=5)

    assert closed is not None, "socket stayed open after its session was deleted"
    assert closed["code"] == 4001


@pytest.mark.asyncio
async def test_websocket_rate_limits_messages():
    from lib.routes import chat_routes

    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])
    budget = chat_routes._ws_limiter.max_events

    async with WsDriver(token) as ws:
        await ws.next_json()  # history
        for i in range(budget + 5):
            await ws.send_json({"message": f"spam {i}"})
        frames = [await ws.next_json() for _ in range(budget + 5)]

    delivered = [f for f in frames if f.get("message", "").startswith("spam")]
    errors = [f for f in frames if f.get("type") == "error"]
    assert len(delivered) == budget
    assert len(errors) == 5
    assert len(await chat_manager.recent_messages("lobby", limit=500)) == budget


@pytest.mark.asyncio
async def test_websocket_rejects_oversized_frame_and_non_string_channel():
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    async with WsDriver(token) as ws:
        await ws.next_json()  # history
        await ws.send_raw('{"message": "' + "a" * 100_000 + '"}')
        assert (await ws.next_json())["message"] == "Message too large."

        # Used to raise TypeError inside the handler and drop the connection.
        await ws.send_json({"type": "switch", "channel": ["lobby"]})
        assert (await ws.next_json())["type"] == "error"

        # Still alive and usable afterwards.
        await ws.send_json({"message": "still here"})
        assert (await ws.next_json())["message"] == "still here"


@pytest.mark.asyncio
async def test_stalled_subscriber_queue_is_bounded():
    """A client that stops reading must not accumulate messages without limit."""
    await auth.register_user("alice", "password123")
    queue = chat_manager.subscribe("lobby")
    try:
        for i in range(400):
            await asyncio.wait_for(chat_manager.broadcast("lobby", "alice", f"m{i}"), timeout=5)
        assert queue.qsize() <= 256
    finally:
        chat_manager.unsubscribe("lobby", queue)


# ---------------------------------------------------------------------------
# Request body size
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oversized_body_rejected_before_auth():
    async with anon_client() as client:
        resp = await client.post(
            "/login",
            content=b"username=a&password=" + b"x" * (2 * 1024 * 1024),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_oversized_chunked_body_rejected():
    """No Content-Length to check, so the bytes have to be counted as they arrive."""
    async def chunks():
        yield b"csrf_token=x&body="
        for _ in range(40):
            yield b"x" * 65536

    user = await auth.register_user("alice", "password123")
    async with await client_for(user["id"]) as client:
        resp = await client.post(
            "/thread/1/reply", content=chunks(),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_upload_endpoint_still_takes_files_above_the_default_limit():
    admin = await auth.register_user("admin", "password123")
    async with await client_for(admin["id"]) as client:
        resp = await client.post(
            "/files/upload",
            files={"file": ("big.txt", b"x" * (2 * 1024 * 1024))},
            data={"area": "general"},
        )
    assert resp.status_code == 302
    assert len(await file_mod.list_files()) == 1


# ---------------------------------------------------------------------------
# Authentication and sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_username_costs_a_bcrypt_check(monkeypatch):
    """Otherwise response time tells an attacker which usernames exist."""
    calls = []
    real = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda pw, h: calls.append(h) or real(pw, h))

    assert await auth.authenticate("nobody", "password123") is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_session_token_is_not_stored_in_the_clear():
    user = await auth.register_user("alice", "password123")
    token = await auth.create_session(user["id"])

    db = await get_db()
    cursor = await db.execute("SELECT token FROM sessions")
    stored = [row["token"] for row in await cursor.fetchall()]

    assert token not in stored
    assert await auth.get_user_by_token(token) is not None
    # What is in the table must not work as a credential either.
    assert await auth.get_user_by_token(stored[0]) is None

    await auth.delete_session(token)
    assert await auth.get_user_by_token(token) is None


@pytest.mark.asyncio
async def test_legacy_plaintext_sessions_are_purged_on_startup():
    user = await auth.register_user("alice", "password123")
    live = await auth.create_session(user["id"])
    db = await get_db()
    await db.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user["id"], "legacy-plaintext-token", "2999-01-01T00:00:00+00:00"),
    )
    await db.commit()

    await close_db()
    db = await get_db()

    cursor = await db.execute("SELECT token FROM sessions")
    tokens = [row["token"] for row in await cursor.fetchall()]
    assert "legacy-plaintext-token" not in tokens
    assert await auth.get_user_by_token(live) is not None


@pytest.mark.asyncio
async def test_concurrent_first_signups_yield_one_superadmin():
    results = await asyncio.gather(*(
        auth.register_user(f"user{i}", "password123") for i in range(4)
    ))
    levels = sorted(r["access_level"] for r in results)
    assert levels == [0, 0, 0, 2]


@pytest.mark.asyncio
async def test_username_uniqueness_ignores_case():
    assert await auth.register_user("admin", "password123") is not None
    assert await auth.register_user("Admin", "password123") is None
    assert await auth.register_user("ADMIN", "password123") is None


def test_new_passwords_need_eight_characters():
    _, error = validate(UserCreate, username="someone", password="seven77")
    assert error and "at least 8" in error
    form, error = validate(UserCreate, username="someone", password="eight888")
    assert error is None and form.password == "eight888"


@pytest.mark.asyncio
async def test_session_cookie_is_secure_behind_tls_proxy(monkeypatch):
    await auth.register_user("alice", "password123")
    creds = {"username": "alice", "password": "password123"}

    async with anon_client() as client:
        # Not trusted: a client-supplied header must not be believed.
        resp = await client.post("/login", data=creds, headers={"x-forwarded-proto": "https"})
        assert "secure" not in resp.headers["set-cookie"].lower()

        monkeypatch.setattr(config, "TRUST_PROXY", True)
        resp = await client.post("/login", data=creds, headers={"x-forwarded-proto": "https"})
        assert "secure" in resp.headers["set-cookie"].lower()


# ---------------------------------------------------------------------------
# Admin privilege edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_superadmin_cannot_be_demoted_or_downgraded_by_promote():
    boss = await auth.register_user("boss", "password123")
    async with await client_for(boss["id"]) as client:
        await client.post(f"/admin/users/{boss['id']}/demote")
        assert (await auth.get_user(boss["id"]))["access_level"] == 2

        await client.post(f"/admin/users/{boss['id']}/promote")
        assert (await auth.get_user(boss["id"]))["access_level"] == 2


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("report.txt", "report.txt"),
    ("../../etc/passwd.txt", "passwd.txt"),
    ("..\\..\\windows\\evil.txt", "evil.txt"),
    ('na"me\r\nX-Injected: 1.txt', "na_me__X-Injected_ 1.txt"),
    ("<img src=x onerror=alert(1)>.png", "_img src_x onerror_alert_1__.png"),
])
def test_sanitize_filename(raw, expected):
    assert file_mod.sanitize_filename(raw) == expected


def test_sanitize_filename_bounds_length_and_rejects_hidden():
    name = file_mod.sanitize_filename("a" * 5000 + ".txt")
    assert len(name) <= 100 and name.endswith(".txt")
    for bad in ("", ".htaccess", "..", "   "):
        with pytest.raises(ValueError):
            file_mod.sanitize_filename(bad)


def test_save_upload_never_overwrites(monkeypatch):
    """exists()-then-write raced; simulate the loser seeing a stale 'absent'."""
    first, _ = file_mod.save_upload("same.txt", b"first")

    from pathlib import Path
    real_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False if self.name == "same.txt" else real_exists(self))

    second, _ = file_mod.save_upload("same.txt", b"second")

    assert first != second
    assert open(first, "rb").read() == b"first"
    assert open(second, "rb").read() == b"second"


@pytest.mark.asyncio
async def test_delete_file_will_not_unlink_outside_the_store(tmp_path):
    admin = await auth.register_user("admin", "password123")
    outside = tmp_path / "precious.txt"
    outside.write_text("do not delete")
    file_id = await file_mod.add_file("x.txt", str(outside), admin["id"], 1)

    await file_mod.delete_file(file_id)

    assert await file_mod.get_file(file_id) is None
    assert outside.exists()


@pytest.mark.asyncio
async def test_upload_stores_sanitized_name_and_is_rate_limited(monkeypatch):
    from lib.routes import file_routes
    from lib.ratelimit import RateLimiter

    monkeypatch.setattr(file_routes, "_upload_limiter", RateLimiter(2, 3600), raising=False)
    admin = await auth.register_user("admin", "password123")
    async with await client_for(admin["id"]) as client:
        for _ in range(3):
            await client.post("/files/upload", files={"file": ("we;ird<name>.txt", b"data")})

    stored = await file_mod.list_files()
    assert len(stored) == 2
    assert {f["filename"] for f in stored} == {"we_ird_name_.txt"}
    for f in stored:
        os.unlink(f["path"])


# ---------------------------------------------------------------------------
# Boards and channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regular_user_posting_is_rate_limited():
    from lib.routes import board_routes

    await auth.register_user("admin", "password123")
    user = await auth.register_user("alice", "password123")
    board_id = await boards.create_board("general")
    thread_id = await boards.create_thread(board_id, "hi", user["id"], "first")
    budget = board_routes._post_limiter.max_events

    async with await client_for(user["id"]) as client:
        for i in range(budget):
            resp = await client.post(f"/thread/{thread_id}/reply", data={"body": f"reply {i}"})
            assert resp.status_code == 302
        resp = await client.post(f"/thread/{thread_id}/reply", data={"body": "one too many"})

    assert resp.status_code == 400
    assert len(await boards.list_posts(thread_id)) == budget + 1


@pytest.mark.asyncio
async def test_channel_name_and_description_are_bounded():
    from lib.chat import get_channel

    admin = await auth.register_user("admin", "password123")
    async with await client_for(admin["id"]) as client:
        await client.post("/chat/channels/create", data={"name": "a" * 200})
        await client.post("/chat/channels/create", data={"name": "ok", "description": "d" * 5000})

    assert await get_channel("a" * 200) is None
    assert len((await get_channel("ok"))["description"]) == 256


# ---------------------------------------------------------------------------
# Response headers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_present():
    async with anon_client() as client:
        resp = await client.get("/")
    csp = resp.headers["content-security-policy"]
    for directive in ("default-src 'self'", "object-src 'none'", "base-uri 'self'",
                      "form-action 'self'", "frame-ancestors 'none'"):
        assert directive in csp
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["cross-origin-opener-policy"] == "same-origin"
    assert "strict-transport-security" not in resp.headers


@pytest.mark.asyncio
async def test_hsts_sent_over_https_only():
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://testserver"
    ) as client:
        resp = await client.get("/")
    assert "max-age=" in resp.headers["strict-transport-security"]


@pytest.mark.asyncio
async def test_static_assets_stay_cacheable():
    async with anon_client() as client:
        resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") != "no-store"

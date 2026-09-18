"""CSRF protection on state-changing requests."""

import re

import pytest

from lib import auth, boards
from lib.chat import chat_manager
from lib.csrf import HEADER_NAME, token_for
from tests.helpers import anon_client, client_for


async def _superadmin():
    user = await auth.register_user("admin", "password123")
    return user


@pytest.mark.asyncio
async def test_post_without_token_is_rejected():
    admin = await _superadmin()
    async with await client_for(admin["id"], csrf=False) as client:
        resp = await client.post(
            "/boards/create", data={"name": "General"}, follow_redirects=False
        )
    assert resp.status_code == 403
    assert await boards.list_boards() == []


@pytest.mark.asyncio
async def test_post_with_wrong_token_is_rejected():
    admin = await _superadmin()
    async with await client_for(admin["id"], csrf=False) as client:
        resp = await client.post(
            "/boards/create",
            data={"name": "General", "csrf_token": "0" * 64},
            follow_redirects=False,
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_another_sessions_token_is_rejected():
    admin = await _superadmin()
    other = await auth.register_user("mallory", "password123")
    other_token = token_for(await auth.create_session(other["id"]))

    async with await client_for(admin["id"], csrf=False) as client:
        resp = await client.post(
            "/boards/create",
            data={"name": "General", "csrf_token": other_token},
            follow_redirects=False,
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_with_form_field_succeeds():
    admin = await _superadmin()
    session = await auth.create_session(admin["id"])

    async with anon_client() as client:
        client.cookies.set("session_token", session)
        resp = await client.post(
            "/boards/create",
            data={"name": "General", "csrf_token": token_for(session)},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert len(await boards.list_boards()) == 1


@pytest.mark.asyncio
async def test_post_with_header_succeeds():
    admin = await _superadmin()
    session = await auth.create_session(admin["id"])

    async with anon_client() as client:
        client.cookies.set("session_token", session)
        resp = await client.post(
            "/boards/create",
            data={"name": "General"},
            headers={HEADER_NAME: token_for(session)},
            follow_redirects=False,
        )
    assert resp.status_code == 302


@pytest.mark.asyncio
async def test_multipart_upload_is_protected_and_still_works():
    """The middleware buffers and replays the body, so uploads must survive it."""
    admin = await _superadmin()
    session = await auth.create_session(admin["id"])

    async with anon_client() as client:
        client.cookies.set("session_token", session)
        blocked = await client.post(
            "/files/upload",
            files={"file": ("note.txt", b"hello", "text/plain")},
            data={"area": "general"},
            follow_redirects=False,
        )
        allowed = await client.post(
            "/files/upload",
            files={"file": ("note.txt", b"hello", "text/plain")},
            data={"area": "general", "csrf_token": token_for(session)},
            follow_redirects=False,
        )

    assert blocked.status_code == 403
    assert allowed.status_code == 302
    from lib import files as file_mod
    uploaded = await file_mod.list_files()
    assert len(uploaded) == 1
    assert uploaded[0]["filename"] == "note.txt"


@pytest.mark.asyncio
async def test_login_and_register_need_no_token():
    async with anon_client() as client:
        registered = await client.post(
            "/register",
            data={"username": "newcomer", "password": "password123"},
            follow_redirects=False,
        )
        assert registered.status_code == 302

    async with anon_client() as client:
        logged_in = await client.post(
            "/login",
            data={"username": "newcomer", "password": "password123"},
            follow_redirects=False,
        )
    assert logged_in.status_code == 302


@pytest.mark.asyncio
async def test_get_requests_are_unaffected():
    admin = await _superadmin()
    async with await client_for(admin["id"], csrf=False) as client:
        assert (await client.get("/home")).status_code == 200


@pytest.mark.asyncio
async def test_logout_is_post_only():
    admin = await _superadmin()
    async with await client_for(admin["id"]) as client:
        assert (await client.get("/logout", follow_redirects=False)).status_code == 405
        assert (await client.post("/logout", follow_redirects=False)).status_code == 302


@pytest.mark.asyncio
async def test_logout_without_token_is_rejected():
    """A GET logout was triggerable cross-site even with SameSite=Lax."""
    admin = await _superadmin()
    async with await client_for(admin["id"], csrf=False) as client:
        assert (await client.post("/logout", follow_redirects=False)).status_code == 403


FORM_RE = re.compile(r'<form\b[^>]*method="post"[^>]*>(.*?)</form>', re.IGNORECASE | re.DOTALL)
EXEMPT_ACTIONS = ("/login", "/register")


@pytest.mark.asyncio
async def test_every_rendered_form_carries_a_token():
    """Audit the real pages so a form added later cannot silently 403."""
    admin = await _superadmin()
    regular = await auth.register_user("ted", "password123")
    board_id = await boards.create_board("General")
    thread_id = await boards.create_thread(board_id, "Subject", admin["id"], "body")
    await chat_manager.broadcast("lobby", "admin", "hello")

    pages = [
        "/home", "/boards", f"/boards/{board_id}", f"/thread/{thread_id}",
        "/chat", "/files", "/admin", "/online", f"/user/{admin['id']}",
        f"/user/{regular['id']}", "/games", "/games/mille",
    ]

    checked = 0
    async with await client_for(admin["id"]) as client:
        for page in pages:
            resp = await client.get(page)
            assert resp.status_code == 200, f"{page} -> {resp.status_code}"
            for match in FORM_RE.finditer(resp.text):
                tag = match.group(0)
                if any(f'action="{a}"' in tag for a in EXEMPT_ACTIONS):
                    continue
                assert 'name="csrf_token"' in match.group(1), (
                    f"form without CSRF token on {page}: {tag[:120]}"
                )
                checked += 1

    assert checked >= 15, f"audit only saw {checked} forms; expected the full set"

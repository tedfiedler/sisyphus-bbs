"""Per-request database work: the session is resolved once, and not at all
for static assets."""

import pytest

from lib import auth
from tests.helpers import anon_client, client_for


@pytest.fixture
def count_token_lookups(monkeypatch):
    """Count calls to get_user_by_token across the whole app for one request."""
    calls = []
    original = auth.get_user_by_token

    async def counting(token):
        calls.append(token)
        return await original(token)

    # Patch every module that resolved the token independently.
    monkeypatch.setattr(auth, "get_user_by_token", counting)
    import lib.web_server as web_server
    import lib.deps as deps
    monkeypatch.setattr(web_server._auth, "get_user_by_token", counting)
    monkeypatch.setattr(deps.auth, "get_user_by_token", counting)
    return calls


@pytest.mark.asyncio
async def test_authenticated_page_resolves_the_session_once(count_token_lookups):
    """The middleware and the route dependency used to each do their own lookup."""
    user = await auth.register_user("alice", "password123")

    async with await client_for(user["id"]) as client:
        resp = await client.get("/home")

    assert resp.status_code == 200
    assert len(count_token_lookups) == 1


@pytest.mark.asyncio
async def test_static_assets_do_no_session_work(count_token_lookups):
    """Every stylesheet fetch used to trigger a token lookup plus file-access checks."""
    user = await auth.register_user("alice", "password123")

    async with await client_for(user["id"]) as client:
        resp = await client.get("/static/style.css")

    assert resp.status_code == 200
    assert count_token_lookups == []


@pytest.mark.asyncio
async def test_anonymous_request_does_no_lookup(count_token_lookups):
    async with anon_client() as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    assert count_token_lookups == []


@pytest.mark.asyncio
async def test_nav_flags_still_computed_for_pages():
    """Skipping work must not break the flags the base template reads."""
    admin = await auth.register_user("admin", "password123")

    async with await client_for(admin["id"]) as client:
        resp = await client.get("/home")

    # Admins always have file access, so the nav link must render.
    assert '<a href="/files">Files</a>' in resp.text


@pytest.mark.asyncio
async def test_auth_still_enforced_after_reuse():
    """The cached user must not leak across unauthenticated requests."""
    async with anon_client() as client:
        resp = await client.get("/home", follow_redirects=False)
    assert resp.status_code == 302

    async with anon_client() as client:
        client.cookies.set("session_token", "not-a-real-token")
        resp = await client.get("/home", follow_redirects=False)
    assert resp.status_code == 302

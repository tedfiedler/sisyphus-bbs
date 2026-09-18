"""Shared helpers for route-level tests."""

import httpx

from lib import auth
from lib.csrf import HEADER_NAME, token_for
from lib.web_server import app


def anon_client() -> httpx.AsyncClient:
    """Return an HTTP client with no session cookie."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


async def client_for(user_id: int, csrf: bool = True) -> httpx.AsyncClient:
    """Return an HTTP client carrying a valid session cookie for the user.

    The session's CSRF token is sent as a header on every request so tests
    can POST without threading a hidden field through each call. Pass
    ``csrf=False`` to exercise the rejection path.
    """
    token = await auth.create_session(user_id)
    headers = {HEADER_NAME: token_for(token)} if csrf else {}
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        cookies={"session_token": token},
        headers=headers,
    )

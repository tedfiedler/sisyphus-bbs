"""CSRF protection for state-changing requests.

Each session gets a token derived from its session token with an HMAC keyed
on ``config.SECRET_KEY``. Nothing extra is stored: the token can always be
recomputed from the cookie, and an attacker who cannot read the cookie cannot
predict it — which holds even if ``SECRET_KEY`` is left at its default.

Templates render the token into a hidden ``csrf_token`` field (see
``_add_globals``); scripts may send it in an ``X-CSRF-Token`` header instead.
:class:`CSRFMiddleware` enforces it for every unsafe method, so a new route
is covered without the author having to remember anything.
"""

import hmac
from hashlib import sha256

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from lib import config

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Credential endpoints run before a session exists, so they have no token to
# check. They are safe to exempt: neither one performs an authenticated action
# on behalf of an existing session.
EXEMPT_PATHS = frozenset({"/login", "/register"})

FIELD_NAME = "csrf_token"
HEADER_NAME = "x-csrf-token"


def token_for(session_token: str | None) -> str:
    """Return the CSRF token belonging to a session token, or "" if anonymous."""
    if not session_token:
        return ""
    return hmac.new(
        config.SECRET_KEY.encode(), session_token.encode(), sha256
    ).hexdigest()


def is_valid(session_token: str | None, submitted: str | None) -> bool:
    """Return True if *submitted* is the token belonging to *session_token*."""
    expected = token_for(session_token)
    if not expected or not submitted:
        return False
    return hmac.compare_digest(expected, submitted)


def _replay(body: bytes):
    """Build a receive callable that serves an already-buffered request body."""
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


async def _buffer_body(receive) -> bytes | None:
    """Read the full request body, or None if the client disconnected."""
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            return b"".join(chunks)


async def _submitted_token(scope, body: bytes) -> str | None:
    """Pull the CSRF token from the request header or the form body."""
    header_token = Headers(scope=scope).get(HEADER_NAME)
    if header_token:
        return header_token
    request = Request(scope, _replay(body))
    try:
        form = await request.form()
    except Exception:
        return None
    try:
        value = form.get(FIELD_NAME)
        return value if isinstance(value, str) else None
    finally:
        await form.close()


class CSRFMiddleware:
    """Reject unsafe requests that do not carry their session's CSRF token.

    Written as raw ASGI rather than ``BaseHTTPMiddleware`` because the body
    has to be read here to find the token and then replayed for the route.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] not in UNSAFE_METHODS
            or scope["path"] in EXEMPT_PATHS
        ):
            await self.app(scope, receive, send)
            return

        body = await _buffer_body(receive)
        if body is None:
            return

        submitted = await _submitted_token(scope, body)
        session_token = Request(scope).cookies.get("session_token")
        if not is_valid(session_token, submitted):
            response = PlainTextResponse("CSRF verification failed", status_code=403)
            await response(scope, _replay(body), send)
            return

        await self.app(scope, _replay(body), send)

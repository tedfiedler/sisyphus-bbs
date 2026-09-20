"""FastAPI application setup, static file mounting, template configuration, and route registration."""

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from lib import auth as _auth
from lib import chat as _chat
from lib import config
from lib.bodylimit import BodySizeLimitMiddleware, upload_limit
from lib.csrf import CSRFMiddleware
from lib.proxy import is_https
# Re-exported so existing imports from this module keep working.
from lib.templating import templates, _add_globals  # noqa: F401

app = FastAPI(title=config.BBS_NAME)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


class _DMCheckMiddleware(BaseHTTPMiddleware):
    """Resolve the session once per request and precompute the nav flags.

    The resolved user is stashed on ``request.state`` so route dependencies
    reuse it instead of looking the token up a second time. Static assets
    need none of this, so they skip the database entirely.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        request.state.user_resolved = False
        request.state.has_unread_dm = False
        request.state.can_access_files = False

        if request.url.path.startswith("/static"):
            return await call_next(request)

        token = request.cookies.get("session_token")
        user = await _auth.get_user_by_token(token) if token else None
        request.state.user = user
        request.state.user_resolved = True
        if user:
            request.state.has_unread_dm = await _chat.has_unread_dms(user["id"])
            file_access = await _auth.check_file_access(user)
            request.state.can_access_files = file_access["allowed"]
        return await call_next(request)


app.add_middleware(_DMCheckMiddleware)


# No 'unsafe-inline': if markup is ever injected into a page, the browser
# will not run its <script>, on* handlers, or style attributes. That only
# works because the templates contain none of their own — scripts live in
# frontend/static/js, styles are classes in style.css, and page data reaches
# scripts through data-* attributes. tests/test_csp.py keeps it that way.
_CSP = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if is_https(request):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        # Pages are per-user; keep them out of shared and on-disk caches so
        # they cannot be read back after logout.
        if not request.url.path.startswith("/static"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


app.add_middleware(_SecurityHeadersMiddleware)

# Added last so it runs outermost: an unsafe request without a valid token is
# rejected before any session or database work happens.
app.add_middleware(CSRFMiddleware)

# Outside even CSRF, which buffers the whole body to find its token: the size
# cap has to apply before that read, and to unauthenticated requests too.
app.add_middleware(
    BodySizeLimitMiddleware,
    path_limits={"/files/upload": upload_limit(config.MAX_UPLOAD_BYTES)},
)




from lib.routes import auth_routes, board_routes, file_routes, chat_routes, admin_routes, game_routes, climb_routes  # noqa: E402

app.include_router(auth_routes.router)
app.include_router(board_routes.router)
app.include_router(file_routes.router)
app.include_router(chat_routes.router)
app.include_router(admin_routes.router)
app.include_router(game_routes.router)
app.include_router(climb_routes.router)

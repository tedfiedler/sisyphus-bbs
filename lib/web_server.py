"""FastAPI application setup, static file mounting, template configuration, and route registration."""

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from lib import auth as _auth
from lib import chat as _chat
from lib import config

app = FastAPI(title=config.BBS_NAME)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


class _DMCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.has_unread_dm = False
        token = request.cookies.get("session_token")
        if token:
            user = await _auth.get_user_by_token(token)
            if user:
                request.state.has_unread_dm = await _chat.has_unread_dms(user["id"])
        return await call_next(request)


app.add_middleware(_DMCheckMiddleware)


def _add_globals(request: Request, extra: dict | None = None) -> dict:
    """Build a template context dict with the request and global BBS settings, merged with any extra values."""
    ctx = {
        "request": request,
        "bbs_name": config.BBS_NAME,
        "has_unread_dm": getattr(request.state, "has_unread_dm", False),
    }
    if extra:
        ctx.update(extra)
    return ctx


from lib.routes import auth_routes, board_routes, file_routes, chat_routes, admin_routes, game_routes  # noqa: E402

app.include_router(auth_routes.router)
app.include_router(board_routes.router)
app.include_router(file_routes.router)
app.include_router(chat_routes.router)
app.include_router(admin_routes.router)
app.include_router(game_routes.router)

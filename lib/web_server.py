"""FastAPI application setup, static file mounting, template configuration, and route registration."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lib import config

app = FastAPI(title=config.BBS_NAME)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def _add_globals(request: Request, extra: dict | None = None) -> dict:
    """Build a template context dict with the request and global BBS settings, merged with any extra values."""
    ctx = {"request": request, "bbs_name": config.BBS_NAME}
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

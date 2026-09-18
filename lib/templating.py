"""Jinja environment and the shared template context.

Kept separate from :mod:`lib.web_server` to break an import cycle: route
modules need ``templates`` and ``_add_globals``, while ``web_server`` imports
every route module to register its router. With both in one module, importing
a route module first left ``web_server`` half-initialized and raised
``AttributeError: ... has no attribute 'router'``.
"""

from fastapi import Request
from fastapi.templating import Jinja2Templates

from lib import config
from lib.csrf import token_for

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def _add_globals(request: Request, extra: dict | None = None) -> dict:
    """Build a template context with the request and global BBS settings."""
    ctx = {
        "request": request,
        "bbs_name": config.BBS_NAME,
        "has_unread_dm": getattr(request.state, "has_unread_dm", False),
        "can_access_files": getattr(request.state, "can_access_files", False),
        "csrf_token": token_for(request.cookies.get("session_token")),
    }
    if extra:
        ctx.update(extra)
    return ctx

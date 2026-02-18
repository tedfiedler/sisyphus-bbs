"""Authentication routes: login, registration, and logout.

Provides form-based authentication with session cookies. Includes
per-IP rate limiting on the login endpoint to mitigate brute-force attacks.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import config
from lib import auth
from lib.content_filter import contains_url
from lib.deps import require_user
from lib.web_server import templates, _add_globals

router = APIRouter()

# Rate limiting: track failed login attempts per IP
_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5       # max failures per window
_WINDOW_SECONDS = 300   # 5-minute window


def _is_rate_limited(ip: str) -> bool:
    """Check whether the given IP has exceeded the failed-login threshold."""
    now = time.monotonic()
    attempts = _login_attempts[ip]
    # Prune old entries
    _login_attempts[ip] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    return len(_login_attempts[ip]) >= _MAX_ATTEMPTS


def _record_failure(ip: str):
    """Record a failed login attempt timestamp for the given IP."""
    _login_attempts[ip].append(time.monotonic())


def _clear_failures(ip: str):
    """Remove all recorded failures for the given IP after a successful login."""
    _login_attempts.pop(ip, None)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the landing page. Redirect authenticated users to /boards."""
    token = request.cookies.get("session_token")
    user = await auth.get_user_by_token(token) if token else None
    if user:
        return RedirectResponse("/home", status_code=302)
    return templates.TemplateResponse("login.html", _add_globals(request))


@router.post("/register")
async def register(request: Request, username: str = Form(), password: str = Form(), email: str = Form("")):
    """Create a new user account, authenticate, and set the session cookie."""
    result = await auth.register_user(username, password, email)
    if result is None:
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Username already taken"}),
            status_code=400,
        )
    user = await auth.authenticate(username, password)
    token = await auth.create_session(user["id"])
    resp = RedirectResponse("/home", status_code=302)
    is_https = request.url.scheme == "https"
    resp.set_cookie("session_token", token, httponly=True, secure=is_https, samesite="Lax", max_age=config.SESSION_EXPIRY_HOURS * 3600)
    return resp


@router.post("/login")
async def login(request: Request, username: str = Form(), password: str = Form()):
    """Authenticate a user and set the session cookie.

    Rate-limited to ``_MAX_ATTEMPTS`` failures per ``_WINDOW_SECONDS`` per
    client IP. On success the failure counter is cleared.
    """
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip):
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Too many failed attempts. Try again later."}),
            status_code=429,
        )
    user = await auth.authenticate(username, password)
    if user is None:
        _record_failure(client_ip)
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Invalid credentials"}),
            status_code=401,
        )
    _clear_failures(client_ip)
    token = await auth.create_session(user["id"])
    resp = RedirectResponse("/home", status_code=302)
    is_https = request.url.scheme == "https"
    resp.set_cookie("session_token", token, httponly=True, secure=is_https, samesite="Lax", max_age=config.SESSION_EXPIRY_HOURS * 3600)
    return resp


@router.get("/home", response_class=HTMLResponse)
async def home(request: Request, user: dict = Depends(require_user)):
    """Display the home landing page with the Camus quote and superadmin message."""
    landing_message = await auth.get_landing_message()
    return templates.TemplateResponse(
        "home.html", _add_globals(request, {"user": user, "landing_message": landing_message})
    )


@router.get("/online", response_class=HTMLResponse)
async def online(request: Request, user: dict = Depends(require_user)):
    """Show the user directory with online status."""
    all_users = await auth.list_users_directory()
    return templates.TemplateResponse(
        "online.html", _add_globals(request, {"user": user, "all_users": all_users})
    )


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_profile(request: Request, user_id: int, user: dict = Depends(require_user)):
    """Display a user's profile page."""
    profile_user = await auth.get_user(user_id)
    if not profile_user:
        return RedirectResponse("/online", status_code=302)
    is_online = bool(
        profile_user.get("last_seen")
        and profile_user["last_seen"] > (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    )
    can_edit = user["id"] == user_id or auth.is_admin(user)
    return templates.TemplateResponse(
        "profile.html",
        _add_globals(request, {
            "user": user,
            "profile_user": profile_user,
            "is_online": is_online,
            "can_edit": can_edit,
        }),
    )


@router.post("/user/{user_id}/about")
async def update_about(request: Request, user_id: int, about_me: str = Form(""), user: dict = Depends(require_user)):
    """Update a user's About Me text."""
    if user["id"] != user_id and not auth.is_admin(user):
        return RedirectResponse(f"/user/{user_id}", status_code=302)
    if not auth.is_admin(user) and contains_url(about_me):
        profile_user = await auth.get_user(user_id)
        is_online = True
        can_edit = True
        return templates.TemplateResponse(
            "profile.html",
            _add_globals(request, {
                "user": user,
                "profile_user": profile_user,
                "is_online": is_online,
                "can_edit": can_edit,
                "error": "URLs are not allowed in About Me.",
            }),
        )
    await auth.update_about_me(user_id, about_me)
    return RedirectResponse(f"/user/{user_id}", status_code=302)


@router.post("/user/{user_id}/landing-message")
async def update_landing_message(request: Request, user_id: int, landing_message: str = Form(""), user: dict = Depends(require_user)):
    """Update the landing page message (superadmin only)."""
    if not auth.is_superadmin(user) or user["id"] != user_id:
        return RedirectResponse(f"/user/{user_id}", status_code=302)
    await auth.update_landing_message(user_id, landing_message)
    return RedirectResponse(f"/user/{user_id}", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Destroy the user's session and clear the session cookie."""
    token = request.cookies.get("session_token")
    if token:
        await auth.delete_session(token)
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp

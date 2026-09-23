"""Authentication routes: login, registration, and logout.

Provides form-based authentication with session cookies. Includes
per-IP rate limiting on the login endpoint to mitigate brute-force attacks.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth, config, invites
from lib.content_filter import contains_url
from lib.deps import require_user
from lib.models import ProfileText, UserCreate, UserLogin, validate
from lib.proxy import is_https
from lib.ratelimit import RateLimiter, client_key
from lib.templating import templates, _add_globals

router = APIRouter()

# Failed logins per client, over a five-minute window.
_login_limiter = RateLimiter(max_events=5, window_seconds=300)

# Registrations per client per hour. Counts every attempt, not just failures,
# so one address cannot mass-create accounts. Kept loose enough that a shared
# address behind NAT is not locked out by a few neighbours signing up.
_register_limiter = RateLimiter(max_events=10, window_seconds=3600)


def _session_redirect(request: Request, token: str) -> RedirectResponse:
    """Build the post-login redirect carrying the session cookie."""
    resp = RedirectResponse("/home", status_code=302)
    resp.set_cookie(
        "session_token", token,
        httponly=True, secure=is_https(request), samesite="Lax",
        max_age=config.SESSION_EXPIRY_HOURS * 3600,
    )
    return resp


def _login_page(request: Request, *, error: str | None = None, invite: str = "",
                show_register: bool = False, status_code: int = 200):
    """The landing page.

    Someone who arrived by an invitation link starts on the New User tab
    with the code already filled in; so does anyone whose registration
    just failed, with what they typed still there.
    """
    invite = invite.strip()[:invites.CODE_MAX]
    context = {
        "error": error,
        "invite_only": config.INVITE_ONLY,
        "invite": invite,
        "show_register": show_register or bool(invite),
    }
    return templates.TemplateResponse(
        "login.html", _add_globals(request, context), status_code=status_code,
    )


def _is_recently_seen(profile_user: dict | None) -> bool:
    """Return True if the profile's last_seen timestamp is within five minutes."""
    if not profile_user or not profile_user.get("last_seen"):
        return False
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    return profile_user["last_seen"] > cutoff



@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the landing page. Redirect authenticated users to /boards."""
    token = request.cookies.get("session_token")
    user = await auth.get_user_by_token(token) if token else None
    if user:
        return RedirectResponse("/home", status_code=302)
    return _login_page(request, invite=request.query_params.get("invite", ""))


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(),
    password: str = Form(),
    email: str = Form(""),
    invite: str = Form("", max_length=invites.CODE_MAX),
):
    """Create a new user account, authenticate, and set the session cookie.

    On an invite-only board the code is the door. It is claimed before the
    account is made, so two people cannot both get in on one code, and given
    back if the name turns out to be taken. On an open board a code is
    optional; a valid one still records who invited whom.
    """
    client = client_key(request)
    if _register_limiter.is_limited(client):
        return _login_page(
            request, error="Too many accounts created. Try again later.",
            invite=invite, show_register=True, status_code=429,
        )
    _register_limiter.record(client)
    form, error = validate(UserCreate, username=username, password=password, email=email)
    if error:
        return _login_page(request, error=error, invite=invite, show_register=True, status_code=400)
    username, password, email = form.username, form.password, form.email

    invite_id = await invites.claim(invite) if invite.strip() else None
    if config.INVITE_ONLY and invite_id is None:
        if invite.strip():
            error = "That invitation code is not valid. It may have been used already, or expired."
        else:
            error = "This board is invite-only. You need an invitation code to register."
        return _login_page(request, error=error, invite=invite, show_register=True, status_code=403)

    result = await auth.register_user(username, password, email)
    if result is None:
        if invite_id is not None:
            await invites.release(invite_id)
        return _login_page(
            request, error="Username already taken", invite=invite, show_register=True, status_code=400,
        )
    if invite_id is not None:
        await invites.assign(invite_id, result["id"])
    # authenticate() rather than using `result` directly: it also records the
    # first login day and last_login.
    user = await auth.authenticate(username, password) or result
    token = await auth.create_session(user["id"])
    return _session_redirect(request, token)


@router.post("/login")
async def login(request: Request, username: str = Form(), password: str = Form()):
    """Authenticate a user and set the session cookie.

    Rate-limited to ``_MAX_ATTEMPTS`` failures per ``_WINDOW_SECONDS`` per
    client IP. On success the failure counter is cleared.
    """
    form, error = validate(UserLogin, username=username, password=password)
    if error:
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Invalid credentials"}),
            status_code=401,
        )
    username, password = form.username, form.password
    client_ip = client_key(request)
    if _login_limiter.is_limited(client_ip):
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Too many failed attempts. Try again later."}),
            status_code=429,
        )
    user = await auth.authenticate(username, password)
    if user is None:
        _login_limiter.record(client_ip)
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Invalid credentials"}),
            status_code=401,
        )
    _login_limiter.clear(client_ip)
    token = await auth.create_session(user["id"])
    return _session_redirect(request, token)


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
    is_online = _is_recently_seen(profile_user)
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
    form, error = validate(ProfileText, text=about_me)
    if not error and not auth.is_admin(user) and contains_url(about_me):
        error = "URLs are not allowed in About Me."
    if error:
        profile_user = await auth.get_user(user_id)
        if profile_user:
            # Keep what the user typed so the edit is not lost on rejection.
            profile_user["about_me"] = about_me
        return templates.TemplateResponse(
            "profile.html",
            _add_globals(request, {
                "user": user,
                "profile_user": profile_user,
                "is_online": _is_recently_seen(profile_user),
                "can_edit": True,
                "error": error,
            }),
            status_code=400,
        )
    await auth.update_about_me(user_id, form.text)
    return RedirectResponse(f"/user/{user_id}", status_code=302)


@router.post("/user/{user_id}/landing-message")
async def update_landing_message(request: Request, user_id: int, landing_message: str = Form(""), user: dict = Depends(require_user)):
    """Update the landing page message (superadmin only)."""
    if not auth.is_superadmin(user) or user["id"] != user_id:
        return RedirectResponse(f"/user/{user_id}", status_code=302)
    form, error = validate(ProfileText, text=landing_message)
    if error:
        return RedirectResponse(f"/user/{user_id}", status_code=302)
    await auth.update_landing_message(user_id, form.text)
    return RedirectResponse(f"/user/{user_id}", status_code=302)


@router.post("/logout")
async def logout(request: Request):
    """Destroy the user's session and clear the session cookie.

    POST rather than GET: a SameSite=Lax cookie is still sent on top-level
    cross-site navigation, so a GET logout can be triggered from any page.
    """
    token = request.cookies.get("session_token")
    if token:
        await auth.delete_session(token)
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import config
from lib import auth
from lib.web_server import templates, _add_globals

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get("session_token")
    user = await auth.get_user_by_token(token) if token else None
    if user:
        return RedirectResponse("/boards", status_code=302)
    return templates.TemplateResponse("login.html", _add_globals(request))


@router.post("/register")
async def register(request: Request, username: str = Form(), password: str = Form(), email: str = Form("")):
    result = await auth.register_user(username, password, email)
    if result is None:
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Username already taken"}),
            status_code=400,
        )
    user = await auth.authenticate(username, password)
    token = await auth.create_session(user["id"])
    resp = RedirectResponse("/boards", status_code=302)
    resp.set_cookie("session_token", token, httponly=True, max_age=config.SESSION_EXPIRY_HOURS * 3600)
    return resp


@router.post("/login")
async def login(request: Request, username: str = Form(), password: str = Form()):
    user = await auth.authenticate(username, password)
    if user is None:
        return templates.TemplateResponse(
            "login.html", _add_globals(request, {"error": "Invalid credentials"}),
            status_code=401,
        )
    token = await auth.create_session(user["id"])
    resp = RedirectResponse("/boards", status_code=302)
    resp.set_cookie("session_token", token, httponly=True, max_age=config.SESSION_EXPIRY_HOURS * 3600)
    return resp


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        await auth.delete_session(token)
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp

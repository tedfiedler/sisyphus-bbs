import json
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
import auth
import boards
import files as file_mod
from chat import chat_manager, delete_message

app = FastAPI(title=config.BBS_NAME)
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def _add_globals(request: Request, extra: dict | None = None) -> dict:
    ctx = {"request": request, "bbs_name": config.BBS_NAME}
    if extra:
        ctx.update(extra)
    return ctx


async def _current_user(request: Request) -> dict | None:
    token = request.cookies.get("session_token")
    if not token:
        return None
    return await auth.get_user_by_token(token)


# --- Auth routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = await _current_user(request)
    if user:
        return RedirectResponse("/boards", status_code=302)
    return templates.TemplateResponse("login.html", _add_globals(request))


@app.post("/register")
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


@app.post("/login")
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


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        await auth.delete_session(token)
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp


# --- Board routes ---

@app.get("/boards", response_class=HTMLResponse)
async def board_list(request: Request):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    board_data = await boards.list_boards()
    return templates.TemplateResponse("boards.html", _add_globals(request, {"user": user, "boards": board_data}))


@app.post("/boards/create")
async def board_create(request: Request, name: str = Form(), description: str = Form("")):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    await boards.create_board(name, description)
    return RedirectResponse("/boards", status_code=302)


@app.get("/boards/{board_id}", response_class=HTMLResponse)
async def board_view(request: Request, board_id: int):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    board = await boards.get_board(board_id)
    if not board:
        return RedirectResponse("/boards", status_code=302)
    thread_list = await boards.list_threads(board_id)
    return templates.TemplateResponse(
        "thread.html", _add_globals(request, {"user": user, "board": board, "threads": thread_list, "posts": None, "thread": None})
    )


@app.post("/boards/{board_id}/thread")
async def thread_create(request: Request, board_id: int, subject: str = Form(), body: str = Form()):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    thread_id = await boards.create_thread(board_id, subject, user["id"], body)
    return RedirectResponse(f"/thread/{thread_id}", status_code=302)


@app.get("/thread/{thread_id}", response_class=HTMLResponse)
async def thread_view(request: Request, thread_id: int):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    thread = await boards.get_thread(thread_id)
    if not thread:
        return RedirectResponse("/boards", status_code=302)
    board = await boards.get_board(thread["board_id"])
    post_list = await boards.list_posts(thread_id)
    return templates.TemplateResponse(
        "thread.html", _add_globals(request, {"user": user, "board": board, "thread": thread, "posts": post_list, "threads": None})
    )


@app.post("/thread/{thread_id}/reply")
async def thread_reply(request: Request, thread_id: int, body: str = Form()):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    await boards.create_post(thread_id, user["id"], body)
    return RedirectResponse(f"/thread/{thread_id}", status_code=302)


# --- File routes ---

@app.get("/files", response_class=HTMLResponse)
async def file_list(request: Request, area: str | None = None):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    file_data = await file_mod.list_files(area)
    areas = await file_mod.list_areas()
    return templates.TemplateResponse(
        "files.html", _add_globals(request, {"user": user, "files": file_data, "areas": areas, "current_area": area})
    )


@app.post("/files/upload")
async def file_upload(
    request: Request,
    file: UploadFile = File(),
    area: str = Form("general"),
    description: str = Form(""),
):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    data = await file.read()
    path, size = file_mod.save_upload(file.filename, data, area)
    await file_mod.add_file(file.filename, path, user["id"], size, area, description)
    return RedirectResponse("/files", status_code=302)


@app.get("/files/download/{file_id}")
async def file_download(request: Request, file_id: int):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    f = await file_mod.get_file(file_id)
    if not f:
        return RedirectResponse("/files", status_code=302)
    await file_mod.increment_download(file_id)
    return FileResponse(f["path"], filename=f["filename"])


# --- Chat routes ---

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    user = await _current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    recent = await chat_manager.recent_messages()
    return templates.TemplateResponse(
        "chat.html", _add_globals(request, {"user": user, "recent_messages": recent})
    )


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    token = websocket.cookies.get("session_token")
    user = await auth.get_user_by_token(token) if token else None
    if not user:
        await websocket.close(code=4001)
        return

    channel = "lobby"
    queue = chat_manager.subscribe(channel)
    try:
        # Send recent history
        recent = await chat_manager.recent_messages(channel)
        for msg in recent:
            await websocket.send_json(msg)

        async def _recv():
            while True:
                data = await websocket.receive_text()
                parsed = json.loads(data)
                await chat_manager.broadcast(channel, user["username"], parsed.get("message", ""))

        async def _send():
            while True:
                msg = await queue.get()
                await websocket.send_json(msg)

        await asyncio.gather(_recv(), _send())
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        chat_manager.unsubscribe(channel, queue)


import asyncio  # noqa: E402 - needed for websocket handler


# --- Admin helpers ---

def _require_admin(user: dict | None) -> Response | None:
    """Return a 403 response if user is not admin, else None."""
    if not user or not auth.is_admin(user):
        return HTMLResponse("Forbidden", status_code=403)
    return None


# --- Admin routes ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    users = await auth.list_users()
    return templates.TemplateResponse(
        "admin.html", _add_globals(request, {"user": user, "users": users})
    )


@app.post("/admin/users/{user_id}/promote")
async def admin_promote(request: Request, user_id: int):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    target = await auth.get_user(user_id)
    if target:
        await auth.set_access_level(user_id, 1)
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/users/{user_id}/demote")
async def admin_demote(request: Request, user_id: int):
    user = await _current_user(request)
    if not user or not auth.is_superadmin(user):
        return HTMLResponse("Forbidden", status_code=403)
    target = await auth.get_user(user_id)
    if target:
        await auth.set_access_level(user_id, 0)
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/users/{user_id}/delete")
async def admin_delete_user(request: Request, user_id: int):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    target = await auth.get_user(user_id)
    if target and target["access_level"] == 0:
        await auth.delete_user(user_id)
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/post/{post_id}/delete")
async def admin_delete_post(request: Request, post_id: int):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    from db import get_db
    db = await get_db()
    cursor = await db.execute("SELECT thread_id FROM posts WHERE id = ?", (post_id,))
    row = await cursor.fetchone()
    thread_id = row["thread_id"] if row else None
    await boards.delete_post(post_id)
    if thread_id:
        return RedirectResponse(f"/thread/{thread_id}", status_code=302)
    return RedirectResponse("/boards", status_code=302)


@app.post("/admin/thread/{thread_id}/delete")
async def admin_delete_thread(request: Request, thread_id: int):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    thread = await boards.get_thread(thread_id)
    board_id = thread["board_id"] if thread else None
    await boards.delete_thread(thread_id)
    if board_id:
        return RedirectResponse(f"/boards/{board_id}", status_code=302)
    return RedirectResponse("/boards", status_code=302)


@app.post("/admin/file/{file_id}/delete")
async def admin_delete_file(request: Request, file_id: int):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    await file_mod.delete_file(file_id)
    return RedirectResponse("/files", status_code=302)


@app.post("/admin/chat/{message_id}/delete")
async def admin_delete_chat(request: Request, message_id: int):
    user = await _current_user(request)
    denied = _require_admin(user)
    if denied:
        return denied
    await delete_message(message_id)
    return RedirectResponse("/chat", status_code=302)

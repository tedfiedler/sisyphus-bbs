from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth
from lib import boards
from lib import files as file_mod
from lib.chat import delete_message
from lib.db import get_db
from lib.deps import require_admin
from lib.web_server import templates, _add_globals

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: dict = Depends(require_admin)):
    users = await auth.list_users()
    return templates.TemplateResponse(
        "admin.html", _add_globals(request, {"user": user, "users": users})
    )


@router.post("/admin/users/{user_id}/promote")
async def admin_promote(request: Request, user_id: int, user: dict = Depends(require_admin)):
    target = await auth.get_user(user_id)
    if target:
        await auth.set_access_level(user_id, 1)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/demote")
async def admin_demote(request: Request, user_id: int):
    from lib.deps import get_current_user
    user = await get_current_user(request)
    if not user or not auth.is_superadmin(user):
        return HTMLResponse("Forbidden", status_code=403)
    target = await auth.get_user(user_id)
    if target:
        await auth.set_access_level(user_id, 0)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def admin_delete_user(request: Request, user_id: int, user: dict = Depends(require_admin)):
    target = await auth.get_user(user_id)
    if target and target["access_level"] == 0:
        await auth.delete_user(user_id)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/post/{post_id}/delete")
async def admin_delete_post(request: Request, post_id: int, user: dict = Depends(require_admin)):
    db = await get_db()
    cursor = await db.execute("SELECT thread_id FROM posts WHERE id = ?", (post_id,))
    row = await cursor.fetchone()
    thread_id = row["thread_id"] if row else None
    await boards.delete_post(post_id)
    if thread_id:
        return RedirectResponse(f"/thread/{thread_id}", status_code=302)
    return RedirectResponse("/boards", status_code=302)


@router.post("/admin/thread/{thread_id}/delete")
async def admin_delete_thread(request: Request, thread_id: int, user: dict = Depends(require_admin)):
    thread = await boards.get_thread(thread_id)
    board_id = thread["board_id"] if thread else None
    await boards.delete_thread(thread_id)
    if board_id:
        return RedirectResponse(f"/boards/{board_id}", status_code=302)
    return RedirectResponse("/boards", status_code=302)


@router.post("/admin/file/{file_id}/delete")
async def admin_delete_file(request: Request, file_id: int, user: dict = Depends(require_admin)):
    await file_mod.delete_file(file_id)
    return RedirectResponse("/files", status_code=302)


@router.post("/admin/chat/{message_id}/delete")
async def admin_delete_chat(request: Request, message_id: int, user: dict = Depends(require_admin)):
    await delete_message(message_id)
    return RedirectResponse("/chat", status_code=302)

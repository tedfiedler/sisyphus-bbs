"""Administration routes for user, content, and chat management.

All endpoints require admin-level access (access_level >= 1). Promotion
and demotion of users require superadmin access (access_level == 2).
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth, config, invites
from lib import boards
from lib import files as file_mod
from lib.chat import delete_message
from lib.db import get_db
from lib.deps import require_admin
from lib.proxy import is_https
from lib.templating import templates, _add_globals

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: dict = Depends(require_admin)):
    """Render the admin dashboard: the user list and the invitations."""
    users = await auth.list_users()
    # The link a new member is handed. Built from what the visitor sees, so
    # it is right behind a proxy as well as on a bare server.
    scheme = "https" if is_https(request) else "http"
    invite_base = f"{scheme}://{request.headers.get('host', request.url.netloc)}/?invite="
    return templates.TemplateResponse(
        "admin.html",
        _add_globals(request, {
            "user": user, "users": users,
            "invites": await invites.list_all(),
            "invite_base": invite_base,
            "invite_only": config.INVITE_ONLY,
            "invite_days": invites.INVITE_DAYS,
        }),
    )


@router.post("/admin/invites")
async def admin_invite_create(
    request: Request,
    note: str = Form("", max_length=invites.NOTE_MAX),
    user: dict = Depends(require_admin),
):
    """Make one invitation code. The note is a reminder of who it is for."""
    await invites.create(user["id"], note)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/invites/{invite_id}/revoke")
async def admin_invite_revoke(request: Request, invite_id: int, user: dict = Depends(require_admin)):
    """Withdraw an invitation that has not been used."""
    await invites.revoke(invite_id)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/promote")
async def admin_promote(request: Request, user_id: int, user: dict = Depends(require_admin)):
    """Promote a user to admin (access_level 1). Superadmin only."""
    if not auth.is_superadmin(user):
        return HTMLResponse("Forbidden", status_code=403)
    target = await auth.get_user(user_id)
    # Only ever raises a regular user: "promoting" a superadmin would
    # silently strip them down to admin.
    if target and target["access_level"] == 0:
        await auth.set_access_level(user_id, 1)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/demote")
async def admin_demote(request: Request, user_id: int, user: dict = Depends(require_admin)):
    """Demote a user to regular access (access_level 0). Superadmin only."""
    if not auth.is_superadmin(user):
        return HTMLResponse("Forbidden", status_code=403)
    target = await auth.get_user(user_id)
    # Superadmins are out of reach, including the caller: demoting the last
    # one would leave nobody able to manage admins at all.
    if target and target["access_level"] == 1:
        await auth.set_access_level(user_id, 0)
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def admin_delete_user(request: Request, user_id: int, user: dict = Depends(require_admin)):
    """Delete a regular user account. Admins cannot delete other admins."""
    target = await auth.get_user(user_id)
    if target and target["access_level"] == 0:
        await auth.delete_user(user_id, reassign_channels_to=user["id"])
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/post/{post_id}/delete")
async def admin_delete_post(request: Request, post_id: int, user: dict = Depends(require_admin)):
    """Delete a single forum post and redirect back to its thread."""
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
    """Delete a thread and all its posts, then redirect to the parent board."""
    thread = await boards.get_thread(thread_id)
    board_id = thread["board_id"] if thread else None
    await boards.delete_thread(thread_id)
    if board_id:
        return RedirectResponse(f"/boards/{board_id}", status_code=302)
    return RedirectResponse("/boards", status_code=302)


@router.post("/admin/file/{file_id}/delete")
async def admin_delete_file(request: Request, file_id: int, user: dict = Depends(require_admin)):
    """Delete an uploaded file from disk and the database."""
    await file_mod.delete_file(file_id)
    return RedirectResponse("/files", status_code=302)


@router.post("/admin/users/{user_id}/toggle-file-access")
async def admin_toggle_file_access(request: Request, user_id: int, user: dict = Depends(require_admin)):
    """Toggle the file_upload_allowed flag for a regular user."""
    target = await auth.get_user(user_id)
    if target and target["access_level"] == 0:
        new_val = 0 if target.get("file_upload_allowed") else 1
        db = await get_db()
        await db.execute("UPDATE users SET file_upload_allowed = ? WHERE id = ?", (new_val, user_id))
        await db.commit()
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/chat/{message_id}/delete")
async def admin_delete_chat(request: Request, message_id: int, user: dict = Depends(require_admin)):
    """Delete a single chat message by ID."""
    await delete_message(message_id)
    return RedirectResponse("/chat", status_code=302)

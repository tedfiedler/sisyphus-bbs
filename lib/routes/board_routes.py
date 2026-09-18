"""Forum board and thread routes.

Handles listing boards, viewing individual boards and threads,
creating new threads, and posting replies.
"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth, boards
from lib.content_filter import contains_url
from lib.db import get_db
from lib.deps import require_user, require_admin
from lib.models import BoardCreate, PostCreate, ThreadCreate, validate
from lib.templating import templates, _add_globals

router = APIRouter()


@router.get("/boards", response_class=HTMLResponse)
async def board_list(request: Request, user: dict = Depends(require_user)):
    """List all boards with thread and post counts."""
    board_data = await boards.list_boards()
    return templates.TemplateResponse("boards.html", _add_globals(request, {"user": user, "boards": board_data}))


@router.post("/boards/create")
async def board_create(request: Request, name: str = Form(), description: str = Form(""), user: dict = Depends(require_admin)):
    """Create a new board and redirect to the board listing."""
    form, error = validate(BoardCreate, name=name, description=description)
    if error:
        return RedirectResponse("/boards", status_code=302)
    await boards.create_board(form.name, form.description)
    return RedirectResponse("/boards", status_code=302)


@router.get("/boards/{board_id}", response_class=HTMLResponse)
async def board_view(request: Request, board_id: int, user: dict = Depends(require_user)):
    """Display a board's thread listing. Redirect to /boards if not found."""
    board = await boards.get_board(board_id)
    if not board:
        return RedirectResponse("/boards", status_code=302)
    thread_list = await boards.list_threads(board_id)
    return templates.TemplateResponse(
        "thread.html", _add_globals(request, {"user": user, "board": board, "threads": thread_list, "posts": None, "thread": None})
    )


@router.post("/boards/{board_id}/thread")
async def thread_create(request: Request, board_id: int, subject: str = Form(), body: str = Form(), user: dict = Depends(require_user)):
    """Create a new thread with an initial post and redirect to it."""
    form, error = validate(ThreadCreate, subject=subject, body=body)
    if not error and not auth.is_admin(user) and (contains_url(subject) or contains_url(body)):
        error = "URLs are not allowed in posts."
    if error:
        board = await boards.get_board(board_id)
        thread_list = await boards.list_threads(board_id)
        return templates.TemplateResponse(
            "thread.html",
            _add_globals(request, {
                "user": user, "board": board, "threads": thread_list,
                "posts": None, "thread": None,
                "error": error,
            }),
            status_code=400,
        )
    thread_id = await boards.create_thread(board_id, form.subject, user["id"], form.body)
    return RedirectResponse(f"/thread/{thread_id}", status_code=302)


@router.get("/thread/{thread_id}", response_class=HTMLResponse)
async def thread_view(request: Request, thread_id: int, user: dict = Depends(require_user)):
    """Display a thread and all its posts. Redirect to /boards if not found."""
    thread = await boards.get_thread(thread_id)
    if not thread:
        return RedirectResponse("/boards", status_code=302)
    board = await boards.get_board(thread["board_id"])
    post_list = await boards.list_posts(thread_id, user["id"])
    return templates.TemplateResponse(
        "thread.html", _add_globals(request, {"user": user, "board": board, "thread": thread, "posts": post_list, "threads": None})
    )


@router.post("/post/{post_id}/like")
async def post_like(request: Request, post_id: int, user: dict = Depends(require_user)):
    """Toggle a like on a post and redirect back to the thread."""
    db = await get_db()
    cursor = await db.execute("SELECT thread_id FROM posts WHERE id = ?", (post_id,))
    row = await cursor.fetchone()
    if not row:
        return RedirectResponse("/boards", status_code=302)
    await boards.toggle_like(post_id, user["id"])
    return RedirectResponse(f"/thread/{row[0]}", status_code=302)


@router.post("/thread/{thread_id}/reply")
async def thread_reply(request: Request, thread_id: int, body: str = Form(), user: dict = Depends(require_user)):
    """Add a reply post to an existing thread."""
    thread = await boards.get_thread(thread_id)
    if not thread:
        return RedirectResponse("/boards", status_code=302)
    form, error = validate(PostCreate, body=body)
    if not error and not auth.is_admin(user) and contains_url(body):
        error = "URLs are not allowed in posts."
    if error:
        board = await boards.get_board(thread["board_id"])
        post_list = await boards.list_posts(thread_id, user["id"])
        return templates.TemplateResponse(
            "thread.html",
            _add_globals(request, {
                "user": user, "board": board, "thread": thread,
                "posts": post_list, "threads": None,
                "error": error,
            }),
            status_code=400,
        )
    await boards.create_post(thread_id, user["id"], form.body)
    return RedirectResponse(f"/thread/{thread_id}", status_code=302)

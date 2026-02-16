from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import boards
from lib.deps import require_user
from lib.web_server import templates, _add_globals

router = APIRouter()


@router.get("/boards", response_class=HTMLResponse)
async def board_list(request: Request, user: dict = Depends(require_user)):
    board_data = await boards.list_boards()
    return templates.TemplateResponse("boards.html", _add_globals(request, {"user": user, "boards": board_data}))


@router.post("/boards/create")
async def board_create(request: Request, name: str = Form(), description: str = Form(""), user: dict = Depends(require_user)):
    await boards.create_board(name, description)
    return RedirectResponse("/boards", status_code=302)


@router.get("/boards/{board_id}", response_class=HTMLResponse)
async def board_view(request: Request, board_id: int, user: dict = Depends(require_user)):
    board = await boards.get_board(board_id)
    if not board:
        return RedirectResponse("/boards", status_code=302)
    thread_list = await boards.list_threads(board_id)
    return templates.TemplateResponse(
        "thread.html", _add_globals(request, {"user": user, "board": board, "threads": thread_list, "posts": None, "thread": None})
    )


@router.post("/boards/{board_id}/thread")
async def thread_create(request: Request, board_id: int, subject: str = Form(), body: str = Form(), user: dict = Depends(require_user)):
    thread_id = await boards.create_thread(board_id, subject, user["id"], body)
    return RedirectResponse(f"/thread/{thread_id}", status_code=302)


@router.get("/thread/{thread_id}", response_class=HTMLResponse)
async def thread_view(request: Request, thread_id: int, user: dict = Depends(require_user)):
    thread = await boards.get_thread(thread_id)
    if not thread:
        return RedirectResponse("/boards", status_code=302)
    board = await boards.get_board(thread["board_id"])
    post_list = await boards.list_posts(thread_id)
    return templates.TemplateResponse(
        "thread.html", _add_globals(request, {"user": user, "board": board, "thread": thread, "posts": post_list, "threads": None})
    )


@router.post("/thread/{thread_id}/reply")
async def thread_reply(request: Request, thread_id: int, body: str = Form(), user: dict = Depends(require_user)):
    await boards.create_post(thread_id, user["id"], body)
    return RedirectResponse(f"/thread/{thread_id}", status_code=302)

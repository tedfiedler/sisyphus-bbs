import asyncio
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse

from lib import auth
from lib.chat import chat_manager
from lib.deps import require_user
from lib.web_server import templates, _add_globals

router = APIRouter()


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, user: dict = Depends(require_user)):
    recent = await chat_manager.recent_messages()
    return templates.TemplateResponse(
        "chat.html", _add_globals(request, {"user": user, "recent_messages": recent})
    )


@router.websocket("/ws/chat")
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

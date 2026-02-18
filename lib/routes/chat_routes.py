"""Chat routes: real-time messaging, channels, DMs, and admin announcements.

Provides a WebSocket endpoint that supports channel switching via a mutable
``state`` dict and a sentinel-based queue swap pattern. HTTP endpoints handle
channel CRUD, DM initiation, and admin broadcast announcements.
"""

import asyncio
import json
import re

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth, chat
from lib.chat import chat_manager
from lib.content_filter import contains_url
from lib.deps import require_user, require_admin
from lib.web_server import templates, _add_globals

router = APIRouter()

_CHANNEL_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, channel: str = "lobby", user: dict = Depends(require_user)):
    """Render the chat page with sidebar data for the given channel."""
    if chat.is_dm_channel(channel):
        await chat.mark_dm_channel_seen(user["id"], channel)
    channels = await chat.list_channels()
    online_users = await auth.list_online_users()
    dm_channels = await chat.list_dm_channels_for_user(user["id"])
    unread_dm_channels = await chat.get_unread_dm_channels(user["id"])
    recent = await chat_manager.recent_messages(channel)
    return templates.TemplateResponse(
        "chat.html",
        _add_globals(request, {
            "user": user,
            "recent_messages": recent,
            "channels": channels,
            "online_users": online_users,
            "dm_channels": dm_channels,
            "unread_dm_channels": unread_dm_channels,
            "current_channel": channel,
        }),
    )


@router.post("/chat/channels/create")
async def create_channel(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(require_admin),
):
    """Create a named chat channel. Admin only.

    Channel names must be lowercase alphanumeric (plus hyphens and
    underscores), and ``lobby`` is reserved.
    """
    name = name.strip().lower()
    if not name or not _CHANNEL_NAME_RE.match(name):
        return RedirectResponse("/chat?error=invalid_name", status_code=303)
    if name == "lobby":
        return RedirectResponse("/chat?error=reserved_name", status_code=303)
    existing = await chat.get_channel(name)
    if existing:
        return RedirectResponse("/chat?error=channel_exists", status_code=303)
    await chat.create_channel(name, description, user["id"])
    return RedirectResponse(f"/chat?channel={name}", status_code=303)


@router.post("/chat/channels/{name}/delete")
async def delete_channel(name: str, user: dict = Depends(require_admin)):
    """Delete a named channel and all its messages. Admin only. Lobby is protected."""
    if name == "lobby":
        return RedirectResponse("/chat?error=cannot_delete_lobby", status_code=303)
    await chat.delete_channel(name)
    return RedirectResponse("/chat", status_code=303)


@router.post("/chat/announce")
async def announce(
    request: Request,
    message: str = Form(...),
    user: dict = Depends(require_admin),
):
    """Broadcast an announcement to all connected WebSocket clients. Admin only."""
    message = message.strip()
    if message:
        await chat_manager.broadcast_all(user["username"], message)
    return RedirectResponse("/chat", status_code=303)


@router.post("/chat/dm/{target_user_id}")
async def start_dm(target_user_id: int, user: dict = Depends(require_user)):
    """Initiate or navigate to a DM conversation with another user."""
    if target_user_id == user["id"]:
        return RedirectResponse("/chat", status_code=303)
    target = await auth.get_user(target_user_id)
    if not target:
        return RedirectResponse("/chat", status_code=303)
    channel = chat.dm_channel_name(user["id"], target_user_id)
    return RedirectResponse(f"/chat?channel={channel}", status_code=303)


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat.

    Supports three incoming message types:
    - ``{"type": "pong"}`` — keepalive response (ignored).
    - ``{"type": "switch", "channel": "..."}`` — switch to a different
      channel. The old queue receives a ``None`` sentinel so the send
      task wakes up and re-reads from the new queue.
    - ``{"message": "..."}`` — broadcast a chat message to the current
      channel.

    Outgoing message types:
    - ``{"type": "history", "messages": [...]}`` — channel history on
      connect or switch.
    - ``{"type": "ping"}`` — periodic keepalive.
    - ``{"type": "error", "message": "..."}`` — channel validation error.
    - ``{"type": "announcement", ...}`` — admin broadcast.
    - Regular chat message dicts.
    """
    await websocket.accept()
    token = websocket.cookies.get("session_token")
    user = await auth.get_user_by_token(token) if token else None
    if not user:
        await websocket.close(code=4001)
        return

    state = {
        "channel": "lobby",
        "queue": chat_manager.subscribe("lobby"),
    }

    try:
        # Send recent history for initial channel
        recent = await chat_manager.recent_messages("lobby")
        await websocket.send_json({"type": "history", "messages": recent})

        async def _recv():
            """Read incoming WebSocket messages and dispatch by type."""
            while True:
                data = await websocket.receive_text()
                parsed = json.loads(data)
                if parsed.get("type") == "pong":
                    continue
                if parsed.get("type") == "switch":
                    new_channel = parsed.get("channel", "lobby")
                    err = await chat.validate_channel(new_channel, user["id"])
                    if err:
                        await websocket.send_json({"type": "error", "message": err})
                        continue
                    if chat.is_dm_channel(new_channel):
                        await chat.mark_dm_channel_seen(user["id"], new_channel)
                    old_channel = state["channel"]
                    old_queue = state["queue"]
                    new_queue = chat_manager.subscribe(new_channel)
                    state["channel"] = new_channel
                    state["queue"] = new_queue
                    chat_manager.unsubscribe(old_channel, old_queue)
                    # Wake _send so it re-reads state["queue"]
                    await old_queue.put(None)
                    # Send history for the new channel
                    history = await chat_manager.recent_messages(new_channel)
                    await websocket.send_json({"type": "history", "messages": history})
                    continue
                msg_text = parsed.get("message", "")
                if not auth.is_admin(user) and contains_url(msg_text):
                    await websocket.send_json({"type": "error", "message": "URLs are not allowed in chat messages."})
                    continue
                await chat_manager.broadcast(
                    state["channel"], user["username"], msg_text
                )

        async def _send():
            """Forward queued messages to the WebSocket client."""
            while True:
                msg = await state["queue"].get()
                if msg is None:
                    # Sentinel: queue was swapped, re-loop to read from new queue
                    continue
                await websocket.send_json(msg)

        async def _ping():
            """Send periodic keepalive pings to detect stale connections."""
            while True:
                await asyncio.sleep(20)
                await websocket.send_json({"type": "ping"})

        await asyncio.gather(_recv(), _send(), _ping())
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        chat_manager.unsubscribe(state["channel"], state["queue"])

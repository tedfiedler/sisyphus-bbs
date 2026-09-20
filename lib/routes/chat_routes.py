"""Chat routes: real-time messaging, channels, DMs, and admin announcements.

Provides a WebSocket endpoint that supports channel switching via a mutable
``state`` dict and a sentinel-based queue swap pattern. HTTP endpoints handle
channel CRUD, DM initiation, and admin broadcast announcements.
"""

import asyncio
import json
import logging
import re

from urllib.parse import urlsplit

import anyio

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import auth, chat, config
from lib.chat import chat_manager
from lib.content_filter import contains_url
from lib.deps import require_user, require_admin
from lib.models import ChatMessage, validate
from lib.ratelimit import RateLimiter
from lib.templating import templates, _add_globals

logger = logging.getLogger(__name__)

router = APIRouter()

_CHANNEL_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
_MAX_CHANNEL_DESCRIPTION = 256

# Seconds between keepalive pings; the session is re-checked on the same beat.
_PING_INTERVAL = 20

# A 2,000-character message can grow sixfold when JSON-escaped; anything
# beyond this is not a chat frame and is refused before it is parsed.
_MAX_FRAME_CHARS = 16_384

# Frames per user across all their sockets. Loose enough for fast typing and
# channel hopping, tight enough that one account cannot flood a channel or
# hammer the database through the socket.
_ws_limiter = RateLimiter(max_events=20, window_seconds=10)


def _origin_allowed(websocket: WebSocket) -> bool:
    """Return True if the handshake came from one of our own pages.

    WebSocket handshakes are not covered by CORS or by the CSRF token, and
    the session cookie rides along on them, so any page the user visits
    could otherwise open this socket as them and read their DMs. Browsers
    always send ``Origin`` on a WebSocket handshake and scripts cannot forge
    it; a missing header means a non-browser client, which carries no
    ambient cookies to abuse.
    """
    origin = websocket.headers.get("origin")
    if origin is None:
        return True
    origin = origin.strip().rstrip("/").lower()
    if origin in config.ALLOWED_ORIGINS:
        return True
    host = websocket.headers.get("host", "").strip().lower()
    return bool(host) and urlsplit(origin).netloc == host


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, channel: str = "lobby", user: dict = Depends(require_user)):
    """Render the chat page with sidebar data for the given channel.

    The requested channel is authorized before any of its history is read,
    matching the check the WebSocket endpoint performs on switch.
    """
    if await chat.validate_channel(channel, user["id"]):
        return RedirectResponse("/chat", status_code=303)
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
    description = description.strip()[:_MAX_CHANNEL_DESCRIPTION]
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
    msg, error = validate(ChatMessage, message=message.strip())
    if error:
        return RedirectResponse("/chat?error=invalid_message", status_code=303)
    await chat_manager.broadcast_all(user["username"], msg.message)
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
    if not _origin_allowed(websocket):
        # Closing before accept() refuses the handshake with a 403.
        await websocket.close(code=1008)
        return
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
                if len(data) > _MAX_FRAME_CHARS:
                    await websocket.send_json({"type": "error", "message": "Message too large."})
                    continue
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Malformed message."})
                    continue
                if not isinstance(parsed, dict):
                    await websocket.send_json({"type": "error", "message": "Malformed message."})
                    continue
                if parsed.get("type") == "pong":
                    continue
                limiter_key = str(user["id"])
                if _ws_limiter.is_limited(limiter_key):
                    await websocket.send_json({"type": "error", "message": "Slow down — too many messages."})
                    continue
                _ws_limiter.record(limiter_key)
                if parsed.get("type") == "switch":
                    new_channel = parsed.get("channel", "lobby")
                    if not isinstance(new_channel, str):
                        await websocket.send_json({"type": "error", "message": "Malformed message."})
                        continue
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
                    # Wake _send so it re-reads state["queue"]. If the old
                    # queue is full _send is not parked on it, so there is
                    # nothing to wake and the dropped sentinel is harmless.
                    chat_manager.offer(old_queue, None)
                    # Send history for the new channel
                    history = await chat_manager.recent_messages(new_channel)
                    await websocket.send_json({"type": "history", "messages": history})
                    continue
                msg, err = validate(
                    ChatMessage, channel=state["channel"], message=parsed.get("message", "")
                )
                if err:
                    await websocket.send_json({"type": "error", "message": err})
                    continue
                if not auth.is_admin(user) and contains_url(msg.message):
                    await websocket.send_json({"type": "error", "message": "URLs are not allowed in chat messages."})
                    continue
                await chat_manager.broadcast(
                    state["channel"], user["username"], msg.message
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
            """Send periodic keepalive pings and re-check the session.

            The cookie is only presented at the handshake, so without this a
            socket opened before a logout, session expiry, or account
            deletion would go on reading and posting indefinitely. The
            refresh also picks up a change of access level.
            """
            while True:
                await asyncio.sleep(_PING_INTERVAL)
                current = await auth.get_user_by_token(token)
                if current is None:
                    await websocket.close(code=4001)
                    return
                user.update(current)
                await websocket.send_json({"type": "ping"})

        # Run the three loops under one cancel scope. asyncio.gather would
        # leave the siblings running when one raises, stranding _send on a
        # queue nothing will ever feed again; when any loop ends here, the
        # scope cancels the rest. anyio is what Starlette itself runs under,
        # so cancellation unwinds cleanly through the ASGI server.
        async with anyio.create_task_group() as task_group:

            async def _run(loop):
                """Run one loop, then bring the whole connection down with it."""
                try:
                    await loop()
                except WebSocketDisconnect:
                    pass
                except Exception:
                    logger.exception("chat websocket failed for user %s", user["id"])
                finally:
                    task_group.cancel_scope.cancel()

            task_group.start_soon(_run, _recv)
            task_group.start_soon(_run, _send)
            task_group.start_soon(_run, _ping)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("chat websocket failed for user %s", user["id"])
    finally:
        chat_manager.unsubscribe(state["channel"], state["queue"])

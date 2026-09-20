"""Cap request body size before anything downstream reads it.

Without a cap, any client — logged in or not — can make the server hold an
arbitrarily large body in memory: :class:`lib.csrf.CSRFMiddleware` buffers
the whole body to find its token, and Starlette reads url-encoded forms in
full. The limit is enforced here, outermost, so an oversized request is
refused before either happens.
"""

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse

# Multipart framing and the other form fields ride along with the file.
_UPLOAD_OVERHEAD = 64 * 1024

# Generous for the largest ordinary form (a 20,000-character post, which can
# triple in size once percent-encoded) while still being small.
DEFAULT_MAX_BODY = 1024 * 1024

# An oversized body is read and thrown away up to this multiple of the limit
# before the 413 goes out. Answering while the client is still sending makes
# it see a connection reset instead of the response, which is a poor way to
# tell someone their file was a little too big. Discarding costs no memory;
# past this point the sender is not worth being polite to.
_DRAIN_FACTOR = 4


class _BodyTooLarge(Exception):
    """Raised from the wrapped ``receive`` once a body outgrows its limit."""


class BodySizeLimitMiddleware:
    """Reject HTTP requests whose body exceeds the limit for their path.

    ``Content-Length`` is checked up front so an honest oversized request is
    refused without reading a byte. Chunked bodies carry no length, so the
    bytes are also counted as they stream in.
    """

    def __init__(self, app, default_limit: int = DEFAULT_MAX_BODY, path_limits: dict[str, int] | None = None):
        self.app = app
        self.default_limit = default_limit
        self.path_limits = path_limits or {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.path_limits.get(scope["path"], self.default_limit)
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                too_large = int(declared) > limit
            except ValueError:
                too_large = True
            if too_large:
                await self._reject(scope, receive, send, drain=limit * _DRAIN_FACTOR)
                return

        received = 0
        response_started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(scope, receive, send, drain=limit * _DRAIN_FACTOR - received)

    @staticmethod
    async def _reject(scope, receive, send, drain: int):
        """Send a 413, first discarding up to *drain* bytes of unread body."""
        while drain > 0:
            message = await receive()
            if message["type"] != "http.request":
                break
            drain -= len(message.get("body", b""))
            if not message.get("more_body", False):
                break
        response = PlainTextResponse(
            "Request body too large", status_code=413, headers={"Connection": "close"}
        )
        await response(scope, receive, send)


def upload_limit(max_upload_bytes: int) -> int:
    """Return the body limit for an endpoint accepting a file of the given size."""
    return max_upload_bytes + _UPLOAD_OVERHEAD

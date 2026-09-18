"""In-memory sliding-window rate limiting.

State lives in the process, so limits are per worker rather than global. That
is adequate for a single-process BBS; running several workers would need a
shared store.

Client identity comes from :func:`client_key`, which uses the socket peer
unless ``SISYPHUS_TRUST_PROXY`` is set. Behind a reverse proxy every request
shares one peer address, which would otherwise put all clients in one bucket.
"""

import time

from fastapi import Request

from lib import config


class RateLimiter:
    """Count events per key within a sliding window, with bounded memory.

    ``defaultdict`` made the previous implementation grow on read: merely
    asking whether a key was limited created an entry for it. Here only
    :meth:`record` inserts, and each insert prunes expired keys, so memory
    tracks the number of *recently active* clients rather than every client
    ever seen.
    """

    def __init__(self, max_events: int, window_seconds: float, max_keys: int = 10_000):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: dict[str, list[float]] = {}

    def _fresh(self, key: str, now: float) -> list[float]:
        """Return the key's timestamps that still fall inside the window."""
        return [t for t in self._events.get(key, ()) if now - t < self.window_seconds]

    def is_limited(self, key: str) -> bool:
        """Return True if *key* has used up its budget. Does not record anything."""
        return len(self._fresh(key, time.monotonic())) >= self.max_events

    def record(self, key: str) -> None:
        """Record one event against *key*.

        Pruning runs after the insert so ``len(self) <= max_keys`` holds on
        return; the just-recorded key is the newest, so it is never the one
        evicted.
        """
        now = time.monotonic()
        self._events[key] = self._fresh(key, now) + [now]
        self._prune(now)

    def clear(self, key: str) -> None:
        """Forget a key's history, e.g. after a successful login."""
        self._events.pop(key, None)

    def _prune(self, now: float) -> None:
        """Drop keys with no events left in the window."""
        expired = [
            key for key, stamps in self._events.items()
            if not any(now - t < self.window_seconds for t in stamps)
        ]
        for key in expired:
            del self._events[key]

        # Hard ceiling in case a flood outpaces expiry: drop the keys whose
        # most recent event is oldest, which are the closest to expiring.
        overflow = len(self._events) - self.max_keys
        if overflow > 0:
            by_age = sorted(self._events, key=lambda k: max(self._events[k]))
            for key in by_age[:overflow]:
                del self._events[key]

    def __len__(self) -> int:
        """Return the number of keys currently tracked."""
        return len(self._events)


def client_key(request: Request) -> str:
    """Return the rate-limiting key for a request.

    ``X-Forwarded-For`` is only consulted when ``SISYPHUS_TRUST_PROXY`` is
    set, since a client can otherwise send the header itself and sidestep
    the limit by varying it.
    """
    if config.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Right-most entry is the hop our trusted proxy observed.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"

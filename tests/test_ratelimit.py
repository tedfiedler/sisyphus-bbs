"""Rate limiting behaviour and its memory bounds."""

import pytest

from lib import config, ratelimit
from lib.ratelimit import RateLimiter, client_key
from tests.helpers import anon_client


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(ratelimit.time, "monotonic", fake)
    return fake


def test_checking_a_key_does_not_track_it(clock):
    """The defaultdict version grew on read, so probing leaked memory."""
    limiter = RateLimiter(max_events=3, window_seconds=60)
    for i in range(1000):
        limiter.is_limited(f"10.0.0.{i}")
    assert len(limiter) == 0


def test_limit_trips_after_the_budget(clock):
    limiter = RateLimiter(max_events=3, window_seconds=60)
    for _ in range(3):
        assert not limiter.is_limited("ip")
        limiter.record("ip")
    assert limiter.is_limited("ip")


def test_window_expiry_releases_the_limit(clock):
    limiter = RateLimiter(max_events=2, window_seconds=60)
    limiter.record("ip")
    limiter.record("ip")
    assert limiter.is_limited("ip")

    clock.advance(61)
    assert not limiter.is_limited("ip")


def test_expired_keys_are_dropped(clock):
    limiter = RateLimiter(max_events=5, window_seconds=60)
    for i in range(50):
        limiter.record(f"10.0.0.{i}")
    assert len(limiter) == 50

    clock.advance(61)
    limiter.record("fresh")
    assert len(limiter) == 1


def test_key_count_is_capped_even_under_a_flood(clock):
    limiter = RateLimiter(max_events=5, window_seconds=3600, max_keys=100)
    for i in range(500):
        limiter.record(f"10.0.0.{i}")
        clock.advance(0.01)
    assert len(limiter) <= 100


def test_clear_forgets_a_key(clock):
    limiter = RateLimiter(max_events=1, window_seconds=60)
    limiter.record("ip")
    assert limiter.is_limited("ip")
    limiter.clear("ip")
    assert not limiter.is_limited("ip")


# --- client identification ---------------------------------------------------

class _Req:
    def __init__(self, peer, headers=None):
        self.client = type("C", (), {"host": peer})() if peer else None
        self.headers = headers or {}


def test_forwarded_header_ignored_unless_proxy_trusted(monkeypatch):
    """A client can set X-Forwarded-For itself to get a fresh bucket."""
    monkeypatch.setattr(config, "TRUST_PROXY", False)
    req = _Req("10.0.0.1", {"x-forwarded-for": "1.2.3.4"})
    assert client_key(req) == "10.0.0.1"


def test_forwarded_header_used_when_proxy_trusted(monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    req = _Req("10.0.0.1", {"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert client_key(req) == "5.6.7.8"


def test_missing_client_falls_back(monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY", False)
    assert client_key(_Req(None)) == "unknown"


# --- routes ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_locks_out_after_repeated_failures():
    from lib import auth
    await auth.register_user("alice", "password123")

    async with anon_client() as client:
        for _ in range(5):
            resp = await client.post(
                "/login", data={"username": "alice", "password": "wrong"},
                follow_redirects=False,
            )
            assert resp.status_code == 401

        resp = await client.post(
            "/login", data={"username": "alice", "password": "wrong"},
            follow_redirects=False,
        )
        assert resp.status_code == 429

        # Even the correct password is refused while the lockout holds.
        resp = await client.post(
            "/login", data={"username": "alice", "password": "password123"},
            follow_redirects=False,
        )
        assert resp.status_code == 429


@pytest.mark.asyncio
async def test_successful_login_clears_the_counter():
    from lib import auth
    await auth.register_user("alice", "password123")

    async with anon_client() as client:
        for _ in range(4):
            await client.post(
                "/login", data={"username": "alice", "password": "wrong"},
                follow_redirects=False,
            )
        ok = await client.post(
            "/login", data={"username": "alice", "password": "password123"},
            follow_redirects=False,
        )
        assert ok.status_code == 302

        # Budget is back: a fresh failure is a 401, not a 429.
        again = await client.post(
            "/login", data={"username": "alice", "password": "wrong"},
            follow_redirects=False,
        )
        assert again.status_code == 401


@pytest.mark.asyncio
async def test_registration_is_rate_limited():
    """Registration previously had no limit at all."""
    async with anon_client() as client:
        for i in range(10):
            resp = await client.post(
                "/register",
                data={"username": f"user{i}", "password": "password123"},
                follow_redirects=False,
            )
            assert resp.status_code == 302, f"signup {i} -> {resp.status_code}"

        resp = await client.post(
            "/register",
            data={"username": "toomany", "password": "password123"},
            follow_redirects=False,
        )
    assert resp.status_code == 429
    from lib import auth
    assert await auth.authenticate("toomany", "password123") is None


@pytest.mark.asyncio
async def test_limiters_are_independent():
    """Exhausting logins must not block signups."""
    from lib import auth
    await auth.register_user("alice", "password123")

    async with anon_client() as client:
        for _ in range(6):
            await client.post(
                "/login", data={"username": "alice", "password": "wrong"},
                follow_redirects=False,
            )
        resp = await client.post(
            "/register",
            data={"username": "newcomer", "password": "password123"},
            follow_redirects=False,
        )
    assert resp.status_code == 302

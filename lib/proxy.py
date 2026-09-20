"""Helpers for seeing the real request when running behind a reverse proxy."""

from starlette.requests import HTTPConnection

from lib import config


def is_https(conn: HTTPConnection) -> bool:
    """Return True if the client reached us over TLS.

    Behind a TLS-terminating proxy the hop to this process is plain HTTP, so
    the scheme alone would say "http" and session cookies would go out
    without ``Secure``. ``X-Forwarded-Proto`` is only believed when
    ``SISYPHUS_TRUST_PROXY`` is set, for the same reason as
    :func:`lib.ratelimit.client_key`: otherwise the client controls it.
    """
    if conn.url.scheme in ("https", "wss"):
        return True
    if config.TRUST_PROXY:
        forwarded = conn.headers.get("x-forwarded-proto", "")
        return forwarded.split(",")[-1].strip().lower() == "https"
    return False

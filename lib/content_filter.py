"""Content filtering utilities for user-submitted text."""

import re

_URL_RE = re.compile(r'https?://|ftp://|//|data:|www\.', re.IGNORECASE)


def contains_url(text: str) -> bool:
    """Return True if *text* contains a URL pattern."""
    return bool(_URL_RE.search(text))

"""Content filtering utilities for user-submitted text."""

import re

# What counts as a link, for the no-links rule applied to regular users.
# Each alternative needs something URL-shaped after it: a bare "//" is a
# code comment far more often than a protocol-relative link, and "data:"
# ends plenty of ordinary sentences ("see the data: ...").
_URL_RE = re.compile(
    r"""
      (?:https?|ftp)://                              # explicit scheme
    | (?<![\w:/]) // [a-z0-9-]+ (?:\.[a-z0-9-]+)* \.[a-z]{2,}   # //host.tld
    | \bdata: [a-z]+ / [a-z0-9.+-]+ [;,]             # data:text/html;... or ,
    | \bwww\. [a-z0-9-]                              # www.something
    """,
    re.IGNORECASE | re.VERBOSE,
)


def contains_url(text: str) -> bool:
    """Return True if *text* contains a URL pattern."""
    return bool(_URL_RE.search(text))

"""The no-links rule should catch links, and only links."""

import pytest

from lib.content_filter import contains_url


@pytest.mark.parametrize("text", [
    "see http://example.com",
    "see HTTPS://EXAMPLE.COM/path?q=1",
    "ftp://files.example.org/pub",
    "visit www.example.com today",
    "protocol-relative //evil.example/x.js",
    "(//cdn.example.co.uk/lib)",
    '<a href="//evil.example">',
    "data:text/html;base64,PHNjcmlwdD4=",
    "data:image/svg+xml,<svg/>",
])
def test_links_are_detected(text):
    assert contains_url(text)


@pytest.mark.parametrize("text", [
    "// TODO: fix this later",
    "int x = 1; // set x",
    "//comment with no space",
    "a //= 2  # floor-divide in place",
    "and/or//either",
    "path is /usr//local/bin",
    "====//====",
    "I looked at the data: it was fine",
    "metadata: none",
    "the www is big",
    "awww. that is sweet",
    "ratio was 3:1 // roughly",
])
def test_ordinary_text_is_not_a_link(text):
    assert not contains_url(text)

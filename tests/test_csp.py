"""The Content-Security-Policy forbids inline script and style.

That is only safe to ship while the templates contain neither: one stray
``onclick=`` or ``style=`` would silently stop working in the browser rather
than fail anywhere a test could see. These tests fail instead.
"""

import re

import pytest

from lib import auth, boards, chat, config
from lib import files as file_mod
from lib.chat import chat_manager
from tests.helpers import anon_client, client_for

# Things the policy blocks. Each is checked in template source, in the
# static scripts that build HTML, and in fully rendered pages.
_BLOCKED = {
    "style attribute": re.compile(r"<[^<>]*\sstyle\s*=", re.IGNORECASE),
    "style element": re.compile(r"<style[\s>]", re.IGNORECASE),
    "inline event handler": re.compile(r"<[^<>]*\son[a-z]+\s*=", re.IGNORECASE),
    "inline script": re.compile(r"<script(?![^>]*\ssrc=)[^>]*>", re.IGNORECASE),
    "javascript: URL": re.compile(r"""(href|src|action)\s*=\s*["']?\s*javascript:""", re.IGNORECASE),
}


def _violations(text: str) -> list[str]:
    return [
        f"{label}: {match.group(0)[:100]}"
        for label, pattern in _BLOCKED.items()
        for match in pattern.finditer(text)
    ]


@pytest.mark.asyncio
async def test_policy_has_no_unsafe_sources():
    async with anon_client() as client:
        resp = await client.get("/")
    csp = resp.headers["content-security-policy"]
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";"))
    assert directives["script-src"] == "'self'"
    assert directives["style-src"] == "'self'"


@pytest.mark.parametrize(
    "template", sorted(config.TEMPLATES_DIR.glob("*.html")), ids=lambda p: p.name
)
def test_template_source_has_nothing_inline(template):
    assert _violations(template.read_text()) == []


@pytest.mark.parametrize(
    "script", sorted((config.STATIC_DIR / "js").glob("*.js")), ids=lambda p: p.name
)
def test_static_scripts_do_not_build_inline_style_or_code(script):
    source = script.read_text()
    assert _violations(source) == []
    for needle in ("eval(", "new Function", "setAttribute('style'", 'setAttribute("style"', "cssText"):
        assert needle not in source, needle


@pytest.mark.asyncio
async def test_rendered_pages_have_nothing_inline():
    """Render every page with real content in it, as an admin so nothing is hidden."""
    admin = await auth.register_user("admin", "password123")
    other = await auth.register_user("alice", "password123")
    board_id = await boards.create_board("general", "talk")
    thread_id = await boards.create_thread(board_id, "hello", other["id"], "first post")
    await chat.create_channel("random", "", admin["id"])
    await chat_manager.broadcast("lobby", "alice", "hi there")
    await chat_manager.broadcast(chat.dm_channel_name(admin["id"], other["id"]), "alice", "psst")
    path, size = file_mod.save_upload("notes.txt", b"data")
    await file_mod.add_file("notes.txt", path, admin["id"], size)
    await auth.update_last_seen(other["id"])

    pages = [
        "/home", "/boards", f"/boards/{board_id}", f"/thread/{thread_id}", "/chat",
        "/files", "/games", "/games/mille", "/online", f"/user/{other['id']}", "/admin",
    ]
    problems = {}
    async with await client_for(admin["id"]) as client:
        for page in pages:
            resp = await client.get(page)
            assert resp.status_code == 200, page
            if found := _violations(resp.text):
                problems[page] = found

        # Mille Bornes renders very different markup once a game is running.
        await client.post("/games/mille/new")
        resp = await client.get("/games/mille")
        if found := _violations(resp.text):
            problems["/games/mille (active)"] = found

    async with anon_client() as client:
        if found := _violations((await client.get("/")).text):
            problems["/"] = found

    assert problems == {}


@pytest.mark.asyncio
async def test_chat_page_hands_its_data_to_the_script_as_attributes():
    admin = await auth.register_user("admin", "password123")
    other = await auth.register_user("alice", "password123")
    await chat.create_channel("random", "", admin["id"])
    dm = chat.dm_channel_name(admin["id"], other["id"])
    await chat_manager.broadcast(dm, "alice", "psst")
    await auth.update_last_seen(other["id"])

    async with await client_for(admin["id"]) as client:
        html = (await client.get(f"/chat?channel={dm}")).text
        unread_html = (await client.get("/chat")).text

    layout = re.search(r'<div id="chat-layout"[^>]*>', html).group(0)
    assert f'data-channel="{dm}"' in layout
    assert 'data-admin="true"' in layout
    assert re.search(r'data-csrf="[0-9a-f]{64}"', layout)

    assert re.search(r'src="/static/js/chat\.js\?v=[0-9a-f]+"', html)
    assert 'data-channel="random"' in html
    assert 'data-channel="lobby" data-switch' in html
    assert f'data-dm-user="{other["id"]}"' in html
    # Opening the DM marked it read; nothing else could have, so the lobby
    # view fetched afterwards must not flag it.
    assert "unread" not in unread_html


@pytest.mark.asyncio
async def test_unread_dm_is_flagged_with_a_class():
    admin = await auth.register_user("admin", "password123")
    other = await auth.register_user("alice", "password123")
    dm = chat.dm_channel_name(admin["id"], other["id"])
    await chat_manager.broadcast(dm, "alice", "psst")

    async with await client_for(admin["id"]) as client:
        html = (await client.get("/chat")).text

    item = re.search(rf'<div class="([^"]*)" data-channel="{dm}"', html)
    assert item and "unread" in item.group(1).split()


@pytest.mark.asyncio
async def test_static_scripts_are_served_and_versioned():
    async with anon_client() as client:
        landing = (await client.get("/")).text
        urls = re.findall(r'(?:src|href)="(/static/[^"]+)"', landing)
        assert any("js/app.js" in u for u in urls)
        assert any("js/login.js" in u for u in urls)
        assert any("style.css" in u for u in urls)
        for url in urls:
            assert "?v=" in url, url
            resp = await client.get(url)
            assert resp.status_code == 200, url
            if ".js" in url:
                assert "javascript" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_destructive_buttons_carry_their_prompt_as_data():
    admin = await auth.register_user("admin", "password123")
    await auth.register_user("alice", "password123")
    async with await client_for(admin["id"]) as client:
        html = (await client.get("/admin")).text
    assert 'data-confirm="Delete user alice?"' in html

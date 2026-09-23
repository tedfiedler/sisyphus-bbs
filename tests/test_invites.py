"""Invitations: the codes admins hand out, and the door they open at /register."""

import pytest

from lib import auth, config, invites
from lib.db import get_db
from tests.helpers import anon_client, client_for


@pytest.fixture
async def admin():
    return await auth.register_user("admin", "password123")


@pytest.fixture
def invite_only(monkeypatch):
    monkeypatch.setattr(config, "INVITE_ONLY", True)


async def _register(client, **fields):
    data = {"username": "newbie", "password": "password123", **fields}
    return await client.post("/register", data=data, follow_redirects=False)


async def _invited_by(username: str):
    db = await get_db()
    cursor = await db.execute("SELECT invited_by FROM users WHERE username = ?", (username,))
    row = await cursor.fetchone()
    return row["invited_by"] if row else "no such user"


async def _expire(invite_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE invites SET expires_at = datetime('now', '-1 minute') WHERE id = ?", (invite_id,)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# The codes themselves
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_code_is_claimed_once(admin):
    code = (await invites.create(admin["id"], "for bob"))["code"]
    claimed = await invites.claim(code)
    assert claimed is not None
    assert await invites.claim(code) is None
    # Given back, it can be claimed again; assigned, it cannot.
    await invites.release(claimed)
    assert await invites.claim(code) == claimed
    await invites.assign(claimed, admin["id"])
    await invites.release(claimed)
    assert await invites.claim(code) is None


@pytest.mark.asyncio
async def test_expired_unknown_and_absurd_codes_are_refused(admin):
    invite = await invites.create(admin["id"])
    await _expire(invite["id"])
    assert await invites.claim(invite["code"]) is None
    assert await invites.claim("") is None
    assert await invites.claim("no-such-code") is None
    assert await invites.claim("x" * 1000) is None
    listed = await invites.list_all()
    assert [(i["id"], bool(i["expired"]), bool(i["open"])) for i in listed] == [(invite["id"], True, False)]


@pytest.mark.asyncio
async def test_only_unused_codes_can_be_revoked(admin):
    fresh = await invites.create(admin["id"])
    used = await invites.create(admin["id"])
    await invites.claim(used["code"])
    assert await invites.revoke(fresh["id"]) is True
    assert await invites.revoke(used["id"]) is False
    assert [i["id"] for i in await invites.list_all()] == [used["id"]]


@pytest.mark.asyncio
async def test_open_codes_are_listed_first(admin):
    old = await invites.create(admin["id"])
    await invites.claim(old["code"])
    new = await invites.create(admin["id"])
    assert [i["id"] for i in await invites.list_all()] == [new["id"], old["id"]]


# ---------------------------------------------------------------------------
# The door
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invite_only_refuses_registration_without_a_code(admin, invite_only):
    async with anon_client() as client:
        resp = await _register(client)
    assert resp.status_code == 403
    assert "invite-only" in resp.text
    assert await auth.authenticate("newbie", "password123") is None


@pytest.mark.asyncio
async def test_invite_only_refuses_a_bad_code(admin, invite_only):
    async with anon_client() as client:
        resp = await _register(client, invite="nope")
    assert resp.status_code == 403
    assert "not valid" in resp.text
    # What they typed is still in the box, on the New User tab.
    assert 'name="invite" placeholder="Invitation code" value="nope"' in resp.text
    assert '<div id="register-form">' in resp.text


@pytest.mark.asyncio
async def test_a_code_admits_exactly_one_person(admin, invite_only):
    code = (await invites.create(admin["id"], "for bob"))["code"]
    async with anon_client() as client:
        first = await _register(client, invite=code)
        second = await _register(client, username="tagalong", invite=code)
    assert first.status_code == 302 and "session_token" in first.headers.get("set-cookie", "")
    assert second.status_code == 403
    assert await _invited_by("newbie") == admin["id"]
    assert await _invited_by("tagalong") == "no such user"
    (invite,) = await invites.list_all()
    assert invite["used_by_name"] == "newbie" and invite["note"] == "for bob"


@pytest.mark.asyncio
async def test_a_taken_name_gives_the_code_back(admin, invite_only):
    code = (await invites.create(admin["id"]))["code"]
    async with anon_client() as client:
        resp = await _register(client, username="admin", invite=code)
        assert resp.status_code == 400
        assert (await _register(client, invite=code)).status_code == 302


@pytest.mark.asyncio
async def test_open_registration_ignores_bad_codes_and_records_good_ones(admin):
    code = (await invites.create(admin["id"]))["code"]
    async with anon_client() as client:
        assert (await _register(client, username="walkin", invite="nonsense")).status_code == 302
        assert (await _register(client, username="brought", invite=code)).status_code == 302
        assert (await _register(client, username="another")).status_code == 302
    assert await _invited_by("walkin") is None
    assert await _invited_by("brought") == admin["id"]
    assert await _invited_by("another") is None


@pytest.mark.asyncio
async def test_landing_page_opens_on_the_new_user_tab_with_the_code(invite_only):
    async with anon_client() as client:
        with_code = await client.get("/?invite=abc123")
        plain = await client.get("/")
    assert 'value="abc123"' in with_code.text
    assert '<div id="register-form">' in with_code.text
    assert '<div id="login-form" class="hidden">' in with_code.text
    assert '<div id="register-form" class="hidden">' in plain.text
    assert "invite-only" in plain.text and 'name="invite"' in plain.text


@pytest.mark.asyncio
async def test_open_board_shows_no_code_field_unless_a_link_carried_one():
    async with anon_client() as client:
        plain = await client.get("/")
        linked = await client.get("/?invite=abc123")
    assert 'name="invite"' not in plain.text
    assert 'name="invite" placeholder="Invitation code" value="abc123"' in linked.text


# ---------------------------------------------------------------------------
# The Admin page
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_makes_and_revokes_invitations(admin):
    async with await client_for(admin["id"]) as client:
        resp = await client.post("/admin/invites", data={"note": "for bob"}, follow_redirects=False)
        assert resp.status_code == 302
        (invite,) = await invites.list_all()
        page = (await client.get("/admin")).text
        assert f"http://testserver/?invite={invite['code']}" in page and "for bob" in page
        resp = await client.post(f"/admin/invites/{invite['id']}/revoke", follow_redirects=False)
        assert resp.status_code == 302
        assert await invites.list_all() == []
        assert "No invitations yet" in (await client.get("/admin")).text


@pytest.mark.asyncio
async def test_the_link_is_built_from_what_the_visitor_sees(admin, monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    code = (await invites.create(admin["id"]))["code"]
    async with await client_for(admin["id"]) as client:
        page = await client.get(
            "/admin", headers={"host": "bbs.example.org", "x-forwarded-proto": "https"},
        )
    assert f"https://bbs.example.org/?invite={code}" in page.text


@pytest.mark.asyncio
async def test_regular_users_cannot_make_invitations(admin):
    bob = await auth.register_user("bob", "password123")
    async with await client_for(bob["id"]) as client:
        assert (await client.post("/admin/invites", data={})).status_code == 403
    assert await invites.list_all() == []


@pytest.mark.asyncio
async def test_deleting_a_user_takes_their_invitations_with_them(admin):
    code = (await invites.create(admin["id"]))["code"]
    async with anon_client() as client:
        assert (await _register(client, username="bob", invite=code)).status_code == 302
    bob = await auth.authenticate("bob", "password123")
    bobs_code = await invites.create(bob["id"])
    assert await _invited_by("bob") == admin["id"]

    await auth.delete_user(bob["id"])
    (remaining,) = await invites.list_all()
    assert remaining["code"] == code and remaining["used_by"] is None
    assert remaining["id"] != bobs_code["id"]

    await auth.delete_user(admin["id"])
    assert await invites.list_all() == []

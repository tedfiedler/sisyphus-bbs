"""Server-side input validation, and the username escaping it backstops."""

import pathlib

import pytest

from lib import auth
from lib.models import (
    BoardCreate, ChatMessage, PostCreate, ProfileText, ThreadCreate,
    UserCreate, validate,
)
from tests.helpers import anon_client, client_for

XSS_USERNAME = '<img src=x onerror=alert(1)>'


# --- username ---------------------------------------------------------------

@pytest.mark.parametrize("username", [
    XSS_USERNAME,
    '<script>alert(1)</script>',
    'has space',
    'quote"name',
    "tick'name",
    'a',                 # too short
    'z' * 33,            # too long
    '_leading',          # must start alphanumeric
    '',
])
def test_invalid_usernames_are_rejected(username):
    form, error = validate(UserCreate, username=username, password="password123")
    assert form is None
    assert error


@pytest.mark.parametrize("username", ["ted", "tim", "admin", "user_1", "a.b-c", "Z9"])
def test_valid_usernames_are_accepted(username):
    """Names already in use must keep working."""
    form, error = validate(UserCreate, username=username, password="password123")
    assert error is None
    assert form.username == username


@pytest.mark.asyncio
async def test_registration_rejects_html_username():
    """The XSS payload cannot reach the database in the first place."""
    async with anon_client() as client:
        resp = await client.post(
            "/register",
            data={"username": XSS_USERNAME, "password": "password123"},
            follow_redirects=False,
        )
    assert resp.status_code == 400
    assert await auth.authenticate(XSS_USERNAME, "password123") is None


@pytest.mark.asyncio
async def test_registration_rejects_overlong_username():
    async with anon_client() as client:
        resp = await client.post(
            "/register",
            data={"username": "z" * 500, "password": "password123"},
            follow_redirects=False,
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_valid_registration_still_succeeds():
    """Guard against over-tightening: an ordinary signup must work."""
    async with anon_client() as client:
        resp = await client.post(
            "/register",
            data={"username": "newcomer", "password": "password123", "email": "a@b.co"},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert await auth.authenticate("newcomer", "password123") is not None


# --- password ---------------------------------------------------------------

def test_short_password_rejected():
    form, error = validate(UserCreate, username="someone", password="abc")
    assert form is None and error


def test_overlong_password_rejected():
    form, error = validate(UserCreate, username="someone", password="a" * 73)
    assert form is None and error


def test_password_limit_counts_bytes_not_characters():
    """A 40-character multibyte password exceeds bcrypt's 72-byte ceiling."""
    form, error = validate(UserCreate, username="someone", password="é" * 40)
    assert form is None and error


def test_verify_password_rejects_overlong_input_without_raising():
    pw_hash = auth.hash_password("password123")
    assert auth.verify_password("a" * 500, pw_hash) is False


@pytest.mark.asyncio
async def test_login_with_overlong_password_is_unauthorized_not_error():
    """This used to raise ValueError out of bcrypt and return a 500."""
    await auth.register_user("alice", "password123")
    async with anon_client() as client:
        resp = await client.post(
            "/login",
            data={"username": "alice", "password": "a" * 100},
            follow_redirects=False,
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_registration_with_overlong_password_reports_the_real_reason():
    """It previously surfaced as the misleading 'Username already taken'."""
    async with anon_client() as client:
        resp = await client.post(
            "/register",
            data={"username": "bob", "password": "a" * 100},
            follow_redirects=False,
        )
    assert resp.status_code == 400
    assert "already taken" not in resp.text


# --- email ------------------------------------------------------------------

@pytest.mark.parametrize("email", ["not-an-email", "a@b", "@b.co", "x" * 250 + "@b.co"])
def test_invalid_emails_rejected(email):
    form, error = validate(UserCreate, username="someone", password="password123", email=email)
    assert form is None and error


@pytest.mark.parametrize("email", ["", "user@example.com"])
def test_acceptable_emails(email):
    form, error = validate(UserCreate, username="someone", password="password123", email=email)
    assert error is None and form.email == email


# --- posts, boards, chat, profile -------------------------------------------

@pytest.mark.parametrize("body", ["", "   ", "x" * 20001])
def test_invalid_post_bodies_rejected(body):
    form, error = validate(PostCreate, body=body)
    assert form is None and error


def test_thread_subject_bounds():
    assert validate(ThreadCreate, subject="", body="ok")[1]
    assert validate(ThreadCreate, subject="   ", body="ok")[1]
    assert validate(ThreadCreate, subject="s" * 129, body="ok")[1]
    assert validate(ThreadCreate, subject="fine", body="ok")[1] is None


def test_board_name_bounds():
    assert validate(BoardCreate, name="")[1]
    assert validate(BoardCreate, name="n" * 65)[1]
    assert validate(BoardCreate, name="General")[1] is None


def test_chat_message_bounds():
    assert validate(ChatMessage, message="")[1]
    assert validate(ChatMessage, message="m" * 2001)[1]
    assert validate(ChatMessage, message="hello")[1] is None


def test_profile_text_bounds():
    assert validate(ProfileText, text="t" * 2001)[1]
    assert validate(ProfileText, text="about me")[1] is None


@pytest.mark.asyncio
async def test_oversized_post_is_rejected_by_the_route():
    from lib import boards
    admin = await auth.register_user("admin", "password123")
    board_id = await boards.create_board("General")
    thread_id = await boards.create_thread(board_id, "T", admin["id"], "body")

    async with await client_for(admin["id"]) as client:
        resp = await client.post(
            f"/thread/{thread_id}/reply",
            data={"body": "x" * 20001},
            follow_redirects=False,
        )

    assert resp.status_code == 400
    assert len(await boards.list_posts(thread_id)) == 1


@pytest.mark.asyncio
async def test_empty_reply_does_not_create_a_post():
    from lib import boards
    admin = await auth.register_user("admin", "password123")
    board_id = await boards.create_board("General")
    thread_id = await boards.create_thread(board_id, "T", admin["id"], "body")

    async with await client_for(admin["id"]) as client:
        resp = await client.post(
            f"/thread/{thread_id}/reply", data={"body": "   "}, follow_redirects=False
        )

    assert resp.status_code == 400
    assert len(await boards.list_posts(thread_id)) == 1


# --- template escaping ------------------------------------------------------

def test_chat_template_escapes_every_interpolated_field():
    """Usernames reach the DOM through innerHTML; none may go in raw.

    A source check, not a browser test: it guards against reintroducing an
    unescaped interpolation in the message-rendering path.
    """
    source = pathlib.Path("frontend/templates/chat.html").read_text()
    for raw in ("${data.username}", "${data.message}", "${time}", "${data.created_at}"):
        assert raw not in source, f"unescaped interpolation {raw} in chat.html"


@pytest.mark.asyncio
async def test_legacy_username_can_still_log_in():
    """Accounts predating the charset rules must not be locked out."""
    legacy = "old style user!"
    await auth.register_user(legacy, "password123")  # bypasses route validation
    assert validate(UserCreate, username=legacy, password="password123")[1]

    async with anon_client() as client:
        resp = await client.post(
            "/login",
            data={"username": legacy, "password": "password123"},
            follow_redirects=False,
        )
    assert resp.status_code == 302

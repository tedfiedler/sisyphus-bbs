"""Authentication and user management utilities.

Provide password hashing, session management, and role-based access control
backed by an SQLite database.
"""

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt

from lib import config
from lib.db import get_db
from lib.files import unlink_stored


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt and return the encoded hash."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    bcrypt refuses inputs over 72 bytes, which no stored password can be;
    such a candidate simply cannot match, so treat it as a failed attempt
    rather than letting the error escape to the caller.
    """
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# Checked when the username does not exist, so a miss costs the same bcrypt
# round as a wrong password and response time does not reveal which names
# are registered.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _hash_token(token: str) -> str:
    """Return the digest a session token is stored under.

    Only the digest is kept, so a copy of the database (a backup, a stray
    dump) does not hand out live sessions. Tokens are 256 bits of randomness,
    so a plain SHA-256 is enough; there is nothing to brute-force.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def register_user(username: str, password: str, email: str = "") -> dict | None:
    """Register a new user and return their info, or None if the name is taken.

    Promote the first registered user to superadmin automatically. The
    "is this the first user" decision and the name check both live inside
    the INSERT itself: with an ``await`` between a separate COUNT and INSERT,
    two concurrent signups on an empty database could each be made
    superadmin. Names are compared case-insensitively so ``Admin`` cannot be
    registered alongside ``admin`` to impersonate them.
    """
    db = await get_db()
    pw_hash = hash_password(password)
    try:
        cursor = await db.execute(
            """INSERT INTO users (username, password_hash, email, access_level)
               SELECT ?, ?, ?, CASE WHEN EXISTS (SELECT 1 FROM users) THEN 0 ELSE 2 END
               WHERE NOT EXISTS (
                   SELECT 1 FROM users WHERE username = ? COLLATE NOCASE
               )""",
            (username, pw_hash, email, username),
        )
    except sqlite3.IntegrityError:
        return None
    if cursor.rowcount == 0:
        return None
    user_id = cursor.lastrowid
    await db.commit()
    cursor = await db.execute("SELECT access_level FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    return {"id": user_id, "username": username, "access_level": row["access_level"]}


async def authenticate(username: str, password: str) -> dict | None:
    """Authenticate a user by username and password, returning user info or None."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, password_hash, access_level FROM users WHERE username = ?",
        (username,),
    )
    row = await cursor.fetchone()
    if row is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    await db.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],)
    )
    await db.execute(
        "INSERT OR IGNORE INTO login_days (user_id, login_date) VALUES (?, date('now'))",
        (row["id"],),
    )
    await db.commit()
    return {"id": row["id"], "username": row["username"], "access_level": row["access_level"]}


async def delete_expired_sessions() -> int:
    """Remove sessions whose expiry has passed. Returns the number deleted."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (datetime.now(timezone.utc).isoformat(),),
    )
    await db.commit()
    return cursor.rowcount


async def create_session(user_id: int) -> str:
    """Create a new session for the given user and return the session token.

    Expired rows are swept here: logins are the only thing that adds sessions,
    so this keeps the table proportional to recent activity without needing a
    background job.
    """
    db = await get_db()
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_EXPIRY_HOURS)
    await db.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (datetime.now(timezone.utc).isoformat(),),
    )
    await db.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, _hash_token(token), expires.isoformat()),
    )
    await db.commit()
    return token


async def get_user_by_token(token: str) -> dict | None:
    """Look up a user by session token, returning None if expired or invalid."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT u.id, u.username, u.access_level
           FROM sessions s JOIN users u ON s.user_id = u.id
           WHERE s.token = ? AND s.expires_at > ?""",
        (_hash_token(token), datetime.now(timezone.utc).isoformat()),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "access_level": row["access_level"]}


async def delete_session(token: str):
    """Delete a session by its token, effectively logging the user out."""
    db = await get_db()
    await db.execute("DELETE FROM sessions WHERE token = ?", (_hash_token(token),))
    await db.commit()


def is_admin(user: dict) -> bool:
    """Check whether the user has admin privileges (access level >= 1)."""
    return user.get("access_level", 0) >= 1


def is_superadmin(user: dict) -> bool:
    """Check whether the user has superadmin privileges (access level == 2)."""
    return user.get("access_level", 0) == 2


async def list_users() -> list[dict]:
    """Return all users ordered by ID, excluding password hashes."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, email, access_level, created_at, last_login, file_upload_allowed FROM users ORDER BY id"
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_user(user_id: int) -> dict | None:
    """Return a single user by ID, or None if not found."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, email, access_level, created_at, last_login, last_seen, about_me, landing_message, file_upload_allowed FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def set_access_level(user_id: int, level: int):
    """Set the access level for a user (0=regular, 1=admin, 2=superadmin)."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET access_level = ? WHERE id = ?", (level, user_id)
    )
    await db.commit()


async def delete_user(user_id: int, reassign_channels_to: int | None = None):
    """Delete a user and every row that references them.

    Threads the user started are removed along with their replies, since
    ``threads.author_id`` cannot be left dangling. Chat channels the user
    created are handed to *reassign_channels_to* (falling back to another
    admin) so a shared channel outlives its creator; if no other admin
    remains, the channel and its messages are removed.

    The whole deletion is committed as a single transaction.
    """
    db = await get_db()

    # Uploaded files: remove from disk first, then drop the rows.
    cursor = await db.execute("SELECT path FROM files WHERE uploader_id = ?", (user_id,))
    for row in await cursor.fetchall():
        unlink_stored(row["path"])
    await db.execute("DELETE FROM files WHERE uploader_id = ?", (user_id,))

    # Likes must go before the posts they point at.
    await db.execute("DELETE FROM post_likes WHERE user_id = ?", (user_id,))
    await db.execute(
        """DELETE FROM post_likes WHERE post_id IN (
               SELECT id FROM posts
               WHERE author_id = ?
                  OR thread_id IN (SELECT id FROM threads WHERE author_id = ?)
           )""",
        (user_id, user_id),
    )

    # Posts by this user, plus any replies left in threads they started.
    await db.execute(
        """DELETE FROM posts
           WHERE author_id = ?
              OR thread_id IN (SELECT id FROM threads WHERE author_id = ?)""",
        (user_id, user_id),
    )
    await db.execute("DELETE FROM threads WHERE author_id = ?", (user_id,))

    # Chat channels they created outlive them where possible.
    cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM chat_channels WHERE created_by = ?", (user_id,)
    )
    if (await cursor.fetchone())["cnt"]:
        heir = reassign_channels_to
        if heir is None or heir == user_id:
            cursor = await db.execute(
                "SELECT id FROM users WHERE access_level >= 1 AND id != ? LIMIT 1",
                (user_id,),
            )
            row = await cursor.fetchone()
            heir = row["id"] if row else None
        if heir is None:
            await db.execute(
                """DELETE FROM chat_messages WHERE channel IN (
                       SELECT name FROM chat_channels WHERE created_by = ?
                   )""",
                (user_id,),
            )
            await db.execute("DELETE FROM chat_channels WHERE created_by = ?", (user_id,))
        else:
            await db.execute(
                "UPDATE chat_channels SET created_by = ? WHERE created_by = ?",
                (heir, user_id),
            )

    for table in ("chat_messages", "game_scores", "login_days", "dm_channel_seen", "sessions"):
        await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))

    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()


async def update_last_seen(user_id: int):
    """Update the last_seen timestamp for a user to the current time."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user_id,)
    )
    await db.commit()


async def list_online_users() -> list[dict]:
    """Return users seen within the last 5 minutes."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, username, last_seen
           FROM users
           WHERE last_seen > datetime('now', '-5 minutes')
           ORDER BY username"""
    )
    return [dict(r) for r in await cursor.fetchall()]


async def list_users_directory() -> list[dict]:
    """Return all users with a computed is_online flag, ordered alphabetically."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, username, access_level, created_at, last_seen,
                  CASE WHEN last_seen > datetime('now', '-5 minutes') THEN 1 ELSE 0 END AS is_online
           FROM users
           ORDER BY username COLLATE NOCASE"""
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_landing_message() -> str:
    """Return the superadmin's landing message text."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT landing_message FROM users WHERE access_level = 2 LIMIT 1"
    )
    row = await cursor.fetchone()
    return row["landing_message"] if row and row["landing_message"] else ""


async def update_landing_message(user_id: int, message: str):
    """Update the landing message for a user."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET landing_message = ? WHERE id = ?", (message, user_id)
    )
    await db.commit()


async def update_about_me(user_id: int, about_me: str):
    """Update the about_me text for a user."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET about_me = ? WHERE id = ?", (about_me, user_id)
    )
    await db.commit()


async def get_login_streak(user_id: int) -> int:
    """Return the number of consecutive login days ending today for the given user."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT login_date FROM login_days WHERE user_id = ? ORDER BY login_date DESC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    dates = {row["login_date"] for row in rows}
    # login_days rows are written with SQLite's date('now'), which is UTC,
    # so the streak must be walked in UTC too.
    today = datetime.now(timezone.utc).date()
    if today.isoformat() not in dates:
        return 0
    streak = 0
    day = today
    while day.isoformat() in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def check_file_access(user: dict) -> dict:
    """Check whether a user meets all criteria for file section access."""
    if is_admin(user):
        return {
            "allowed": True,
            "is_admin": True,
            "streak": 0,
            "streak_ok": True,
            "admin_approved": True,
            "has_like": True,
            "has_game": True,
        }
    db = await get_db()
    streak = await get_login_streak(user["id"])
    streak_ok = streak >= 5

    # Read the flag from the database rather than trusting the caller's dict:
    # session-derived user dicts only carry id/username/access_level.
    cursor = await db.execute(
        "SELECT file_upload_allowed FROM users WHERE id = ?", (user["id"],)
    )
    row = await cursor.fetchone()
    admin_approved = bool(row["file_upload_allowed"]) if row else False

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM post_likes pl JOIN posts p ON pl.post_id = p.id WHERE p.author_id = ?",
        (user["id"],),
    )
    row = await cursor.fetchone()
    has_like = row["cnt"] > 0

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM game_scores WHERE user_id = ?",
        (user["id"],),
    )
    row = await cursor.fetchone()
    has_game = row["cnt"] > 0

    allowed = streak_ok and admin_approved and has_like and has_game
    return {
        "allowed": allowed,
        "is_admin": False,
        "streak": streak,
        "streak_ok": streak_ok,
        "admin_approved": admin_approved,
        "has_like": has_like,
        "has_game": has_game,
    }

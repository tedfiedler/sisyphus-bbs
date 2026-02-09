import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

import config
from db import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


async def register_user(username: str, password: str, email: str = "") -> dict | None:
    db = await get_db()
    try:
        pw_hash = hash_password(password)
        cursor = await db.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, pw_hash, email),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "username": username}
    except Exception:
        return None


async def authenticate(username: str, password: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, password_hash, access_level FROM users WHERE username = ?",
        (username,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    await db.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],)
    )
    await db.commit()
    return {"id": row["id"], "username": row["username"], "access_level": row["access_level"]}


async def create_session(user_id: int) -> str:
    db = await get_db()
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_EXPIRY_HOURS)
    await db.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires.isoformat()),
    )
    await db.commit()
    return token


async def get_user_by_token(token: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT u.id, u.username, u.access_level
           FROM sessions s JOIN users u ON s.user_id = u.id
           WHERE s.token = ? AND s.expires_at > ?""",
        (token, datetime.now(timezone.utc).isoformat()),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "access_level": row["access_level"]}


async def delete_session(token: str):
    db = await get_db()
    await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    await db.commit()

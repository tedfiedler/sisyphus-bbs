"""Invitation codes: how new members arrive on an invite-only board.

An admin makes a code on the Admin page and hands the link to one person.
A code is single-use and good for ``INVITE_DAYS``; once redeemed it records
who invited whom. With ``SISYPHUS_INVITE_ONLY`` set, ``/register`` refuses
anything without a valid code. With it off, registration is open and a code,
if one is given, still records the introduction.

Redeeming is two steps around the account's creation: :func:`claim` takes
the code out of circulation in one atomic UPDATE, so two people racing on
the same code cannot both get in; :func:`assign` records the new account
against it, or :func:`release` puts the code back if the registration
failed after all (name taken).

Codes are stored in the clear so an admin can copy the link again later.
They are 96 bits of randomness, good for a week, and worth exactly one
account on a board whose members are all known to the sysop: nothing that
would justify making them show-once.
"""

import secrets

from lib.db import get_db

INVITE_DAYS = 7
NOTE_MAX = 80
CODE_MAX = 64


def new_code() -> str:
    return secrets.token_urlsafe(12)


async def get(invite_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(_SELECT + " WHERE i.id = ?", (invite_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create(created_by: int, note: str = "") -> dict:
    """Make a new code. Expired, never-used codes older than a month are swept out."""
    db = await get_db()
    await db.execute(
        "DELETE FROM invites WHERE used_at IS NULL AND expires_at < datetime('now', '-30 days')"
    )
    cursor = await db.execute(
        """INSERT INTO invites (code, created_by, note, expires_at)
           VALUES (?, ?, ?, datetime('now', ?))""",
        (new_code(), created_by, note.strip()[:NOTE_MAX], f"+{INVITE_DAYS} days"),
    )
    await db.commit()
    return await get(cursor.lastrowid)


async def list_all(limit: int = 50) -> list[dict]:
    """Open codes first, newest first, then the redeemed and expired ones for the record."""
    db = await get_db()
    cursor = await db.execute(_SELECT + " ORDER BY open DESC, i.id DESC LIMIT ?", (limit,))
    return [dict(row) for row in await cursor.fetchall()]


async def revoke(invite_id: int) -> bool:
    """Delete a code that has not been used. Returns whether anything was deleted."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM invites WHERE id = ? AND used_at IS NULL", (invite_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def claim(code: str) -> int | None:
    """Take an open code out of circulation and return its id.

    None if the code is unknown, already used, or expired. The single UPDATE
    is the whole race: whichever of two simultaneous registrations runs it
    first gets the code, and the other sees no row to change.
    """
    code = code.strip()
    if not code or len(code) > CODE_MAX:
        return None
    db = await get_db()
    cursor = await db.execute(
        """UPDATE invites SET used_at = datetime('now')
           WHERE code = ? AND used_at IS NULL AND expires_at > datetime('now')""",
        (code,),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    cursor = await db.execute("SELECT id FROM invites WHERE code = ?", (code,))
    return (await cursor.fetchone())["id"]


async def release(invite_id: int) -> None:
    """Put a claimed code back, because the registration it was claimed for failed."""
    db = await get_db()
    await db.execute(
        "UPDATE invites SET used_at = NULL WHERE id = ? AND used_by IS NULL", (invite_id,)
    )
    await db.commit()


async def assign(invite_id: int, user_id: int) -> None:
    """Record the account a claimed code produced, on both the code and the user."""
    db = await get_db()
    await db.execute("UPDATE invites SET used_by = ? WHERE id = ?", (user_id, invite_id))
    await db.execute(
        "UPDATE users SET invited_by = (SELECT created_by FROM invites WHERE id = ?) WHERE id = ?",
        (invite_id, user_id),
    )
    await db.commit()


_SELECT = """
    SELECT i.id, i.code, i.created_by, i.created_at, i.expires_at, i.note,
           i.used_by, i.used_at,
           c.username AS created_by_name, u.username AS used_by_name,
           (i.used_at IS NULL AND i.expires_at > datetime('now')) AS open,
           (i.used_at IS NULL AND i.expires_at <= datetime('now')) AS expired
    FROM invites i
    JOIN users c ON c.id = i.created_by
    LEFT JOIN users u ON u.id = i.used_by
"""

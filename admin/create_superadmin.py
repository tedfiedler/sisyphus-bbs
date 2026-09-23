#!/usr/bin/env python3
"""Create the superadmin account on an empty database.

On a fresh board the first account to register becomes superadmin, which is
fine on a laptop and a race on a public server: whoever finds the address
first owns the board. This makes the account before anyone can, and refuses
to run once any account exists.

Usage:
    python admin/create_superadmin.py USERNAME              # asks for the password twice
    python admin/create_superadmin.py USERNAME --password-stdin < file
    python admin/create_superadmin.py USERNAME --if-empty   # exit 0, do nothing, if accounts exist

Safe to run while the server is up: it only adds a row, which the running
server sees at once.
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import auth
from lib.db import close_db, get_db
from lib.models import UserCreate, validate


async def _has_accounts() -> bool:
    db = await get_db()
    cursor = await db.execute("SELECT 1 FROM users LIMIT 1")
    return await cursor.fetchone() is not None


async def create(username: str, password: str) -> int:
    """Create the account and return an exit status; the message goes to stdout."""
    try:
        if await _has_accounts():
            print("This board already has accounts; the superadmin exists. Nothing done.")
            return 2
        user = await auth.register_user(username, password)
        if user is None or user["access_level"] != 2:
            print("Could not create the account.")
            return 1
        print(f"Superadmin '{username}' created.")
        return 0
    finally:
        await close_db()


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if len(args) != 1 or flags - {"--password-stdin", "--if-empty"}:
        print(__doc__.strip().split("Usage:")[1].strip())
        return 2
    username = args[0]

    if "--if-empty" in flags and asyncio.run(_check_then_close()):
        print("Accounts exist already; nothing to do.")
        return 0

    if "--password-stdin" in flags:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass(f"Password for {username}: ")
        if password != getpass.getpass("Again: "):
            print("The passwords do not match.")
            return 1

    _, error = validate(UserCreate, username=username, password=password)
    if error:
        print(error)
        return 1
    return asyncio.run(create(username, password))


async def _check_then_close() -> bool:
    try:
        return await _has_accounts()
    finally:
        await close_db()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

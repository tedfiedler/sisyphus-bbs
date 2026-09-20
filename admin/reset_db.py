#!/usr/bin/env python3
"""Reset the Sisyphus BBS to a fresh install.

Deletes the database (and its WAL/shm files) and every uploaded file, then
reinitializes an empty database with the schema. The first account
registered afterwards becomes superadmin.

The server must be stopped first. A running server keeps the old database
open, so deleting the file underneath it changes nothing it can see: every
account, the admin included, carries on working until the next restart, and
anything written in the meantime is lost.

Usage:
    ./sisyphus.sh stop
    python admin/reset_db.py [--yes] [--force]
"""

import asyncio
import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config
from lib.db import get_db, close_db


def server_is_running() -> bool:
    """Return True if something is accepting connections on the BBS port."""
    host = "127.0.0.1" if config.WEB_HOST in ("0.0.0.0", "::", "") else config.WEB_HOST
    try:
        with socket.create_connection((host, config.WEB_PORT), timeout=1):
            return True
    except OSError:
        return False


def clear_file_store() -> int:
    """Delete every uploaded file. Returns how many were removed.

    Uploads are only reachable through their ``files`` rows; once the
    database is gone they can be neither downloaded nor deleted from the UI.
    """
    store = config.FILE_STORE
    if not store.is_dir():
        return 0
    removed = sum(1 for p in store.rglob("*") if p.is_file())
    for child in store.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return removed


async def reset():
    db_path = Path(config.DB_PATH)

    # Remove existing database files
    removed = []
    for suffix in ("", "-shm", "-wal"):
        f = Path(str(db_path) + suffix)
        if f.exists():
            f.unlink()
            removed.append(f.name)

    if removed:
        print(f"Removed: {', '.join(removed)}")
    else:
        print("No existing database found.")

    print(f"Removed {clear_file_store()} uploaded file(s) from {config.FILE_STORE}")

    # Reinitialize with fresh schema
    await get_db()
    await close_db()
    print(f"Database initialized at {db_path}")
    print("The first account registered will become superadmin.")


if __name__ == "__main__":
    if server_is_running() and "--force" not in sys.argv:
        print(
            f"The BBS appears to be running on port {config.WEB_PORT}. Stop it first "
            "(./sisyphus.sh stop):\na running server keeps the old database open and "
            "would not see the reset.\nPass --force to reset anyway."
        )
        sys.exit(1)

    if "--yes" not in sys.argv:
        answer = input("This will delete ALL data, including uploaded files. Continue? [y/N] ")
        if answer.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(reset())

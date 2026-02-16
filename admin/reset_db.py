#!/usr/bin/env python3
"""Reset the Sisyphus BBS database.

Deletes the existing database (and WAL/shm files) and reinitializes
a fresh empty database with the schema.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config
from lib.db import get_db, close_db


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

    # Reinitialize with fresh schema
    await get_db()
    await close_db()
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        answer = input("This will delete ALL data. Continue? [y/N] ")
        if answer.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(reset())

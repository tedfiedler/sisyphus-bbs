import os
from pathlib import Path

import config
from db import get_db


async def list_files(area: str | None = None) -> list[dict]:
    db = await get_db()
    if area:
        cursor = await db.execute(
            """SELECT f.*, u.username as uploader_name
               FROM files f JOIN users u ON f.uploader_id = u.id
               WHERE f.area = ? ORDER BY f.uploaded_at DESC""",
            (area,),
        )
    else:
        cursor = await db.execute(
            """SELECT f.*, u.username as uploader_name
               FROM files f JOIN users u ON f.uploader_id = u.id
               ORDER BY f.uploaded_at DESC"""
        )
    return [dict(r) for r in await cursor.fetchall()]


async def list_areas() -> list[str]:
    db = await get_db()
    cursor = await db.execute("SELECT DISTINCT area FROM files ORDER BY area")
    return [row["area"] for row in await cursor.fetchall()]


async def add_file(
    filename: str,
    path: str,
    uploader_id: int,
    size_bytes: int,
    area: str = "general",
    description: str = "",
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO files (area, filename, description, uploader_id, size_bytes, path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (area, filename, description, uploader_id, size_bytes, path),
    )
    await db.commit()
    return cursor.lastrowid


async def get_file(file_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def increment_download(file_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE files SET download_count = download_count + 1 WHERE id = ?",
        (file_id,),
    )
    await db.commit()


def save_upload(filename: str, data: bytes, area: str = "general") -> tuple[str, int]:
    area_dir = config.FILE_STORE / area
    area_dir.mkdir(parents=True, exist_ok=True)
    dest = area_dir / filename
    # Avoid overwriting
    counter = 1
    while dest.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        dest = area_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    dest.write_bytes(data)
    return str(dest), len(data)

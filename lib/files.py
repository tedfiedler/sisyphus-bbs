"""File storage and retrieval operations backed by SQLite and the local filesystem."""

import os
import re
from pathlib import Path

from lib import config
from lib.db import get_db


async def list_files(area: str | None = None) -> list[dict]:
    """Return all files, optionally filtered by area, sorted newest first."""
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
    """Return a sorted list of distinct area names that contain files."""
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
    """Insert a new file record into the database and return its row ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO files (area, filename, description, uploader_id, size_bytes, path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (area, filename, description, uploader_id, size_bytes, path),
    )
    await db.commit()
    return cursor.lastrowid


async def get_file(file_id: int) -> dict | None:
    """Return the file record for the given ID, or None if not found."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def increment_download(file_id: int):
    """Bump the download counter for the given file by one."""
    db = await get_db()
    await db.execute(
        "UPDATE files SET download_count = download_count + 1 WHERE id = ?",
        (file_id,),
    )
    await db.commit()


async def delete_file(file_id: int):
    """Remove the file from disk and delete its database record."""
    db = await get_db()
    cursor = await db.execute("SELECT path FROM files WHERE id = ?", (file_id,))
    row = await cursor.fetchone()
    if row:
        unlink_stored(row["path"])
        await db.execute("DELETE FROM files WHERE id = ?", (file_id,))
        await db.commit()


def unlink_stored(path: str) -> None:
    """Remove an uploaded file from disk, refusing anything outside FILE_STORE.

    Stored paths are written by :func:`save_upload`, so this should never
    trip; it is here so a tampered or corrupted ``files.path`` row cannot
    turn a delete button into an arbitrary-file unlink.
    """
    target = Path(path).resolve()
    if not target.is_relative_to(config.FILE_STORE.resolve()):
        return
    try:
        os.unlink(target)
    except OSError:
        pass


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._ -]")
MAX_FILENAME_LENGTH = 100


def sanitize_filename(filename: str) -> str:
    """Reduce a client-supplied filename to a safe basename, or raise ValueError.

    Path components are dropped (both separators, since a Windows client
    sends backslashes that ``Path.name`` keeps on POSIX), anything outside a
    conservative character set becomes ``_`` so control characters and
    header/HTML metacharacters never reach the disk or a
    ``Content-Disposition`` header, and the stem is trimmed so the name fits
    comfortably inside filesystem limits.
    """
    filename = Path(filename.replace("\\", "/")).name
    filename = _UNSAFE_FILENAME_CHARS.sub("_", filename).strip()
    if not filename or filename.startswith("."):
        raise ValueError("Invalid filename")
    suffix = Path(filename).suffix[:16]
    stem = Path(filename).stem[: MAX_FILENAME_LENGTH - len(suffix)]
    return stem + suffix


def save_upload(filename: str, data: bytes, area: str = "general") -> tuple[str, int]:
    """Sanitize the filename, write bytes to the area directory, and return the path and size."""
    filename = sanitize_filename(filename)
    # Sanitize area — alphanumeric, underscore, hyphen only
    area = re.sub(r'[^a-zA-Z0-9_-]', '', area) or "general"
    area_dir = config.FILE_STORE / area
    area_dir.mkdir(parents=True, exist_ok=True)
    dest = area_dir / filename
    # Verify resolved path stays inside FILE_STORE
    if not dest.resolve().is_relative_to(config.FILE_STORE.resolve()):
        raise ValueError("Path traversal detected")
    # Avoid overwriting. Mode "x" makes create-if-absent a single atomic
    # step; checking exists() first and writing afterwards let two uploads
    # of the same name race and one silently replace the other.
    stem, suffix = Path(filename).stem, Path(filename).suffix
    counter = 0
    while True:
        try:
            with open(dest, "xb") as fh:
                fh.write(data)
            break
        except FileExistsError:
            counter += 1
            dest = area_dir / f"{stem}_{counter}{suffix}"
    return str(dest), len(data)

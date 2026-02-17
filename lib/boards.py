"""Database operations for boards, threads, and posts."""

from lib.db import get_db


async def list_boards() -> list[dict]:
    """Return all boards with their thread and post counts, ordered by sort_order then name."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT b.*,
           (SELECT COUNT(*) FROM threads t WHERE t.board_id = b.id) as thread_count,
           (SELECT COUNT(*) FROM posts p JOIN threads t ON p.thread_id = t.id WHERE t.board_id = b.id) as post_count
           FROM boards b ORDER BY b.sort_order, b.name"""
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_board(board_id: int) -> dict | None:
    """Return a single board by its ID, or None if not found."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM boards WHERE id = ?", (board_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_board(name: str, description: str = "", sort_order: int = 0) -> int:
    """Create a new board and return its ID."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO boards (name, description, sort_order) VALUES (?, ?, ?)",
        (name, description, sort_order),
    )
    await db.commit()
    return cursor.lastrowid


async def list_threads(board_id: int) -> list[dict]:
    """Return all threads for a board, with post counts, ordered by pinned status then latest activity."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.*, u.username as author_name,
           (SELECT COUNT(*) FROM posts p WHERE p.thread_id = t.id) as post_count,
           (SELECT MAX(p.created_at) FROM posts p WHERE p.thread_id = t.id) as last_post_at
           FROM threads t JOIN users u ON t.author_id = u.id
           WHERE t.board_id = ?
           ORDER BY t.pinned DESC, last_post_at DESC""",
        (board_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_thread(thread_id: int) -> dict | None:
    """Return a single thread with its author name, or None if not found."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT t.*, u.username as author_name FROM threads t JOIN users u ON t.author_id = u.id WHERE t.id = ?",
        (thread_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_thread(board_id: int, subject: str, author_id: int, body: str) -> int:
    """Create a new thread with an initial post and return the thread ID."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO threads (board_id, subject, author_id) VALUES (?, ?, ?)",
        (board_id, subject, author_id),
    )
    thread_id = cursor.lastrowid
    await db.execute(
        "INSERT INTO posts (thread_id, author_id, body) VALUES (?, ?, ?)",
        (thread_id, author_id, body),
    )
    await db.commit()
    return thread_id


async def list_posts(thread_id: int, user_id: int | None = None) -> list[dict]:
    """Return all posts in a thread with author names, like counts, and current user's liked status."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT p.*, u.username as author_name,
           (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id) as like_count,
           (SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id = p.id AND pl.user_id = ?) as liked
           FROM posts p JOIN users u ON p.author_id = u.id
           WHERE p.thread_id = ?
           ORDER BY p.created_at""",
        (user_id, thread_id),
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    for row in rows:
        row["liked"] = bool(row["liked"])
    return rows


async def create_post(thread_id: int, author_id: int, body: str) -> int:
    """Create a new post in a thread and return its ID."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO posts (thread_id, author_id, body) VALUES (?, ?, ?)",
        (thread_id, author_id, body),
    )
    await db.commit()
    return cursor.lastrowid


async def toggle_like(post_id: int, user_id: int) -> int:
    """Toggle a like on a post. Returns the new like count."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?",
        (post_id, user_id),
    )
    existing = await cursor.fetchone()
    if existing:
        await db.execute("DELETE FROM post_likes WHERE id = ?", (existing[0],))
    else:
        await db.execute(
            "INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)",
            (post_id, user_id),
        )
    await db.commit()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM post_likes WHERE post_id = ?", (post_id,)
    )
    row = await cursor.fetchone()
    return row[0]


async def delete_post(post_id: int):
    """Delete a single post by its ID."""
    db = await get_db()
    await db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    await db.commit()


async def delete_thread(thread_id: int):
    """Delete a thread and all of its posts."""
    db = await get_db()
    await db.execute("DELETE FROM posts WHERE thread_id = ?", (thread_id,))
    await db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
    await db.commit()

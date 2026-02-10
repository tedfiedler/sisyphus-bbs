from db import get_db


async def list_boards() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT b.*,
           (SELECT COUNT(*) FROM threads t WHERE t.board_id = b.id) as thread_count,
           (SELECT COUNT(*) FROM posts p JOIN threads t ON p.thread_id = t.id WHERE t.board_id = b.id) as post_count
           FROM boards b ORDER BY b.sort_order, b.name"""
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_board(board_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM boards WHERE id = ?", (board_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_board(name: str, description: str = "", sort_order: int = 0) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO boards (name, description, sort_order) VALUES (?, ?, ?)",
        (name, description, sort_order),
    )
    await db.commit()
    return cursor.lastrowid


async def list_threads(board_id: int) -> list[dict]:
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
    db = await get_db()
    cursor = await db.execute(
        "SELECT t.*, u.username as author_name FROM threads t JOIN users u ON t.author_id = u.id WHERE t.id = ?",
        (thread_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_thread(board_id: int, subject: str, author_id: int, body: str) -> int:
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


async def list_posts(thread_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT p.*, u.username as author_name
           FROM posts p JOIN users u ON p.author_id = u.id
           WHERE p.thread_id = ?
           ORDER BY p.created_at""",
        (thread_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def create_post(thread_id: int, author_id: int, body: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO posts (thread_id, author_id, body) VALUES (?, ?, ?)",
        (thread_id, author_id, body),
    )
    await db.commit()
    return cursor.lastrowid


async def delete_post(post_id: int):
    db = await get_db()
    await db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    await db.commit()


async def delete_thread(thread_id: int):
    db = await get_db()
    await db.execute("DELETE FROM posts WHERE thread_id = ?", (thread_id,))
    await db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
    await db.commit()

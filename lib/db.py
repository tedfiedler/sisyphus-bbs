"""Manage the shared aiosqlite database connection and schema initialization."""

import aiosqlite
from lib import config

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    access_level INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    about_me TEXT DEFAULT '',
    landing_message TEXT DEFAULT '',
    last_dm_seen TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id),
    subject TEXT NOT NULL,
    author_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pinned INTEGER DEFAULT 0,
    locked INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL REFERENCES threads(id),
    author_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT DEFAULT 'general',
    filename TEXT NOT NULL,
    description TEXT DEFAULT '',
    uploader_id INTEGER NOT NULL REFERENCES users(id),
    size_bytes INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    channel TEXT DEFAULT 'lobby',
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS game_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    game TEXT NOT NULL DEFAULT 'mille',
    score INTEGER NOT NULL,
    opponent TEXT NOT NULL,
    won INTEGER NOT NULL DEFAULT 0,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS post_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, user_id)
);

CREATE TABLE IF NOT EXISTS login_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    login_date TEXT NOT NULL,
    UNIQUE(user_id, login_date)
);

CREATE TABLE IF NOT EXISTS dm_channel_seen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    channel TEXT NOT NULL,
    last_seen_at TIMESTAMP NOT NULL,
    UNIQUE(user_id, channel)
);

-- Indexes for the lookups the app makes on every page: thread and board
-- listings, like counts, channel history, and session expiry sweeps.
CREATE INDEX IF NOT EXISTS idx_posts_thread ON posts(thread_id);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_threads_board ON threads(board_id);
CREATE INDEX IF NOT EXISTS idx_threads_author ON threads(author_id);
CREATE INDEX IF NOT EXISTS idx_post_likes_post ON post_likes(post_id);
CREATE INDEX IF NOT EXISTS idx_post_likes_user ON post_likes(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_channel ON chat_messages(channel, id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_files_uploader ON files(uploader_id);
CREATE INDEX IF NOT EXISTS idx_game_scores_user ON game_scores(user_id);
CREATE INDEX IF NOT EXISTS idx_login_days_user ON login_days(user_id);
"""


async def _migrate(db: aiosqlite.Connection):
    """Run lightweight migrations for columns added after initial schema creation."""
    cursor = await db.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "last_seen" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP")
    if "about_me" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN about_me TEXT DEFAULT ''")
    if "landing_message" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN landing_message TEXT DEFAULT ''")
    if "last_dm_seen" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN last_dm_seen TIMESTAMP")
    if "file_upload_allowed" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN file_upload_allowed INTEGER DEFAULT 0")

    cursor = await db.execute("PRAGMA table_info(game_scores)")
    gs_columns = {row[1] for row in await cursor.fetchall()}
    if "game" not in gs_columns:
        await db.execute("ALTER TABLE game_scores ADD COLUMN game TEXT NOT NULL DEFAULT 'mille'")


async def get_db() -> aiosqlite.Connection:
    """Return the shared database connection, creating it on first call.

    Initialize the schema, enable WAL journal mode, and turn on foreign-key
    enforcement when opening a new connection.
    """
    global _db
    if _db is None:
        _db = await aiosqlite.connect(config.DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(SCHEMA)
        await _migrate(_db)
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.commit()
    return _db


async def close_db():
    """Close the shared database connection and reset the module-level handle."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None

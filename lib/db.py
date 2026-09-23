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
    last_dm_seen TIMESTAMP,
    invited_by INTEGER REFERENCES users(id)
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

-- Invitations (lib/invites.py). A code is single-use: used_at is set the
-- instant it is claimed, used_by once the account it produced exists.
CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    used_by INTEGER REFERENCES users(id),
    used_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dm_channel_seen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    channel TEXT NOT NULL,
    last_seen_at TIMESTAMP NOT NULL,
    UNIQUE(user_id, channel)
);

-- The Long Climb. A climber's attributes and any fight in progress are JSON
-- (lib/climb/store.py); `turn` rises with every action and is what makes a
-- stale or repeated form submission a no-op.
CREATE TABLE IF NOT EXISTS climb_players (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    turn INTEGER NOT NULL DEFAULT 0,
    climber TEXT NOT NULL,
    scene TEXT NOT NULL DEFAULT 'agora',
    fight TEXT,
    event TEXT,
    notice TEXT NOT NULL DEFAULT '[]',
    mail TEXT NOT NULL DEFAULT '[]',
    last_day TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- The Herald's news (user_id NULL for the town's own daily line) and the
-- tavern wall, the only player-written text in the game.
CREATE TABLE IF NOT EXISTS climb_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    line TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_climb_news_day ON climb_news(day);

CREATE TABLE IF NOT EXISTS climb_wall (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    line TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Who tried to rob whom, and when: one attempt per pair per day.
CREATE TABLE IF NOT EXISTS climb_robberies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    attacker_id INTEGER NOT NULL REFERENCES users(id),
    victim_id INTEGER NOT NULL REFERENCES users(id),
    UNIQUE(day, attacker_id, victim_id)
);

-- Courtship between climbers. One row per pair (low_id < high_id): how far it
-- has got, when each last flirted, and who, if anyone, has proposed. A door is
-- one climber silently refusing another's attention.
CREATE TABLE IF NOT EXISTS climb_hearts (
    low_id INTEGER NOT NULL REFERENCES users(id),
    high_id INTEGER NOT NULL REFERENCES users(id),
    affinity INTEGER NOT NULL DEFAULT 0,
    low_last TEXT,
    high_last TEXT,
    proposal_from INTEGER,
    PRIMARY KEY (low_id, high_id)
);
CREATE TABLE IF NOT EXISTS climb_doors (
    owner_id INTEGER NOT NULL REFERENCES users(id),
    shut_to_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (owner_id, shut_to_id)
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
    if "invited_by" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN invited_by INTEGER REFERENCES users(id)")

    cursor = await db.execute("PRAGMA table_info(game_scores)")
    gs_columns = {row[1] for row in await cursor.fetchall()}
    if "game" not in gs_columns:
        await db.execute("ALTER TABLE game_scores ADD COLUMN game TEXT NOT NULL DEFAULT 'mille'")

    # climb_players.event arrived after the table was first deployed.
    cursor = await db.execute("PRAGMA table_info(climb_players)")
    climb_columns = {row[1] for row in await cursor.fetchall()}
    if "event" not in climb_columns:
        await db.execute("ALTER TABLE climb_players ADD COLUMN event TEXT")
    if "mail" not in climb_columns:
        await db.execute("ALTER TABLE climb_players ADD COLUMN mail TEXT NOT NULL DEFAULT '[]'")

    # Session tokens are stored as SHA-256 hex digests. Rows written before
    # that hold the raw token, which can no longer match a lookup; drop them
    # so usable credentials do not sit in the table until they expire.
    await db.execute("DELETE FROM sessions WHERE length(token) != 64")
    # The DELETE opens a transaction, and journal_mode cannot be changed
    # inside one.
    await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Return the shared database connection, creating it on first call.

    Initialize the schema, enable WAL journal mode, and turn on foreign-key
    enforcement when opening a new connection.
    """
    global _db
    if _db is None:
        db = await aiosqlite.connect(config.DB_PATH)
        try:
            db.row_factory = aiosqlite.Row
            await db.executescript(SCHEMA)
            await _migrate(db)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.commit()
        except BaseException:
            # A half-initialized connection must not become the shared one,
            # and its worker thread would keep the process from exiting.
            await db.close()
            raise
        _db = db
    return _db


async def close_db():
    """Close the shared database connection and reset the module-level handle."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None

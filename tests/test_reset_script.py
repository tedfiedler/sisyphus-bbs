"""admin/reset_db.py: refuses to run under a live server, and clears uploads too."""

import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "admin" / "reset_db.py"


@pytest.fixture
def listening_port():
    """A port with something accepting connections on it, standing in for the BBS."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    yield server.getsockname()[1]
    server.close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed(tmp_path):
    """A database with one user in it and an uploaded file on disk."""
    db_path, store = tmp_path / "bbs.db", tmp_path / "files"
    (store / "general").mkdir(parents=True)
    (store / "general" / "upload.txt").write_text("data")
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    db.execute("INSERT INTO users (username) VALUES ('oldadmin')")
    db.commit()
    db.close()
    return db_path, store


def _run(db_path, store, port, *args):
    env = {**os.environ, "SISYPHUS_DB": str(db_path), "SISYPHUS_FILES": str(store),
           "SISYPHUS_WEB_PORT": str(port), "SISYPHUS_WEB_HOST": "127.0.0.1"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], env=env, cwd=tmp_cwd(db_path),
        capture_output=True, text=True, timeout=60,
    )


def tmp_cwd(db_path):
    # Run from outside the project so a developer's .env cannot leak in.
    return str(db_path.parent)


def _usernames(db_path):
    db = sqlite3.connect(db_path)
    try:
        return [row[0] for row in db.execute("SELECT username FROM users")]
    finally:
        db.close()


def test_refuses_while_the_server_is_running(tmp_path, listening_port):
    """Deleting the file under a live server changes nothing it can see: the old admin lives on."""
    db_path, store = _seed(tmp_path)

    result = _run(db_path, store, listening_port, "--yes")

    assert result.returncode == 1
    assert "Stop it first" in result.stdout
    assert _usernames(db_path) == ["oldadmin"]
    assert (store / "general" / "upload.txt").exists()


def test_resets_database_and_uploads_when_the_server_is_stopped(tmp_path):
    db_path, store = _seed(tmp_path)

    result = _run(db_path, store, _free_port(), "--yes")

    assert result.returncode == 0, result.stderr
    assert "Removed 1 uploaded file(s)" in result.stdout
    assert _usernames(db_path) == []
    assert list(store.rglob("*")) == []
    # The fresh database has the real schema, ready for the first signup.
    db = sqlite3.connect(db_path)
    columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    db.close()
    assert {"password_hash", "access_level"} <= columns


def test_force_overrides_the_running_check(tmp_path, listening_port):
    db_path, store = _seed(tmp_path)
    result = _run(db_path, store, listening_port, "--yes", "--force")
    assert result.returncode == 0, result.stderr
    assert _usernames(db_path) == []


def test_without_yes_it_asks_and_a_no_changes_nothing(tmp_path):
    db_path, store = _seed(tmp_path)
    env = {**os.environ, "SISYPHUS_DB": str(db_path), "SISYPHUS_FILES": str(store),
           "SISYPHUS_WEB_PORT": str(_free_port()), "SISYPHUS_WEB_HOST": "127.0.0.1"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, cwd=str(tmp_path),
        input="n\n", capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0 and "Aborted." in result.stdout
    assert _usernames(db_path) == ["oldadmin"]

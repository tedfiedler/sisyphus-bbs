"""admin/create_superadmin.py: makes the first account, and only the first."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "admin" / "create_superadmin.py"


def _run(db_path, *args, stdin=""):
    env = {**os.environ, "SISYPHUS_DB": str(db_path)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], env=env, cwd=str(db_path.parent),
        input=stdin, capture_output=True, text=True, timeout=60,
    )


def _accounts(db_path):
    db = sqlite3.connect(db_path)
    try:
        return list(db.execute("SELECT username, access_level FROM users"))
    finally:
        db.close()


def test_creates_the_superadmin_on_an_empty_database(tmp_path):
    db_path = tmp_path / "bbs.db"
    result = _run(db_path, "ted", "--password-stdin", stdin="password123\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Superadmin 'ted' created" in result.stdout
    assert _accounts(db_path) == [("ted", 2)]


def test_refuses_once_any_account_exists(tmp_path):
    db_path = tmp_path / "bbs.db"
    _run(db_path, "ted", "--password-stdin", stdin="password123\n")

    again = _run(db_path, "other", "--password-stdin", stdin="password123\n")
    assert again.returncode == 2 and "already has accounts" in again.stdout

    quiet = _run(db_path, "other", "--if-empty", "--password-stdin", stdin="password123\n")
    assert quiet.returncode == 0 and "nothing to do" in quiet.stdout
    assert _accounts(db_path) == [("ted", 2)]


def test_rejects_a_bad_password_or_name_before_touching_the_database(tmp_path):
    db_path = tmp_path / "bbs.db"
    short = _run(db_path, "ted", "--password-stdin", stdin="short\n")
    assert short.returncode == 1 and "at least 8 characters" in short.stdout
    bad_name = _run(db_path, "-ted", "--password-stdin", stdin="password123\n")
    assert bad_name.returncode == 1 and "Username must" in bad_name.stdout
    assert _run(db_path).returncode == 2
    assert not db_path.exists()

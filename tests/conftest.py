import os
import sys
import tempfile

import pytest
import pytest_asyncio

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use a temp database for tests
os.environ["SISYPHUS_DB"] = os.path.join(tempfile.gettempdir(), "sisyphus_test.db")


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Rate limiters are module-level, so clear them between tests."""
    from lib.routes import auth_routes

    for limiter in (auth_routes._login_limiter, auth_routes._register_limiter):
        limiter._events.clear()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    """Reset database before each test."""
    from lib import config
    from lib import db

    # Close any existing connection
    await db.close_db()

    # Remove old test db
    if os.path.exists(config.DB_PATH):
        os.unlink(config.DB_PATH)

    # Initialize fresh
    await db.get_db()
    yield
    await db.close_db()
    if os.path.exists(config.DB_PATH):
        os.unlink(config.DB_PATH)

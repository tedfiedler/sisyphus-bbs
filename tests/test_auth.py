import pytest

import auth


@pytest.mark.asyncio
async def test_register_user():
    result = await auth.register_user("testuser", "password123")
    assert result is not None
    assert result["username"] == "testuser"


@pytest.mark.asyncio
async def test_register_duplicate():
    await auth.register_user("testuser", "password123")
    result = await auth.register_user("testuser", "other")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_success():
    await auth.register_user("testuser", "password123")
    user = await auth.authenticate("testuser", "password123")
    assert user is not None
    assert user["username"] == "testuser"


@pytest.mark.asyncio
async def test_authenticate_wrong_password():
    await auth.register_user("testuser", "password123")
    user = await auth.authenticate("testuser", "wrongpassword")
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_nonexistent():
    user = await auth.authenticate("nobody", "password123")
    assert user is None


@pytest.mark.asyncio
async def test_session_flow():
    await auth.register_user("testuser", "password123")
    user = await auth.authenticate("testuser", "password123")
    token = await auth.create_session(user["id"])
    assert token is not None

    found = await auth.get_user_by_token(token)
    assert found is not None
    assert found["username"] == "testuser"

    await auth.delete_session(token)
    found = await auth.get_user_by_token(token)
    assert found is None


@pytest.mark.asyncio
async def test_password_hashing():
    pw_hash = auth.hash_password("mypassword")
    assert auth.verify_password("mypassword", pw_hash)
    assert not auth.verify_password("wrongpassword", pw_hash)

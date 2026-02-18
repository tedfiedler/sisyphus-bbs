"""Dependency functions for FastAPI route injection of user authentication."""

from fastapi import Request, HTTPException

from lib import auth


async def get_current_user(request: Request) -> dict | None:
    """Extract and return the current user from the session cookie, or None if unauthenticated."""
    token = request.cookies.get("session_token")
    if not token:
        return None
    return await auth.get_user_by_token(token)


async def require_user(request: Request) -> dict:
    """Require an authenticated user or redirect to the home page with a 302."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/"})
    await auth.update_last_seen(user["id"])
    return user


async def require_admin(request: Request) -> dict:
    """Require an authenticated admin user or raise a 403 Forbidden error."""
    user = await require_user(request)
    if not auth.is_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


async def require_file_access(request: Request) -> dict:
    """Require an authenticated user who meets all file access criteria, or raise 403."""
    user = await require_user(request)
    file_access = await auth.check_file_access(user)
    if not file_access["allowed"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

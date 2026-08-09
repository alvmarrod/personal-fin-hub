from collections.abc import AsyncGenerator
from contextvars import Token

from fastapi import Header, HTTPException, status

from db import queries
from db.connection import get_db, reset_active_profile, set_active_profile


async def require_profile(
    x_profile_id: int | None = Header(default=None, alias="X-Profile-ID"),
) -> AsyncGenerator[int]:
    """Require an authenticated profile for the current request.

    Rejects requests without the ``X-Profile-ID`` header (401) or with a
    header naming a nonexistent profile (404). On success, scopes every
    connection opened during the request to that profile via a contextvar.
    """
    if x_profile_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Profile-ID header")

    conn = get_db()
    try:
        profile = queries.get_profile(conn, x_profile_id)
    finally:
        conn.close()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Profile {x_profile_id} not found")

    token: Token = set_active_profile(x_profile_id)
    try:
        yield x_profile_id
    finally:
        reset_active_profile(token)

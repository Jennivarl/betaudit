"""Auth dependencies: API-key gate for callers, admin gate for key issuance.

Callers authenticate with ``X-API-Key: rl_live_...``. The verified ApiKey is
attached to ``request.state.api_key`` so the endpoint can meter + audit it.

Admin routes (minting keys) require ``Authorization: Bearer <admin_token>``.
When ``admin_token`` is empty (local dev) the admin gate is open, so the
service is usable out of the box; production MUST set it.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import ApiKey
from app.services import keys as key_service


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    api_key = await key_service.verify_key(session, x_api_key)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    request.state.api_key = api_key
    return api_key


async def require_admin(
    authorization: str | None = Header(default=None),
) -> None:
    admin_token = get_settings().admin_token
    if not admin_token:
        return  # dev: admin routes open when no token configured
    expected = f"Bearer {admin_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required.",
        )

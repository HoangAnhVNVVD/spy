"""Authentication & security dependencies."""

from __future__ import annotations

from typing import Optional
from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.config import settings

security_bearer = HTTPBearer(auto_error=False)


def verify_token_string(token: Optional[str]) -> bool:
    """Compare provided token against configured secret."""
    if not token or not settings.API_KEY:
        return False
    return token.strip() == settings.API_KEY.strip()


def require_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    token_query: Optional[str] = Query(None, alias="token"),
) -> str:
    """
    Enforce valid Bearer token or token query parameter.
    Raises HTTP 401 Unauthorized if invalid.
    """
    token_candidate = None
    if credentials:
        token_candidate = credentials.credentials
    elif token_query:
        token_candidate = token_query

    if not verify_token_string(token_candidate):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_candidate or ""


def optional_auth_for_reads(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    token_query: Optional[str] = Query(None, alias="token"),
) -> None:
    """
    Check authorization only if REQUIRE_AUTH_FOR_READS is enabled in settings.
    Otherwise allows open read-only access to dashboard and query APIs.
    """
    if settings.REQUIRE_AUTH_FOR_READS:
        require_api_key(credentials, token_query)

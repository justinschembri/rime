"""Bearer token authentication for rime-server-http.

Two token roles per ``app_id``:

- **ingress** — edge producers calling ``POST /v1/apps/{app_id}/messages``
- **egress**  — rime-ingest calling ``GET`` and ``ACK`` endpoints

Tokens are compared with :func:`hmac.compare_digest` to avoid timing attacks.
"""

from __future__ import annotations

import hmac
from typing import Literal

from fastapi import HTTPException, Request, status

from .config import ServerConfig

TokenRole = Literal["ingress", "egress"]


def _extract_bearer(request: Request) -> str:
    """Pull the raw token from a ``Request``'s Authorization header."""
    return _parse_bearer(request.headers.get("Authorization", ""))


def _parse_bearer(header: str | None) -> str:
    """Parse ``Bearer <token>`` from a raw header string."""
    if not header or not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return header.removeprefix("Bearer ").strip()


def _check_credentials(
    token: str,
    app_id: str,
    role: TokenRole,
    config: ServerConfig,
) -> None:
    """Raise ``401`` or ``403`` if *token* does not match the expected credential."""
    app_creds = config.apps.get(app_id)
    if app_creds is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown app_id: {app_id!r}",
        )
    expected = (
        app_creds.ingress_token if role == "ingress" else app_creds.egress_token
    )
    if not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_token(
    request: Request,
    app_id: str,
    role: TokenRole,
    config: ServerConfig,
) -> None:
    """Auth check for handlers that receive a full ``Request`` object."""
    _check_credentials(_extract_bearer(request), app_id, role, config)


def check_bearer(
    authorization: str | None,
    app_id: str,
    role: TokenRole,
    config: ServerConfig,
) -> None:
    """Auth check for handlers that receive the ``Authorization`` header directly."""
    _check_credentials(_parse_bearer(authorization), app_id, role, config)

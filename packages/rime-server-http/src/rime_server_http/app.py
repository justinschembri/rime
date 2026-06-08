"""FastAPI application for rime-server-http.

Routes
------
GET  /health
    Liveness probe. No auth.

POST /v1/apps/{app_id}/messages
    Edge ingress. Requires ingress Bearer token.
    Body: opaque bytes (wire payload).
    Returns 202 on success, 413 if body too large, 429 if queue full.

GET  /v1/apps/{app_id}/messages?limit=N
    Ingest drain. Requires egress Bearer token.
    Returns up to N messages in JSON. Messages move to in-flight until acked.

POST /v1/apps/{app_id}/messages/ack
    Ingest commit. Requires egress Bearer token.
    Body: {"ids": ["server-uuid", ...]}
    Returns 204. Unknown ids are reported but do not cause failure.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .auth import check_bearer, require_token
from .buffer import MessageBuffer, StoredMessage
from .config import ServerConfig

_bearer = HTTPBearer(auto_error=False)

logger = logging.getLogger("rime-server-http")


# Pydantic models defined at module level so FastAPI can resolve them
# reliably regardless of where routes are registered.

class _DrainedMessage(BaseModel):
    id: str
    message_id: str | None
    received_at: datetime
    emitted_at: datetime | None
    content_type: str
    body: str   # base64-encoded


class _DrainResponse(BaseModel):
    messages: list[_DrainedMessage]


class _AckRequest(BaseModel):
    ids: list[str]


def create_app(config: ServerConfig, buffer: MessageBuffer) -> FastAPI:
    """Construct and return the FastAPI application.

    ``config`` and ``buffer`` are injected rather than module-global so the
    app is straightforward to test without monkeypatching.
    """
    app = FastAPI(
        title="rime-server-http",
        description="Edge ingress buffer for rime-ingest.",
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Ingress — edge → server
    # ------------------------------------------------------------------

    @app.post(
        "/v1/apps/{app_id}/messages",
        status_code=status.HTTP_202_ACCEPTED,
        summary="Accept a wire payload from an edge producer.",
    )
    async def post_message(
        app_id: str,
        request: Request,
        x_rime_message_id: Annotated[str | None, Header()] = None,
        x_rime_emitted_at: Annotated[str | None, Header()] = None,
    ) -> Response:
        require_token(request, app_id, "ingress", config)

        body = await request.body()
        if not body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body must not be empty.",
            )
        if len(body) > config.limits.max_body_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    f"Payload size {len(body)} bytes exceeds limit "
                    f"{config.limits.max_body_bytes} bytes."
                ),
            )

        emitted_at: datetime | None = None
        if x_rime_emitted_at:
            try:
                emitted_at = datetime.fromisoformat(x_rime_emitted_at)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid X-Rime-Emitted-At value: {x_rime_emitted_at!r}",
                )

        msg = StoredMessage(
            app_id=app_id,
            message_id=x_rime_message_id or None,
            emitted_at=emitted_at,
            content_type=request.headers.get(
                "Content-Type", "application/octet-stream"
            ),
            body=body,
        )

        buf = buffer.get_or_create(app_id)
        if not buf.enqueue(msg):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Queue for app_id {app_id!r} is full "
                    f"({config.limits.max_queue_depth_per_app} messages). "
                    "Retry after ingest drains the buffer."
                ),
                headers={"Retry-After": "30"},
            )

        logger.info(
            "Accepted message app_id=%s server_id=%s size=%d",
            app_id,
            msg.id,
            len(body),
        )
        return Response(status_code=status.HTTP_202_ACCEPTED)

    # ------------------------------------------------------------------
    # Drain — ingest polls
    # ------------------------------------------------------------------

    @app.get(
        "/v1/apps/{app_id}/messages",
        response_model=_DrainResponse,
        summary="Drain pending messages for an app (ingest poll).",
    )
    async def get_messages(
        app_id: str,
        request: Request,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ) -> _DrainResponse:
        require_token(request, app_id, "egress", config)

        buf = buffer.get_or_create(app_id)
        batch = buf.drain(limit)

        return _DrainResponse(
            messages=[
                _DrainedMessage(
                    id=m.id,
                    message_id=m.message_id,
                    received_at=m.received_at,
                    emitted_at=m.emitted_at,
                    content_type=m.content_type,
                    body=base64.b64encode(m.body).decode(),
                )
                for m in batch
            ]
        )

    # ------------------------------------------------------------------
    # Ack — ingest commits
    # ------------------------------------------------------------------

    @app.post(
        "/v1/apps/{app_id}/messages/ack",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Acknowledge processed messages (ingest commit).",
    )
    async def ack_messages(
        app_id: str,
        ack_body: _AckRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        check_bearer(authorization, app_id, "egress", config)

        buf = buffer.get_or_create(app_id)
        unknown = buf.ack(ack_body.ids)

        if unknown:
            logger.warning(
                "ACK for unknown ids app_id=%s ids=%s", app_id, unknown
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------
    # Buffer stats (ops convenience, no auth for now)
    # ------------------------------------------------------------------

    @app.get("/v1/stats", include_in_schema=False)
    async def stats() -> dict:
        return buffer.stats()

    return app

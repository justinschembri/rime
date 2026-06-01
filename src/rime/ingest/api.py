"""FastAPI application exposing transport lifecycle endpoints.

Endpoints
---------
GET  /health
GET  /transports
GET  /transports/{app_name}
POST /transports/{app_name}/start
POST /transports/{app_name}/stop
POST /transports/{app_name}/restart
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel

from rime.ingest.runtime import IngestRuntime, RuntimeStatus, TransportStatus

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class TransportStartRequest(BaseModel):
    """Config entry for a single application (value under applications.<name>)."""
    config: dict[str, Any]


class TransportRestartRequest(BaseModel):
    """Updated config entry for an existing application."""
    config: dict[str, Any]


class TransportStatusResponse(BaseModel):
    app_name: str
    is_alive: bool
    push_success: int
    push_fail: int


class RuntimeStatusResponse(BaseModel):
    transports: list[TransportStatusResponse]
    uptime_seconds: float
    expected_sensors: list[str]


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# App factory — takes a runtime instance so tests can inject a mock
# ---------------------------------------------------------------------------

def create_app(runtime: IngestRuntime) -> FastAPI:
    """Build and return the FastAPI application.

    Args:
        runtime: The IngestRuntime instance this app controls.  Tests pass a
            fresh IngestRuntime (or a mock); production passes the singleton.
    """
    app = FastAPI(
        title="rime-ingest",
        description="Transport lifecycle API for the rime ingest service.",
        version="0.1.0",
    )

    # Dependency — makes the runtime available to all route handlers
    def get_runtime() -> IngestRuntime:
        return runtime

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health", response_model=MessageResponse, tags=["health"])
    def health() -> MessageResponse:
        """Basic liveness probe."""
        return MessageResponse(message="ok")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @app.get(
        "/transports",
        response_model=RuntimeStatusResponse,
        tags=["transports"],
    )
    def list_transports(rt: IngestRuntime = Depends(get_runtime)) -> RuntimeStatusResponse:
        """Return status of all known transports."""
        status_snapshot = rt.get_status()
        return RuntimeStatusResponse(
            transports=[
                TransportStatusResponse(
                    app_name=t.app_name,
                    is_alive=t.is_alive,
                    push_success=t.push_success,
                    push_fail=t.push_fail,
                )
                for t in status_snapshot.transports
            ],
            uptime_seconds=status_snapshot.uptime_seconds,
            expected_sensors=status_snapshot.expected_sensors,
        )

    @app.get(
        "/transports/{app_name}",
        response_model=TransportStatusResponse,
        tags=["transports"],
    )
    def get_transport(
        app_name: str,
        rt: IngestRuntime = Depends(get_runtime),
    ) -> TransportStatusResponse:
        """Return status of a single transport."""
        snapshot = rt.get_status()
        match = next(
            (t for t in snapshot.transports if t.app_name == app_name), None
        )
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transport '{app_name}' not found.",
            )
        return TransportStatusResponse(
            app_name=match.app_name,
            is_alive=match.is_alive,
            push_success=match.push_success,
            push_fail=match.push_fail,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @app.post(
        "/transports/{app_name}/start",
        response_model=MessageResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["transports"],
    )
    def start_transport(
        app_name: str,
        body: TransportStartRequest,
        rt: IngestRuntime = Depends(get_runtime),
    ) -> MessageResponse:
        """Start a new transport thread for the given application."""
        try:
            rt.start_transport(app_name, body.config)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            )
        return MessageResponse(message=f"Transport '{app_name}' started.")

    @app.post(
        "/transports/{app_name}/stop",
        response_model=MessageResponse,
        tags=["transports"],
    )
    def stop_transport(
        app_name: str,
        rt: IngestRuntime = Depends(get_runtime),
    ) -> MessageResponse:
        """Stop a running transport thread."""
        try:
            rt.stop_transport(app_name)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            )
        return MessageResponse(message=f"Transport '{app_name}' stopped.")

    @app.post(
        "/transports/{app_name}/restart",
        response_model=MessageResponse,
        tags=["transports"],
    )
    def restart_transport(
        app_name: str,
        body: TransportRestartRequest,
        rt: IngestRuntime = Depends(get_runtime),
    ) -> MessageResponse:
        """Stop and restart a transport with updated config."""
        try:
            rt.restart_transport(app_name, body.config)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            )
        return MessageResponse(message=f"Transport '{app_name}' restarted.")

    return app

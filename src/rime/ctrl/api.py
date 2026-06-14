"""FastAPI application for the rime-ctrl service.

Endpoints
---------
GET  /health                     — liveness check
POST /reconcile                  — trigger a reconcile cycle on demand
GET  /sensors                    — list sensor YAML files in the ops volume
DELETE /sensors/{name}           — remove a sensor YAML file
GET|POST|DELETE|PATCH
     /frost/{path}               — reverse-proxy to the internal FROST endpoint
GET  /status                     — FROST reachability + ingest transport summary
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import httpx
import requests as _requests
from fastapi import FastAPI, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from rime.config import get_frost_auth_header
from rime.ctrl.reconciler import IngestClient, reconcile

logger = logging.getLogger("ctrl.api")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str


class ReconcileResponse(BaseModel):
    started: list[str]
    stopped: list[str]
    restarted: list[str]
    unchanged: list[str]


class SensorInfo(BaseModel):
    name: str
    filename: str


class SensorsResponse(BaseModel):
    sensors: list[SensorInfo]


class SensorModelsResponse(BaseModel):
    models: list[str]


class CreateSensorRequest(BaseModel):
    sensor_model: str
    sensor_id: str
    thing_name: str
    thing_description: str
    location_name: str
    location_description: str
    longitude: float
    latitude: float


class StatusResponse(BaseModel):
    frost_reachable: bool
    ingest_reachable: bool
    transports: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    ingest_client: IngestClient,
    sensor_config_dir: Path,
    app_config_path: Path,
    frost_endpoint: str = "http://web:8080/FROST-Server/v1.1",
) -> FastAPI:
    """Create and return the rime-ctrl FastAPI application.

    Args:
        ingest_client:      Pre-configured client for the rime-ingest API.
        sensor_config_dir:  Path to the sensor_configs directory (ops volume).
        app_config_path:    Path to application-configs.yml (ops volume).
        frost_endpoint:     Internal FROST base URL (default: Docker service name).
    """
    app = FastAPI(
        title="rime-ctrl",
        description="Control plane for the rime ingestion pipeline.",
        version="0.1.0",
    )

    # One lock prevents concurrent reconcile cycles (from API calls *and* the
    # git-watch background thread sharing the same IngestClient).
    _reconcile_lock = threading.Lock()

    _templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scan_sensor_files() -> list[Path]:
        """Return all non-template sensor YAML files under sensor_config_dir."""
        paths = [
            p
            for ext in ("*.yml", "*.yaml", "*.YML", "*.YAML")
            for p in sensor_config_dir.rglob(ext)
            if "template" not in p.stem
        ]
        return list({p for p in paths})

    def _list_sensor_models() -> list[str]:
        templates = (
            list(sensor_config_dir.rglob("template_*.yml")) +
            list(sensor_config_dir.rglob("template_*.yaml"))
        )
        return sorted({p.stem.removeprefix("template_") for p in templates})

    def _get_status_data() -> tuple[bool, bool, list[dict[str, Any]]]:
        """Fetch FROST and ingest status — shared by JSON and HTML routes."""
        frost_reachable = False
        try:
            r = _requests.get(
                frost_endpoint,
                timeout=5,
                headers={"Authorization": f"Basic {_frost_auth}"} if _frost_auth else {},
            )
            frost_reachable = r.status_code < 500
        except Exception:
            pass

        ingest_reachable = False
        transports: list[dict[str, Any]] = []
        try:
            r = _requests.get(f"{ingest_client.base_url}/transports", timeout=5)
            r.raise_for_status()
            ingest_reachable = True
            transports = r.json().get("transports", [])
        except Exception:
            pass

        return frost_reachable, ingest_reachable, transports

    # ------------------------------------------------------------------
    # GET /health
    # ------------------------------------------------------------------

    @app.get("/health", response_model=MessageResponse, tags=["system"])
    def health() -> MessageResponse:
        return MessageResponse(message="ok")

    # ------------------------------------------------------------------
    # POST /reconcile
    # ------------------------------------------------------------------

    @app.post(
        "/reconcile",
        response_model=ReconcileResponse,
        status_code=status.HTTP_200_OK,
        tags=["ctrl"],
    )
    def trigger_reconcile() -> ReconcileResponse:
        """Run a reconcile cycle: provision FROST, sync ingest transports.

        Returns 409 if a reconcile is already in progress.
        """
        if not _reconcile_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A reconcile cycle is already in progress.",
            )
        try:
            sensor_paths = _scan_sensor_files()
            diff = reconcile(
                app_config_path=app_config_path,
                sensor_config_paths=sensor_paths,
                ingest_client=ingest_client,
                sensor_config_dir=sensor_config_dir,
            )
            logger.info(
                "Reconcile via API complete: started=%s stopped=%s restarted=%s unchanged=%s",
                list(diff.to_start), diff.to_stop, list(diff.to_restart), diff.unchanged,
            )
            return ReconcileResponse(
                started=list(diff.to_start),
                stopped=diff.to_stop,
                restarted=list(diff.to_restart),
                unchanged=diff.unchanged,
            )
        finally:
            _reconcile_lock.release()

    # ------------------------------------------------------------------
    # GET /sensors
    # ------------------------------------------------------------------

    @app.get("/sensors", response_model=SensorsResponse, tags=["sensors"])
    def list_sensors() -> SensorsResponse:
        """List all sensor YAML configuration files in the ops volume."""
        paths = sorted(_scan_sensor_files(), key=lambda p: p.name)
        return SensorsResponse(
            sensors=[SensorInfo(name=p.stem, filename=p.name) for p in paths]
        )

    # ------------------------------------------------------------------
    # GET /sensors/models
    # ------------------------------------------------------------------

    @app.get("/sensors/models", response_model=SensorModelsResponse, tags=["sensors"])
    def list_sensor_models() -> SensorModelsResponse:
        """List sensor models for which a template exists in the ops volume."""
        return SensorModelsResponse(models=_list_sensor_models())

    # ------------------------------------------------------------------
    # POST /sensors
    # ------------------------------------------------------------------

    @app.post("/sensors", response_model=MessageResponse, status_code=status.HTTP_201_CREATED, tags=["sensors"])
    def create_sensor(body: CreateSensorRequest) -> MessageResponse:
        """Generate a sensor YAML config from a template and write it to the ops volume.

        The sensor_id becomes the filename (``<sensor_id>.yml``).  Returns 404
        if no template exists for the requested model and 409 if a config with
        that sensor_id already exists.
        """
        import yaml
        from rime.cli.config_generator import _replace_placeholders

        # Locate the template inside the sensor_config_dir
        candidates = (
            list(sensor_config_dir.rglob(f"template_{body.sensor_model}.yaml")) +
            list(sensor_config_dir.rglob(f"template_{body.sensor_model}.yml"))
        )
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No template found for sensor model '{body.sensor_model}'.",
            )

        output_path = sensor_config_dir / f"{body.sensor_id}.yml"
        if output_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sensor config '{body.sensor_id}' already exists.",
            )

        with open(candidates[0]) as f:
            template = yaml.safe_load(f)

        config = _replace_placeholders(
            template,
            body.sensor_id,
            body.thing_name,
            body.thing_description,
            body.location_name,
            body.location_description,
            body.longitude,
            body.latitude,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        logger.info("Created sensor config: %s", output_path)
        return MessageResponse(message=f"Sensor config '{body.sensor_id}' created.")

    # ------------------------------------------------------------------
    # DELETE /sensors/{name}
    # ------------------------------------------------------------------

    @app.delete(
        "/sensors/{name}",
        response_model=MessageResponse,
        tags=["sensors"],
    )
    def delete_sensor(name: str) -> MessageResponse:
        """Delete a sensor YAML configuration file.

        Searches for ``<name>.yml`` or ``<name>.yaml`` under the sensor config
        directory. The corresponding FROST Thing must be deleted separately via
        the ``/frost`` proxy endpoint to avoid ingest recreating it on the next
        reconcile.
        """
        candidates = list(sensor_config_dir.rglob(f"{name}.yml")) + \
                     list(sensor_config_dir.rglob(f"{name}.yaml"))
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sensor config '{name}' not found.",
            )
        target = candidates[0]
        target.unlink()
        logger.info("Deleted sensor config: %s", target)
        return MessageResponse(message=f"Sensor config '{name}' deleted.")

    # ------------------------------------------------------------------
    # /frost/{path} — reverse proxy
    # ------------------------------------------------------------------

    try:
        _frost_auth = get_frost_auth_header()
    except Exception:
        _frost_auth = None

    @app.api_route(
        "/frost/{path:path}",
        methods=["GET", "POST", "DELETE", "PATCH"],
        tags=["frost"],
    )
    async def frost_proxy(path: str, request: Request) -> Response:
        """Reverse-proxy requests to the internal FROST Server.

        FROST is not exposed outside the Docker network; this endpoint makes it
        reachable from the rime-ctrl web UI (and the browser).
        """
        url = f"{frost_endpoint}/{path}"
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        if _frost_auth:
            headers["Authorization"] = f"Basic {_frost_auth}"

        async with httpx.AsyncClient() as client:
            try:
                proxy_resp = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=await request.body(),
                    params=dict(request.query_params),
                    timeout=30.0,
                )
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"FROST request failed: {exc}",
                )

        return Response(
            content=proxy_resp.content,
            status_code=proxy_resp.status_code,
            media_type=proxy_resp.headers.get("content-type"),
        )

    # ------------------------------------------------------------------
    # GET /status
    # ------------------------------------------------------------------

    @app.get("/status", response_model=StatusResponse, tags=["system"])
    def get_status() -> StatusResponse:
        """Return FROST reachability and ingest transport health summary."""
        frost_reachable, ingest_reachable, transports = _get_status_data()
        return StatusResponse(
            frost_reachable=frost_reachable,
            ingest_reachable=ingest_reachable,
            transports=transports,
        )

    # ------------------------------------------------------------------
    # Web UI routes
    # All routes under / and /ui/* serve Jinja2 HTML pages for browsers.
    # The JSON API routes above are kept unchanged for programmatic use.
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(request, "dashboard.html")

    @app.get("/ui/status", response_class=HTMLResponse, include_in_schema=False)
    def status_partial(request: Request) -> HTMLResponse:
        frost_reachable, ingest_reachable, transports = _get_status_data()
        return _templates.TemplateResponse(request, "partials/status.html", {
            "frost_reachable": frost_reachable,
            "ingest_reachable": ingest_reachable,
            "transports": transports,
        })

    @app.post("/ui/reconcile", response_class=HTMLResponse, include_in_schema=False)
    def reconcile_htmx(request: Request) -> HTMLResponse:
        if not _reconcile_lock.acquire(blocking=False):
            return _templates.TemplateResponse(
                request, "partials/reconcile_result.html",
                {"error": "A reconcile is already in progress. Try again in a moment."},
            )
        try:
            diff = reconcile(
                app_config_path=app_config_path,
                sensor_config_paths=_scan_sensor_files(),
                ingest_client=ingest_client,
                sensor_config_dir=sensor_config_dir,
            )
            logger.info(
                "Reconcile via web UI complete: started=%s stopped=%s restarted=%s unchanged=%s",
                list(diff.to_start), diff.to_stop, list(diff.to_restart), diff.unchanged,
            )
            return _templates.TemplateResponse(request, "partials/reconcile_result.html", {
                "started": list(diff.to_start),
                "stopped": diff.to_stop,
                "restarted": list(diff.to_restart),
                "unchanged": diff.unchanged,
                "error": None,
            })
        except Exception as exc:
            logger.error("Reconcile failed: %s", exc)
            return _templates.TemplateResponse(
                request, "partials/reconcile_result.html", {"error": str(exc)},
            )
        finally:
            _reconcile_lock.release()

    @app.get("/ui/sensors", response_class=HTMLResponse, include_in_schema=False)
    def sensors_page(request: Request, created: str = "") -> HTMLResponse:
        paths = sorted(_scan_sensor_files(), key=lambda p: p.name)
        return _templates.TemplateResponse(request, "sensors.html", {
            "sensors": [{"name": p.stem, "filename": p.name} for p in paths],
            "created": bool(created),
        })

    @app.get("/ui/sensors/new", response_class=HTMLResponse, include_in_schema=False)
    def sensor_new_page(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(request, "sensor_new.html", {
            "models": _list_sensor_models(),
            "error": None,
            "form": {},
        })

    @app.post("/ui/sensors", response_class=HTMLResponse, include_in_schema=False)
    def create_sensor_form(
        request: Request,
        sensor_model: str = Form(...),
        sensor_id: str = Form(...),
        thing_name: str = Form(...),
        thing_description: str = Form(...),
        location_name: str = Form(...),
        location_description: str = Form(...),
        latitude: float = Form(...),
        longitude: float = Form(...),
    ) -> HTMLResponse:
        import yaml
        from rime.cli.config_generator import _replace_placeholders

        form_data = {
            "sensor_model": sensor_model,
            "sensor_id": sensor_id,
            "thing_name": thing_name,
            "thing_description": thing_description,
            "location_name": location_name,
            "location_description": location_description,
            "latitude": latitude,
            "longitude": longitude,
        }

        def _render_error(msg: str, code: int = 400) -> HTMLResponse:
            return _templates.TemplateResponse(
                request, "sensor_new.html",
                {"models": _list_sensor_models(), "error": msg, "form": form_data},
                status_code=code,
            )

        candidates = (
            list(sensor_config_dir.rglob(f"template_{sensor_model}.yaml")) +
            list(sensor_config_dir.rglob(f"template_{sensor_model}.yml"))
        )
        if not candidates:
            return _render_error(f"No template found for model '{sensor_model}'.", 404)

        output_path = sensor_config_dir / f"{sensor_id}.yml"
        if output_path.exists():
            return _render_error(f"Sensor '{sensor_id}' already exists.", 409)

        with open(candidates[0]) as f:
            template = yaml.safe_load(f)

        config = _replace_placeholders(
            template,
            sensor_id, thing_name, thing_description,
            location_name, location_description,
            longitude, latitude,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        logger.info("Created sensor config via web UI: %s", output_path)
        return RedirectResponse(url="/ui/sensors?created=1", status_code=303)

    @app.delete("/ui/sensors/{name}", response_class=HTMLResponse, include_in_schema=False)
    def delete_sensor_htmx(name: str) -> Response:
        candidates = (
            list(sensor_config_dir.rglob(f"{name}.yml")) +
            list(sensor_config_dir.rglob(f"{name}.yaml"))
        )
        if not candidates:
            raise HTTPException(status_code=404, detail=f"Sensor '{name}' not found.")
        candidates[0].unlink()
        logger.info("Deleted sensor config via web UI: %s", candidates[0])
        return Response(content="", status_code=200)

    return app

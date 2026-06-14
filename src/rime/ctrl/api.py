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
GET  /applications               — list provider applications from YAML
POST /applications               — add a new provider application
DELETE /applications/{name}      — remove a provider application
PATCH /applications/{name}       — update a provider application config
PUT  /credentials/{app_name}     — upsert application API key
DELETE /credentials/{app_name}   — remove application API key
GET  /tokens                     — list OAuth token files
PUT  /tokens/{app_name}          — write/replace a token file
DELETE /tokens/{app_name}        — delete a token file
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
import requests as _requests
from fastapi import FastAPI, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
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


class NetatmoAppConfig(BaseModel):
    provider: Literal["netatmo"] = "netatmo"
    request_interval: int = 300
    max_retries: int = 10
    expected_sensors: int | None = None


class TTSAppConfig(BaseModel):
    provider: Literal["tts"] = "tts"
    host: str
    port: int = 8883
    topic: str
    max_retries: int = 5
    expected_sensors: int | None = None


class ApplicationInfo(BaseModel):
    name: str
    provider: str
    config: dict[str, Any]
    has_credentials: bool
    has_token: bool


class ApplicationsResponse(BaseModel):
    applications: list[ApplicationInfo]


class CreateApplicationRequest(BaseModel):
    name: str
    config: NetatmoAppConfig | TTSAppConfig = Field(discriminator="provider")


class TokenInfo(BaseModel):
    name: str
    keys: list[str]


class TokensResponse(BaseModel):
    tokens: list[TokenInfo]


class LogsResponse(BaseModel):
    lines: list[str]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

_STALE_HOURS = 1


def _staleness_label(last_obs: str | None) -> tuple[str, str]:
    """Return (badge_css_class, human_label) for a datastream's last observation."""
    if not last_obs:
        return "badge-muted", "no data"
    dt = datetime.fromisoformat(last_obs.replace("Z", "+00:00"))
    age = datetime.now(tz=timezone.utc) - dt
    hours = age.total_seconds() / 3600
    mins = int(age.total_seconds() / 60)
    if hours < _STALE_HOURS:
        return "badge-ok", (f"{mins}m ago" if mins > 0 else "just now")
    elif hours < 24:
        return "badge-error", f"{int(hours)}h ago"
    else:
        return "badge-error", f"{int(hours / 24)}d ago"


def create_app(
    ingest_client: IngestClient,
    sensor_config_dir: Path,
    app_config_path: Path,
    frost_endpoint: str = "http://web:8080/FROST-Server/v1.1",
    credentials_path: Path | None = None,
    tokens_dir: Path | None = None,
    logs_dir: Path | None = None,
) -> FastAPI:
    """Create and return the rime-ctrl FastAPI application.

    Args:
        ingest_client:      Pre-configured client for the rime-ingest API.
        sensor_config_dir:  Path to the sensor_configs directory (ops volume).
        app_config_path:    Path to application-configs.yml (ops volume).
        frost_endpoint:     Internal FROST base URL (default: Docker service name).
        credentials_path:   Path to application_credentials.json.
                            Defaults to CREDENTIALS_DIR/application_credentials.json
                            from rime.paths.
        tokens_dir:         Directory containing OAuth token JSON files.
                            Defaults to TOKENS_DIR from rime.paths.
    """
    if credentials_path is None:
        from rime.paths import CREDENTIALS_DIR
        credentials_path = CREDENTIALS_DIR / "application_credentials.json"
    if tokens_dir is None:
        from rime.paths import TOKENS_DIR as _TOKENS_DIR
        tokens_dir = _TOKENS_DIR
    if logs_dir is None:
        from rime.paths import LOGS_DIR
        logs_dir = LOGS_DIR
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

    def _load_app_config_raw() -> dict[str, Any]:
        import yaml
        with open(app_config_path) as f:
            return yaml.safe_load(f) or {}

    def _write_app_config(raw: dict[str, Any]) -> None:
        import shutil
        import yaml
        # Write to /tmp (not the bind-mounted /ops dir which may be :ro for directory ops),
        # then move to target. shutil.move falls back to copy+delete on cross-device moves.
        tmp = Path(tempfile.mktemp(prefix=".app-config-", suffix=".tmp"))
        try:
            with open(tmp, "w") as f:
                yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False, indent=2)
            shutil.move(str(tmp), app_config_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _load_credentials() -> dict[str, Any]:
        if credentials_path.exists():
            with open(credentials_path) as f:
                return json.load(f)
        return {}

    def _write_credentials(creds: dict[str, Any]) -> None:
        credentials_path.parent.mkdir(parents=True, exist_ok=True)
        with open(credentials_path, "w") as f:
            json.dump(creds, f, indent=4)

    def _tail_log(n: int = 100) -> list[str]:
        log_path = logs_dir / "general.log"
        if not log_path.exists():
            return []
        with open(log_path) as f:
            return f.readlines()[-n:]

    def _classify_line(line: str) -> str:
        if ": ERROR" in line or ": CRITICAL" in line:
            return "log-error"
        if ": WARNING" in line:
            return "log-warn"
        return "log-info"

    async def _fetch_datastream_status() -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        url: str | None = (
            f"{frost_endpoint}/Datastreams"
            "?$expand=Observations($top=1;$orderby=phenomenonTime%20desc),Thing"
            "&$top=200"
        )
        headers = {"Authorization": f"Basic {_frost_auth}"} if _frost_auth else {}
        async with httpx.AsyncClient() as client:
            while url:
                try:
                    resp = await client.get(url, headers=headers, timeout=15.0)
                    resp.raise_for_status()
                except httpx.RequestError:
                    break
                data = resp.json()
                results.extend(data.get("value", []))
                next_link: str | None = data.get("@iot.nextLink")
                if next_link:
                    # Rewrite external host in nextLink back to internal frost_endpoint
                    internal_base = frost_endpoint.split("/FROST-Server")[0]
                    external_base = next_link.split("/FROST-Server")[0]
                    url = next_link.replace(external_base, internal_base)
                else:
                    url = None
        return results

    def _load_tokens() -> list[dict[str, Any]]:
        result = []
        if tokens_dir.exists():
            for p in sorted(tokens_dir.glob("*.json")):
                try:
                    data = json.loads(p.read_text())
                    result.append({"name": p.stem, "keys": list(data.keys())})
                except Exception:
                    result.append({"name": p.stem, "keys": []})
        return result

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
    # GET /applications
    # ------------------------------------------------------------------

    @app.get("/applications", response_model=ApplicationsResponse, tags=["applications"])
    def list_applications() -> ApplicationsResponse:
        """List all provider applications from application-configs.yml."""
        raw = _load_app_config_raw()
        apps_dict = raw.get("applications", {})
        creds = _load_credentials()
        result = []
        for name, cfg in apps_dict.items():
            has_token = tokens_dir.exists() and (tokens_dir / f"{name}.json").exists()
            result.append(ApplicationInfo(
                name=name,
                provider=cfg.get("provider", ""),
                config=cfg,
                has_credentials=name in creds,
                has_token=has_token,
            ))
        return ApplicationsResponse(applications=result)

    # ------------------------------------------------------------------
    # POST /applications
    # ------------------------------------------------------------------

    @app.post(
        "/applications",
        response_model=MessageResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["applications"],
    )
    def create_application(body: CreateApplicationRequest) -> MessageResponse:
        """Add a new provider application to application-configs.yml."""
        raw = _load_app_config_raw()
        apps = raw.setdefault("applications", {})
        if body.name in apps:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Application '{body.name}' already exists.",
            )
        apps[body.name] = body.config.model_dump(exclude_none=True)
        _write_app_config(raw)
        logger.info("Created application: %s", body.name)
        return MessageResponse(message=f"Application '{body.name}' created.")

    # ------------------------------------------------------------------
    # DELETE /applications/{name}
    # ------------------------------------------------------------------

    @app.delete("/applications/{name}", response_model=MessageResponse, tags=["applications"])
    def delete_application(name: str) -> MessageResponse:
        """Remove a provider application from application-configs.yml."""
        raw = _load_app_config_raw()
        apps = raw.get("applications", {})
        if name not in apps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application '{name}' not found.",
            )
        del apps[name]
        _write_app_config(raw)
        logger.info("Deleted application: %s", name)
        return MessageResponse(message=f"Application '{name}' deleted.")

    # ------------------------------------------------------------------
    # PATCH /applications/{name}
    # ------------------------------------------------------------------

    @app.patch("/applications/{name}", response_model=MessageResponse, tags=["applications"])
    def update_application(name: str, body: NetatmoAppConfig | TTSAppConfig) -> MessageResponse:
        """Replace the config for an existing provider application."""
        raw = _load_app_config_raw()
        apps = raw.get("applications", {})
        if name not in apps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application '{name}' not found.",
            )
        apps[name] = body.model_dump(exclude_none=True)
        _write_app_config(raw)
        logger.info("Updated application: %s", name)
        return MessageResponse(message=f"Application '{name}' updated.")

    # ------------------------------------------------------------------
    # PUT /credentials/{app_name}
    # ------------------------------------------------------------------

    @app.put("/credentials/{app_name}", response_model=MessageResponse, tags=["credentials"])
    def upsert_credential(app_name: str, api_key: str) -> MessageResponse:
        """Upsert an application API key in application_credentials.json."""
        creds = _load_credentials()
        creds[app_name] = {"api_key": api_key}
        _write_credentials(creds)
        logger.info("Upserted credential for: %s", app_name)
        return MessageResponse(message=f"Credential for '{app_name}' saved.")

    # ------------------------------------------------------------------
    # DELETE /credentials/{app_name}
    # ------------------------------------------------------------------

    @app.delete("/credentials/{app_name}", response_model=MessageResponse, tags=["credentials"])
    def delete_credential(app_name: str) -> MessageResponse:
        """Remove an application API key from application_credentials.json."""
        creds = _load_credentials()
        if app_name not in creds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No credential for '{app_name}'.",
            )
        del creds[app_name]
        _write_credentials(creds)
        logger.info("Deleted credential for: %s", app_name)
        return MessageResponse(message=f"Credential for '{app_name}' deleted.")

    # ------------------------------------------------------------------
    # GET /tokens
    # ------------------------------------------------------------------

    @app.get("/tokens", response_model=TokensResponse, tags=["tokens"])
    def list_tokens() -> TokensResponse:
        """List OAuth token files and their top-level keys."""
        return TokensResponse(
            tokens=[TokenInfo(name=t["name"], keys=t["keys"]) for t in _load_tokens()]
        )

    # ------------------------------------------------------------------
    # PUT /tokens/{app_name}
    # ------------------------------------------------------------------

    @app.put("/tokens/{app_name}", response_model=MessageResponse, tags=["tokens"])
    def upsert_token(app_name: str, token_data: dict[str, str]) -> MessageResponse:
        """Write or replace an OAuth token file."""
        tokens_dir.mkdir(parents=True, exist_ok=True)
        token_file = tokens_dir / f"{app_name}.json"
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=4)
        logger.info("Upserted token for: %s", app_name)
        return MessageResponse(message=f"Token for '{app_name}' saved.")

    # ------------------------------------------------------------------
    # DELETE /tokens/{app_name}
    # ------------------------------------------------------------------

    @app.delete("/tokens/{app_name}", response_model=MessageResponse, tags=["tokens"])
    def delete_token(app_name: str) -> MessageResponse:
        """Delete an OAuth token file."""
        token_file = tokens_dir / f"{app_name}.json"
        if not token_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Token '{app_name}' not found.",
            )
        token_file.unlink()
        logger.info("Deleted token for: %s", app_name)
        return MessageResponse(message=f"Token for '{app_name}' deleted.")

    # ------------------------------------------------------------------
    # GET /logs
    # ------------------------------------------------------------------

    @app.get("/logs", response_model=LogsResponse, tags=["system"])
    def get_logs(n: int = 100) -> LogsResponse:
        """Return the last n lines of general.log."""
        return LogsResponse(lines=_tail_log(n))

    # ------------------------------------------------------------------
    # GET /datastreams/status
    # ------------------------------------------------------------------

    @app.get("/datastreams/status", tags=["system"])
    async def datastreams_status() -> dict[str, Any]:
        """Return all FROST datastreams grouped by Thing with staleness info."""
        raw = await _fetch_datastream_status()
        by_thing: dict[str, list[dict[str, Any]]] = {}
        for ds in raw:
            thing_name = ds.get("Thing", {}).get("name", "Unknown")
            obs = ds.get("Observations", [])
            last_time: str | None = obs[0].get("phenomenonTime") if obs else None
            css, label = _staleness_label(last_time)
            by_thing.setdefault(thing_name, []).append({
                "name": ds.get("name", ""),
                "last_observation": last_time,
                "staleness_class": css,
                "staleness_label": label,
            })
        return {
            "things": [
                {"name": k, "datastreams": v}
                for k, v in sorted(by_thing.items())
            ]
        }

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

    # ------------------------------------------------------------------
    # Web UI — Applications
    # ------------------------------------------------------------------

    @app.get("/ui/applications", response_class=HTMLResponse, include_in_schema=False)
    def applications_page(request: Request, created: str = "") -> HTMLResponse:
        raw = _load_app_config_raw()
        apps_dict = raw.get("applications", {})
        creds = _load_credentials()
        rows = []
        for name, cfg in apps_dict.items():
            has_token = tokens_dir.exists() and (tokens_dir / f"{name}.json").exists()
            rows.append({
                "name": name,
                "provider": cfg.get("provider", ""),
                "config": cfg,
                "has_credentials": name in creds,
                "has_token": has_token,
            })
        return _templates.TemplateResponse(request, "applications.html", {
            "applications": rows,
            "created": bool(created),
        })

    @app.get("/ui/applications/new", response_class=HTMLResponse, include_in_schema=False)
    def application_new_page(request: Request) -> HTMLResponse:
        from rime.providers.registry import PROVIDER_REGISTRY
        return _templates.TemplateResponse(request, "application_new.html", {
            "providers": list(PROVIDER_REGISTRY.keys()),
            "error": None,
            "form": {},
        })

    @app.get("/ui/applications/provider-fields", response_class=HTMLResponse, include_in_schema=False)
    def provider_fields_partial(request: Request, provider: str = "") -> HTMLResponse:
        return _templates.TemplateResponse(
            request, "partials/provider_fields.html", {"provider": provider, "form": {}}
        )

    @app.post("/ui/applications", response_class=HTMLResponse, include_in_schema=False)
    def create_application_form(
        request: Request,
        name: str = Form(...),
        provider: str = Form(...),
        max_retries: int = Form(10),
        expected_sensors: int | None = Form(None),
        request_interval: int | None = Form(None),
        host: str | None = Form(None),
        port: int | None = Form(None),
        topic: str | None = Form(None),
        api_key: str | None = Form(None),
    ) -> HTMLResponse:
        from rime.providers.registry import PROVIDER_REGISTRY

        form_data = {
            "name": name, "provider": provider, "max_retries": max_retries,
            "expected_sensors": expected_sensors, "request_interval": request_interval,
            "host": host, "port": port, "topic": topic, "api_key": api_key,
        }

        def _render_error(msg: str, code: int = 400) -> HTMLResponse:
            return _templates.TemplateResponse(
                request, "application_new.html",
                {"providers": list(PROVIDER_REGISTRY.keys()), "error": msg, "form": form_data},
                status_code=code,
            )

        if provider not in PROVIDER_REGISTRY:
            return _render_error(f"Unknown provider '{provider}'.", 400)

        raw = _load_app_config_raw()
        apps = raw.setdefault("applications", {})
        if name in apps:
            return _render_error(f"Application '{name}' already exists.", 409)

        cfg: dict[str, Any] = {"provider": provider, "max_retries": max_retries}
        if expected_sensors is not None:
            cfg["expected_sensors"] = expected_sensors

        if provider == "netatmo":
            if not request_interval:
                return _render_error("Request interval is required for Netatmo.", 400)
            cfg["request_interval"] = request_interval
        elif provider == "tts":
            if not host or not topic:
                return _render_error("Host and topic are required for TTS.", 400)
            if not api_key:
                return _render_error("API key is required for TTS.", 400)
            cfg["host"] = host
            cfg["port"] = port or 8883
            cfg["topic"] = topic

        apps[name] = cfg
        _write_app_config(raw)

        if provider == "tts" and api_key:
            creds = _load_credentials()
            creds[name] = {"api_key": api_key}
            _write_credentials(creds)

        logger.info("Created application via web UI: %s", name)
        return RedirectResponse(url="/ui/applications?created=1", status_code=303)

    @app.delete("/ui/applications/{name}", response_class=HTMLResponse, include_in_schema=False)
    def delete_application_htmx(name: str) -> Response:
        raw = _load_app_config_raw()
        apps = raw.get("applications", {})
        if name not in apps:
            raise HTTPException(status_code=404, detail=f"Application '{name}' not found.")
        del apps[name]
        _write_app_config(raw)
        logger.info("Deleted application via web UI: %s", name)
        return Response(content="", status_code=200)

    # ------------------------------------------------------------------
    # Web UI — Tokens
    # ------------------------------------------------------------------

    @app.get("/ui/tokens", response_class=HTMLResponse, include_in_schema=False)
    def tokens_page(request: Request, saved: str = "") -> HTMLResponse:
        return _templates.TemplateResponse(request, "tokens.html", {
            "tokens": _load_tokens(),
            "saved": bool(saved),
            "error": None,
            "form": {},
        })

    @app.post("/ui/tokens", response_class=HTMLResponse, include_in_schema=False)
    def create_token_form(
        request: Request,
        app_name: str = Form(...),
        token_json: str = Form(...),
    ) -> HTMLResponse:
        def _render_error(msg: str) -> HTMLResponse:
            return _templates.TemplateResponse(
                request, "tokens.html",
                {"tokens": _load_tokens(), "saved": False, "error": msg,
                 "form": {"app_name": app_name}},
                status_code=400,
            )

        try:
            token_data = json.loads(token_json)
        except json.JSONDecodeError as exc:
            return _render_error(f"Invalid JSON: {exc}")
        if not isinstance(token_data, dict):
            return _render_error("Token JSON must be an object ({...}).")

        tokens_dir.mkdir(parents=True, exist_ok=True)
        token_file = tokens_dir / f"{app_name}.json"
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=4)
        logger.info("Saved token via web UI: %s", app_name)
        return RedirectResponse(url="/ui/tokens?saved=1", status_code=303)

    @app.delete("/ui/tokens/{name}", response_class=HTMLResponse, include_in_schema=False)
    def delete_token_htmx(name: str) -> Response:
        token_file = tokens_dir / f"{name}.json"
        if not token_file.exists():
            raise HTTPException(status_code=404, detail=f"Token '{name}' not found.")
        token_file.unlink()
        logger.info("Deleted token via web UI: %s", name)
        return Response(content="", status_code=200)

    # ------------------------------------------------------------------
    # Web UI — Logs
    # ------------------------------------------------------------------

    @app.get("/ui/logs", response_class=HTMLResponse, include_in_schema=False)
    def logs_page(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(request, "logs.html")

    @app.get("/ui/logs/tail", response_class=HTMLResponse, include_in_schema=False)
    def log_tail_partial(request: Request) -> HTMLResponse:
        raw_lines = _tail_log(100)
        lines = [(line.rstrip("\n"), _classify_line(line)) for line in raw_lines]
        return _templates.TemplateResponse(
            request, "partials/log_tail.html", {"lines": lines}
        )

    # ------------------------------------------------------------------
    # Web UI — Datastreams
    # ------------------------------------------------------------------

    @app.get("/ui/datastreams", response_class=HTMLResponse, include_in_schema=False)
    def datastreams_page(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(request, "datastreams.html")

    @app.get("/ui/datastreams/data", response_class=HTMLResponse, include_in_schema=False)
    async def datastreams_partial(request: Request) -> HTMLResponse:
        raw = await _fetch_datastream_status()
        by_thing: dict[str, list[dict[str, Any]]] = {}
        for ds in raw:
            thing_name = ds.get("Thing", {}).get("name", "Unknown")
            obs = ds.get("Observations", [])
            last_time: str | None = obs[0].get("phenomenonTime") if obs else None
            css, label = _staleness_label(last_time)
            by_thing.setdefault(thing_name, []).append({
                "name": ds.get("name", ""),
                "staleness_class": css,
                "staleness_label": label,
            })
        things = [{"name": k, "datastreams": v} for k, v in sorted(by_thing.items())]
        frost_reachable = bool(raw)
        return _templates.TemplateResponse(
            request, "partials/datastreams_table.html",
            {"things": things, "frost_reachable": frost_reachable},
        )

    return app

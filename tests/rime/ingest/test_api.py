"""Unit tests for the ingest FastAPI application.

Uses FastAPI's TestClient — no real HTTP server, no threads, no providers.
The IngestRuntime is replaced with a MagicMock so every test controls
exactly what the runtime returns or raises.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from rime.ingest.api import create_app
from rime.ingest.runtime import IngestRuntime, RuntimeStatus, TransportStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_runtime() -> MagicMock:
    return MagicMock(spec=IngestRuntime)


@pytest.fixture()
def client(mock_runtime: MagicMock) -> TestClient:
    app = create_app(mock_runtime)
    return TestClient(app)


def _runtime_status(*app_names: str, alive: bool = True) -> RuntimeStatus:
    """Build a RuntimeStatus with one TransportStatus per given app name."""
    return RuntimeStatus(
        transports=[
            TransportStatus(
                app_name=name,
                is_alive=alive,
                push_success=0,
                push_fail=0,
            )
            for name in app_names
        ],
        uptime_seconds=42.0,
        expected_sensors=["sensor-uuid-1"],
    )


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"message": "ok"}


# ---------------------------------------------------------------------------
# POST /sensors/reload
# ---------------------------------------------------------------------------

class TestSensorReload:
    def test_reloads_sensor_registry(self, client, mock_runtime, tmp_path):
        # create a real dir so the endpoint doesn't 404
        sensor_dir = tmp_path / "sensor_configs"
        sensor_dir.mkdir()
        (sensor_dir / "sensor-a.yml").write_text("name: a\n")

        response = client.post(
            "/sensors/reload",
            json={"sensor_config_dir": str(sensor_dir)},
        )

        assert response.status_code == 200
        assert "updated" in response.json()["message"].lower()
        mock_runtime.update_sensor_registry.assert_called_once()

    def test_returns_404_when_dir_missing(self, client, mock_runtime):
        response = client.post(
            "/sensors/reload",
            json={"sensor_config_dir": "/does/not/exist"},
        )
        assert response.status_code == 404

    def test_returns_422_when_body_missing(self, client):
        response = client.post("/sensors/reload")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /transports/running-config
# ---------------------------------------------------------------------------

class TestRunningConfig:
    def test_returns_stored_configs(self, client, mock_runtime):
        mock_runtime.get_running_app_config.return_value = {
            "app-a": {"provider": "netatmo", "request_interval": 300},
        }

        response = client.get("/transports/running-config")

        assert response.status_code == 200
        assert response.json() == {
            "app-a": {"provider": "netatmo", "request_interval": 300}
        }

    def test_returns_empty_dict_when_no_transports(self, client, mock_runtime):
        mock_runtime.get_running_app_config.return_value = {}

        response = client.get("/transports/running-config")

        assert response.status_code == 200
        assert response.json() == {}


# ---------------------------------------------------------------------------
# GET /transports
# ---------------------------------------------------------------------------

class TestListTransports:
    def test_returns_all_transports(self, client, mock_runtime):
        mock_runtime.get_status.return_value = _runtime_status("app-a", "app-b")

        response = client.get("/transports")

        assert response.status_code == 200
        data = response.json()
        names = [t["app_name"] for t in data["transports"]]
        assert "app-a" in names
        assert "app-b" in names
        assert data["uptime_seconds"] == 42.0

    def test_returns_empty_list_when_no_transports(self, client, mock_runtime):
        mock_runtime.get_status.return_value = _runtime_status()

        response = client.get("/transports")

        assert response.status_code == 200
        assert response.json()["transports"] == []


# ---------------------------------------------------------------------------
# GET /transports/{app_name}
# ---------------------------------------------------------------------------

class TestGetTransport:
    def test_returns_transport_when_found(self, client, mock_runtime):
        mock_runtime.get_status.return_value = _runtime_status("app-a")

        response = client.get("/transports/app-a")

        assert response.status_code == 200
        assert response.json()["app_name"] == "app-a"
        assert response.json()["is_alive"] is True

    def test_returns_404_when_not_found(self, client, mock_runtime):
        mock_runtime.get_status.return_value = _runtime_status("app-a")

        response = client.get("/transports/does-not-exist")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /transports/{app_name}/start
# ---------------------------------------------------------------------------

class TestStartTransport:
    def test_starts_transport_successfully(self, client, mock_runtime):
        response = client.post(
            "/transports/new-app/start",
            json={"config": {"provider": "netatmo", "request_interval": 300}},
        )

        assert response.status_code == 201
        assert "started" in response.json()["message"].lower()
        mock_runtime.start_transport.assert_called_once_with(
            "new-app", {"provider": "netatmo", "request_interval": 300}
        )

    def test_returns_409_when_already_running(self, client, mock_runtime):
        mock_runtime.start_transport.side_effect = ValueError(
            "Transport 'new-app' is already running."
        )

        response = client.post(
            "/transports/new-app/start",
            json={"config": {"provider": "netatmo"}},
        )

        assert response.status_code == 409
        assert "already running" in response.json()["detail"].lower()

    def test_returns_422_when_body_missing(self, client):
        response = client.post("/transports/new-app/start")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /transports/{app_name}/stop
# ---------------------------------------------------------------------------

class TestStopTransport:
    def test_stops_transport_successfully(self, client, mock_runtime):
        response = client.post("/transports/app-a/stop")

        assert response.status_code == 200
        assert "stopped" in response.json()["message"].lower()
        mock_runtime.stop_transport.assert_called_once_with("app-a")

    def test_returns_404_when_not_found(self, client, mock_runtime):
        mock_runtime.stop_transport.side_effect = KeyError("Unknown transport: 'ghost'.")

        response = client.post("/transports/ghost/stop")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /transports/{app_name}/restart
# ---------------------------------------------------------------------------

class TestRestartTransport:
    def test_restarts_transport_successfully(self, client, mock_runtime):
        response = client.post(
            "/transports/app-a/restart",
            json={"config": {"provider": "tts", "host": "eu1.cloud.thethings.network"}},
        )

        assert response.status_code == 200
        assert "restarted" in response.json()["message"].lower()
        mock_runtime.restart_transport.assert_called_once_with(
            "app-a",
            {"provider": "tts", "host": "eu1.cloud.thethings.network"},
        )

    def test_returns_404_when_not_found(self, client, mock_runtime):
        mock_runtime.restart_transport.side_effect = KeyError(
            "Unknown transport: 'ghost'."
        )

        response = client.post(
            "/transports/ghost/restart",
            json={"config": {"provider": "netatmo"}},
        )

        assert response.status_code == 404

    def test_returns_422_when_body_missing(self, client):
        response = client.post("/transports/app-a/restart")
        assert response.status_code == 422

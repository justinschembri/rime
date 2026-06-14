"""Unit tests for the rime-ctrl FastAPI application.

Uses FastAPI's TestClient — no real HTTP, no running Docker containers.
The IngestClient and reconcile function are mocked; FROST calls use
httpx's MockTransport.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from rime.ctrl.api import create_app
from rime.ctrl.reconciler import IngestClient, TransportDiff


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ops_dir(tmp_path) -> dict:
    """Minimal ops directory with one sensor config and an app config."""
    app_config = tmp_path / "application-configs.yml"
    app_config.write_text(textwrap.dedent("""\
        applications:
          app-a:
            provider: netatmo
            request_interval: 300
    """))
    sensor_dir = tmp_path / "sensor_configs"
    sensor_dir.mkdir()
    (sensor_dir / "sensor-a.yml").write_text("name: sensor-a\n")
    return {"app_config": app_config, "sensor_dir": sensor_dir}


@pytest.fixture()
def mock_ingest_client() -> MagicMock:
    return MagicMock(spec=IngestClient, base_url="http://ingest:8001")


@pytest.fixture()
def client(ops_dir, mock_ingest_client) -> TestClient:
    app = create_app(
        ingest_client=mock_ingest_client,
        sensor_config_dir=ops_dir["sensor_dir"],
        app_config_path=ops_dir["app_config"],
        frost_endpoint="http://frost-mock:8080/FROST-Server/v1.1",
    )
    return TestClient(app)


def _make_diff(**kwargs) -> TransportDiff:
    defaults = dict(to_start={}, to_stop=[], to_restart={}, unchanged=[])
    defaults.update(kwargs)
    d = MagicMock(spec=TransportDiff)
    d.to_start = defaults["to_start"]
    d.to_stop = defaults["to_stop"]
    d.to_restart = defaults["to_restart"]
    d.unchanged = defaults["unchanged"]
    return d


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"message": "ok"}


# ---------------------------------------------------------------------------
# POST /reconcile
# ---------------------------------------------------------------------------

class TestReconcile:
    def test_returns_diff_on_success(self, client, ops_dir):
        diff = _make_diff(started=["app-new"], unchanged=["app-a"])
        diff.to_start = {"app-new": {}}
        diff.to_stop = []
        diff.to_restart = {}
        diff.unchanged = ["app-a"]

        with patch("rime.ctrl.api.reconcile", return_value=diff):
            response = client.post("/reconcile")

        assert response.status_code == 200
        body = response.json()
        assert "app-new" in body["started"]
        assert "app-a" in body["unchanged"]
        assert body["stopped"] == []
        assert body["restarted"] == []

    def test_returns_409_when_lock_held(self, client, ops_dir):
        import threading

        # Simulate a slow reconcile holding the lock
        diff = _make_diff()
        barrier = threading.Barrier(2)

        def slow_reconcile(**kwargs):
            barrier.wait()   # signal we've started
            barrier.wait()   # wait for test to fire second request
            return diff

        results = {}

        def first_request():
            with patch("rime.ctrl.api.reconcile", side_effect=slow_reconcile):
                results["first"] = client.post("/reconcile")

        t = threading.Thread(target=first_request)
        t.start()
        barrier.wait()  # wait until slow reconcile has the lock

        # Second request should get 409
        with patch("rime.ctrl.api.reconcile", return_value=diff):
            second = client.post("/reconcile")
        assert second.status_code == 409

        barrier.wait()  # let slow reconcile finish
        t.join()

    def test_propagates_reconcile_exception(self, client):
        with patch("rime.ctrl.api.reconcile", side_effect=ConnectionError("ingest down")):
            with pytest.raises(ConnectionError):
                client.post("/reconcile")


# ---------------------------------------------------------------------------
# GET /sensors
# ---------------------------------------------------------------------------

class TestListSensors:
    def test_returns_sensor_files(self, client, ops_dir):
        response = client.get("/sensors")
        assert response.status_code == 200
        names = [s["name"] for s in response.json()["sensors"]]
        assert "sensor-a" in names

    def test_excludes_template_files(self, client, ops_dir):
        (ops_dir["sensor_dir"] / "template_netatmo.yml").write_text("template: true\n")
        response = client.get("/sensors")
        names = [s["name"] for s in response.json()["sensors"]]
        assert "template_netatmo" not in names

    def test_returns_empty_when_no_sensors(self, ops_dir, mock_ingest_client):
        empty_dir = ops_dir["sensor_dir"].parent / "empty_sensors"
        empty_dir.mkdir()
        app = create_app(
            ingest_client=mock_ingest_client,
            sensor_config_dir=empty_dir,
            app_config_path=ops_dir["app_config"],
        )
        c = TestClient(app)
        response = c.get("/sensors")
        assert response.status_code == 200
        assert response.json()["sensors"] == []


# ---------------------------------------------------------------------------
# DELETE /sensors/{name}
# ---------------------------------------------------------------------------

class TestDeleteSensor:
    def test_deletes_existing_yml_file(self, client, ops_dir):
        assert (ops_dir["sensor_dir"] / "sensor-a.yml").exists()
        response = client.delete("/sensors/sensor-a")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()
        assert not (ops_dir["sensor_dir"] / "sensor-a.yml").exists()

    def test_returns_404_when_not_found(self, client):
        response = client.delete("/sensors/does-not-exist")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_deletes_yaml_extension_too(self, client, ops_dir):
        (ops_dir["sensor_dir"] / "sensor-b.yaml").write_text("name: b\n")
        response = client.delete("/sensors/sensor-b")
        assert response.status_code == 200
        assert not (ops_dir["sensor_dir"] / "sensor-b.yaml").exists()


# ---------------------------------------------------------------------------
# GET /frost/{path} — proxy
# ---------------------------------------------------------------------------

class TestFrostProxy:
    def test_proxies_get_to_frost(self, client):
        import httpx

        mock_response = httpx.Response(
            200,
            json={"value": []},
            request=httpx.Request("GET", "http://frost-mock:8080/FROST-Server/v1.1/Things"),
        )

        with patch("rime.ctrl.api.get_frost_auth_header", return_value=None), \
             patch("httpx.AsyncClient.request", return_value=mock_response):
            response = client.get("/frost/Things")

        assert response.status_code == 200

    def test_returns_502_when_frost_unreachable(self, client):
        import httpx

        with patch("rime.ctrl.api.get_frost_auth_header", return_value=None), \
             patch(
                 "httpx.AsyncClient.request",
                 side_effect=httpx.ConnectError("Connection refused"),
             ):
            response = client.get("/frost/Things")

        assert response.status_code == 502


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_returns_status_when_both_reachable(self, client, mock_ingest_client):
        with patch("rime.ctrl.api._requests.get") as mock_get:
            frost_resp = MagicMock()
            frost_resp.status_code = 200

            ingest_resp = MagicMock()
            ingest_resp.status_code = 200
            ingest_resp.json.return_value = {
                "transports": [{"app_name": "app-a", "is_alive": True}]
            }
            ingest_resp.raise_for_status = MagicMock()

            mock_get.side_effect = [frost_resp, ingest_resp]

            response = client.get("/status")

        assert response.status_code == 200
        body = response.json()
        assert body["frost_reachable"] is True
        assert body["ingest_reachable"] is True
        assert len(body["transports"]) == 1

    def test_reports_frost_unreachable(self, client):
        with patch("rime.ctrl.api._requests.get", side_effect=ConnectionError):
            response = client.get("/status")

        assert response.status_code == 200
        assert response.json()["frost_reachable"] is False
        assert response.json()["ingest_reachable"] is False

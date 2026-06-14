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
    secrets_dir = tmp_path / "secrets" / "credentials"
    secrets_dir.mkdir(parents=True)
    tokens_dir = tmp_path / "secrets" / "tokens"
    tokens_dir.mkdir(parents=True)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)
    return {
        "app_config": app_config,
        "sensor_dir": sensor_dir,
        "creds_path": secrets_dir / "application_credentials.json",
        "tokens_dir": tokens_dir,
        "logs_dir": logs_dir,
    }


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
        credentials_path=ops_dir["creds_path"],
        tokens_dir=ops_dir["tokens_dir"],
        logs_dir=ops_dir["logs_dir"],
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
# GET /sensors/models
# ---------------------------------------------------------------------------

class TestListSensorModels:
    def test_returns_models_from_templates(self, ops_dir, mock_ingest_client):
        templates_dir = ops_dir["sensor_dir"] / "netatmo"
        templates_dir.mkdir()
        (templates_dir / "template_netatmo.nws03.yaml").write_text("Sensors: {}\n")

        app = create_app(
            ingest_client=mock_ingest_client,
            sensor_config_dir=ops_dir["sensor_dir"],
            app_config_path=ops_dir["app_config"],
        )
        response = TestClient(app).get("/sensors/models")

        assert response.status_code == 200
        assert "netatmo.nws03" in response.json()["models"]

    def test_returns_empty_when_no_templates(self, client):
        response = client.get("/sensors/models")
        assert response.status_code == 200
        assert response.json()["models"] == []


# ---------------------------------------------------------------------------
# POST /sensors
# ---------------------------------------------------------------------------

class TestCreateSensor:
    @pytest.fixture()
    def client_with_template(self, ops_dir, mock_ingest_client):
        """Client whose sensor_dir contains a minimal netatmo template."""
        template_dir = ops_dir["sensor_dir"] / "netatmo"
        template_dir.mkdir(exist_ok=True)
        # Minimal template with one placeholder of each type
        (template_dir / "template_netatmo.nws03.yaml").write_text(
            "Sensors:\n"
            "  netatmo.nws03:\n"
            "    name: <SENSOR_ID>\n"
            "Things:\n"
            "  <THING_NAME>:\n"
            "    description: <THING_DESCRIPTION>\n"
            "Locations:\n"
            "  <LOCATION_NAME>:\n"
            "    description: <LOCATION_DESCRIPTION>\n"
            "    location:\n"
            "      type: Point\n"
            "      coordinates: [<LONGITUDE>, <LATITUDE>]\n"
        )
        app = create_app(
            ingest_client=mock_ingest_client,
            sensor_config_dir=ops_dir["sensor_dir"],
            app_config_path=ops_dir["app_config"],
        )
        return TestClient(app), ops_dir["sensor_dir"]

    def _payload(self, **overrides):
        base = {
            "sensor_model": "netatmo.nws03",
            "sensor_id": "aa:bb:cc:dd:ee:ff",
            "thing_name": "Test Station",
            "thing_description": "A test weather station",
            "location_name": "Roof",
            "location_description": "Rooftop location",
            "longitude": 4.35,
            "latitude": 52.01,
        }
        base.update(overrides)
        return base

    def test_creates_yaml_file(self, client_with_template):
        client, sensor_dir = client_with_template
        response = client.post("/sensors", json=self._payload())

        assert response.status_code == 201
        assert "created" in response.json()["message"].lower()
        assert (sensor_dir / "aa:bb:cc:dd:ee:ff.yml").exists()

    def test_replaces_sensor_id_placeholder(self, client_with_template):
        import yaml
        client, sensor_dir = client_with_template
        client.post("/sensors", json=self._payload())

        with open(sensor_dir / "aa:bb:cc:dd:ee:ff.yml") as f:
            config = yaml.safe_load(f)

        assert config["Sensors"]["netatmo.nws03"]["name"] == "aa:bb:cc:dd:ee:ff"

    def test_returns_404_for_unknown_model(self, client_with_template):
        client, _ = client_with_template
        response = client.post("/sensors", json=self._payload(sensor_model="unknown.model"))
        assert response.status_code == 404
        assert "template" in response.json()["detail"].lower()

    def test_returns_409_when_sensor_already_exists(self, client_with_template):
        client, _ = client_with_template
        client.post("/sensors", json=self._payload())
        response = client.post("/sensors", json=self._payload())
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()


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


# ---------------------------------------------------------------------------
# GET /applications
# ---------------------------------------------------------------------------

class TestListApplications:
    def test_returns_applications_from_yaml(self, client):
        response = client.get("/applications")
        assert response.status_code == 200
        apps = response.json()["applications"]
        assert len(apps) == 1
        assert apps[0]["name"] == "app-a"
        assert apps[0]["provider"] == "netatmo"

    def test_returns_empty_when_no_applications(self, ops_dir, mock_ingest_client):
        ops_dir["app_config"].write_text("applications: {}\n")
        app = create_app(
            ingest_client=mock_ingest_client,
            sensor_config_dir=ops_dir["sensor_dir"],
            app_config_path=ops_dir["app_config"],
            credentials_path=ops_dir["creds_path"],
            tokens_dir=ops_dir["tokens_dir"],
        )
        response = TestClient(app).get("/applications")
        assert response.status_code == 200
        assert response.json()["applications"] == []

    def test_includes_has_credentials_flag(self, client, ops_dir):
        import json
        ops_dir["creds_path"].write_text(json.dumps({"app-a": {"api_key": "secret"}}))
        response = client.get("/applications")
        assert response.json()["applications"][0]["has_credentials"] is True

    def test_has_credentials_false_when_absent(self, client):
        response = client.get("/applications")
        assert response.json()["applications"][0]["has_credentials"] is False

    def test_has_token_true_when_file_exists(self, client, ops_dir):
        import json
        (ops_dir["tokens_dir"] / "app-a.json").write_text(
            json.dumps({"access_token": "tok"})
        )
        response = client.get("/applications")
        assert response.json()["applications"][0]["has_token"] is True


# ---------------------------------------------------------------------------
# POST /applications
# ---------------------------------------------------------------------------

class TestCreateApplication:
    def test_creates_netatmo_application(self, client, ops_dir):
        body = {"name": "new-app", "config": {"provider": "netatmo", "request_interval": 600}}
        response = client.post("/applications", json=body)
        assert response.status_code == 201
        assert "created" in response.json()["message"].lower()

        import yaml
        with open(ops_dir["app_config"]) as f:
            raw = yaml.safe_load(f)
        assert "new-app" in raw["applications"]
        assert raw["applications"]["new-app"]["provider"] == "netatmo"

    def test_creates_tts_application(self, client, ops_dir):
        body = {
            "name": "my-tts",
            "config": {
                "provider": "tts",
                "host": "eu1.cloud.thethings.network",
                "port": 8883,
                "topic": "v3/my-app@ttn/devices/+/up",
            },
        }
        response = client.post("/applications", json=body)
        assert response.status_code == 201

        import yaml
        with open(ops_dir["app_config"]) as f:
            raw = yaml.safe_load(f)
        assert raw["applications"]["my-tts"]["host"] == "eu1.cloud.thethings.network"

    def test_returns_409_when_name_exists(self, client):
        body = {"name": "app-a", "config": {"provider": "netatmo", "request_interval": 300}}
        response = client.post("/applications", json=body)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_returns_422_for_unknown_provider(self, client):
        body = {"name": "bad-app", "config": {"provider": "unknown"}}
        response = client.post("/applications", json=body)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /applications/{name}
# ---------------------------------------------------------------------------

class TestDeleteApplication:
    def test_deletes_existing_application(self, client, ops_dir):
        response = client.delete("/applications/app-a")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        import yaml
        with open(ops_dir["app_config"]) as f:
            raw = yaml.safe_load(f)
        assert "app-a" not in (raw.get("applications") or {})

    def test_returns_404_when_not_found(self, client):
        response = client.delete("/applications/does-not-exist")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PATCH /applications/{name}
# ---------------------------------------------------------------------------

class TestUpdateApplication:
    def test_updates_netatmo_config(self, client, ops_dir):
        body = {"provider": "netatmo", "request_interval": 120, "max_retries": 3}
        response = client.patch("/applications/app-a", json=body)
        assert response.status_code == 200

        import yaml
        with open(ops_dir["app_config"]) as f:
            raw = yaml.safe_load(f)
        assert raw["applications"]["app-a"]["request_interval"] == 120

    def test_returns_404_when_not_found(self, client):
        body = {"provider": "netatmo", "request_interval": 300, "max_retries": 10}
        response = client.patch("/applications/no-such-app", json=body)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /credentials/{app_name}
# ---------------------------------------------------------------------------

class TestUpsertCredential:
    def test_creates_credentials_file_when_missing(self, client, ops_dir):
        import json
        assert not ops_dir["creds_path"].exists()
        response = client.put("/credentials/app-a?api_key=my-secret")
        assert response.status_code == 200
        assert ops_dir["creds_path"].exists()
        creds = json.loads(ops_dir["creds_path"].read_text())
        assert creds["app-a"]["api_key"] == "my-secret"

    def test_updates_existing_credential(self, client, ops_dir):
        import json
        ops_dir["creds_path"].write_text(json.dumps({"app-a": {"api_key": "old"}}))
        client.put("/credentials/app-a?api_key=new-secret")
        creds = json.loads(ops_dir["creds_path"].read_text())
        assert creds["app-a"]["api_key"] == "new-secret"

    def test_deletes_credential(self, client, ops_dir):
        import json
        ops_dir["creds_path"].write_text(json.dumps({"app-a": {"api_key": "tok"}}))
        response = client.delete("/credentials/app-a")
        assert response.status_code == 200
        creds = json.loads(ops_dir["creds_path"].read_text())
        assert "app-a" not in creds

    def test_delete_returns_404_when_absent(self, client):
        response = client.delete("/credentials/no-such-app")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /tokens
# ---------------------------------------------------------------------------

class TestListTokens:
    def test_returns_empty_when_no_token_files(self, client):
        response = client.get("/tokens")
        assert response.status_code == 200
        assert response.json()["tokens"] == []

    def test_returns_token_names_and_keys(self, client, ops_dir):
        import json
        (ops_dir["tokens_dir"] / "app-a.json").write_text(
            json.dumps({"access_token": "tok", "refresh_token": "ref"})
        )
        response = client.get("/tokens")
        tokens = response.json()["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["name"] == "app-a"
        assert "access_token" in tokens[0]["keys"]
        assert "refresh_token" in tokens[0]["keys"]


# ---------------------------------------------------------------------------
# PUT /tokens/{app_name}  +  DELETE /tokens/{app_name}
# ---------------------------------------------------------------------------

class TestUpsertToken:
    def test_creates_token_file(self, client, ops_dir):
        import json
        token_data = {"access_token": "abc", "refresh_token": "xyz"}
        response = client.put("/tokens/app-a", json=token_data)
        assert response.status_code == 200
        written = json.loads((ops_dir["tokens_dir"] / "app-a.json").read_text())
        assert written["access_token"] == "abc"

    def test_overwrites_existing(self, client, ops_dir):
        import json
        (ops_dir["tokens_dir"] / "app-a.json").write_text(json.dumps({"access_token": "old"}))
        client.put("/tokens/app-a", json={"access_token": "new"})
        written = json.loads((ops_dir["tokens_dir"] / "app-a.json").read_text())
        assert written["access_token"] == "new"

    def test_deletes_token_file(self, client, ops_dir):
        import json
        (ops_dir["tokens_dir"] / "app-a.json").write_text(json.dumps({"access_token": "tok"}))
        response = client.delete("/tokens/app-a")
        assert response.status_code == 200
        assert not (ops_dir["tokens_dir"] / "app-a.json").exists()

    def test_delete_returns_404_when_absent(self, client):
        response = client.delete("/tokens/no-such-app")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /logs
# ---------------------------------------------------------------------------

class TestGetLogs:
    def test_returns_empty_list_when_log_file_missing(self, client):
        response = client.get("/logs")
        assert response.status_code == 200
        assert response.json()["lines"] == []

    def test_returns_lines_from_log_file(self, client, ops_dir):
        log_file = ops_dir["logs_dir"] / "general.log"
        log_file.write_text("line1\nline2\nline3\n")
        response = client.get("/logs")
        assert response.status_code == 200
        lines = response.json()["lines"]
        assert len(lines) == 3
        assert "line1\n" in lines

    def test_respects_n_query_param(self, client, ops_dir):
        log_file = ops_dir["logs_dir"] / "general.log"
        log_file.write_text("\n".join(f"line{i}" for i in range(200)) + "\n")
        response = client.get("/logs?n=10")
        assert response.status_code == 200
        assert len(response.json()["lines"]) == 10


# ---------------------------------------------------------------------------
# GET /datastreams/status
# ---------------------------------------------------------------------------

def _make_ds_response(value: list, next_link: str | None = None) -> "httpx.Response":
    import httpx
    body: dict = {"value": value}
    if next_link:
        body["@iot.nextLink"] = next_link
    return httpx.Response(
        200,
        json=body,
        request=httpx.Request(
            "GET",
            "http://frost-mock:8080/FROST-Server/v1.1/Datastreams",
        ),
    )


class TestDatastreamsStatus:
    def _ds(self, name: str, thing_name: str, last_obs: str | None = None) -> dict:
        obs = [{"phenomenonTime": last_obs}] if last_obs else []
        return {"name": name, "Thing": {"name": thing_name}, "Observations": obs}

    def test_returns_grouped_by_thing(self, client):
        import httpx
        from unittest.mock import AsyncMock

        ds_list = [
            self._ds("Temperature", "Station A", "2030-01-01T00:00:00Z"),
            self._ds("Humidity", "Station A", "2030-01-01T00:01:00Z"),
            self._ds("Temperature", "Station B", "2030-01-01T00:02:00Z"),
        ]
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_make_ds_response(ds_list))):
            response = client.get("/datastreams/status")

        assert response.status_code == 200
        data = response.json()
        thing_names = [t["name"] for t in data["things"]]
        assert "Station A" in thing_names
        assert "Station B" in thing_names
        station_a = next(t for t in data["things"] if t["name"] == "Station A")
        assert len(station_a["datastreams"]) == 2

    def test_marks_fresh_observation_correctly(self, client):
        import httpx
        from datetime import datetime, timezone, timedelta
        from unittest.mock import AsyncMock

        recent = (datetime.now(tz=timezone.utc) - timedelta(minutes=5)).isoformat()
        ds_list = [self._ds("Temp", "Station A", recent)]
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_make_ds_response(ds_list))):
            response = client.get("/datastreams/status")

        thing = response.json()["things"][0]
        ds = thing["datastreams"][0]
        assert ds["staleness_class"] == "badge-ok"
        assert "m ago" in ds["staleness_label"] or ds["staleness_label"] == "just now"

    def test_marks_stale_observation_correctly(self, client):
        import httpx
        from datetime import datetime, timezone, timedelta
        from unittest.mock import AsyncMock

        old = (datetime.now(tz=timezone.utc) - timedelta(hours=3)).isoformat()
        ds_list = [self._ds("Temp", "Station A", old)]
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_make_ds_response(ds_list))):
            response = client.get("/datastreams/status")

        ds = response.json()["things"][0]["datastreams"][0]
        assert ds["staleness_class"] == "badge-error"
        assert "h ago" in ds["staleness_label"]

    def test_marks_no_data_when_no_observations(self, client):
        import httpx
        from unittest.mock import AsyncMock

        ds_list = [self._ds("Temp", "Station A", None)]
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_make_ds_response(ds_list))):
            response = client.get("/datastreams/status")

        ds = response.json()["things"][0]["datastreams"][0]
        assert ds["staleness_class"] == "badge-muted"
        assert ds["staleness_label"] == "no data"

    def test_handles_frost_unreachable_gracefully(self, client):
        import httpx
        from unittest.mock import AsyncMock

        with patch(
            "httpx.AsyncClient.get",
            new=AsyncMock(side_effect=httpx.RequestError("timeout")),
        ):
            response = client.get("/datastreams/status")

        assert response.status_code == 200
        assert response.json()["things"] == []

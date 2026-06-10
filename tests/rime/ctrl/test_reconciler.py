"""Unit tests for the ctrl-plane reconciler.

All external calls (FROST, ingest API) are mocked — no network required.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from rime.ctrl.reconciler import (
    IngestClient,
    TransportDiff,
    diff_app_configs,
    load_app_config,
    reconcile,
)


# ---------------------------------------------------------------------------
# load_app_config
# ---------------------------------------------------------------------------

class TestLoadAppConfig:
    def test_loads_valid_yaml(self, tmp_path):
        config_file = tmp_path / "application-configs.yml"
        config_file.write_text(textwrap.dedent("""\
            applications:
              app-a:
                provider: netatmo
                request_interval: 300
        """))

        result = load_app_config(config_file)

        assert "app-a" in result
        assert result["app-a"]["provider"] == "netatmo"

    def test_raises_on_missing_applications_key(self, tmp_path):
        config_file = tmp_path / "bad.yml"
        config_file.write_text("something_else: true\n")

        with pytest.raises(ValueError, match="Missing 'applications' key"):
            load_app_config(config_file)


# ---------------------------------------------------------------------------
# diff_app_configs
# ---------------------------------------------------------------------------

class TestDiffAppConfigs:
    def test_new_app_goes_to_to_start(self):
        desired = {"app-new": {"provider": "netatmo"}}
        running = {}

        diff = diff_app_configs(desired, running)

        assert "app-new" in diff.to_start
        assert diff.to_stop == []
        assert diff.to_restart == {}

    def test_removed_app_goes_to_to_stop(self):
        desired = {}
        running = {"app-old": {"provider": "netatmo"}}

        diff = diff_app_configs(desired, running)

        assert "app-old" in diff.to_stop
        assert diff.to_start == {}

    def test_changed_app_goes_to_to_restart(self):
        desired = {"app-a": {"provider": "netatmo", "request_interval": 600}}
        running = {"app-a": {"provider": "netatmo", "request_interval": 300}}

        diff = diff_app_configs(desired, running)

        assert "app-a" in diff.to_restart
        assert diff.to_stop == []
        assert diff.to_start == {}

    def test_unchanged_app_goes_to_unchanged(self):
        config = {"app-a": {"provider": "netatmo", "request_interval": 300}}

        diff = diff_app_configs(config, config)

        assert "app-a" in diff.unchanged
        assert diff.to_start == {}
        assert diff.to_stop == []
        assert diff.to_restart == {}

    def test_mixed_changes(self):
        desired = {
            "app-new": {"provider": "tts"},
            "app-same": {"provider": "netatmo"},
            "app-changed": {"provider": "netatmo", "request_interval": 600},
        }
        running = {
            "app-old": {"provider": "tts"},
            "app-same": {"provider": "netatmo"},
            "app-changed": {"provider": "netatmo", "request_interval": 300},
        }

        diff = diff_app_configs(desired, running)

        assert "app-new" in diff.to_start
        assert "app-old" in diff.to_stop
        assert "app-changed" in diff.to_restart
        assert "app-same" in diff.unchanged


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------

class TestReconcile:
    @pytest.fixture()
    def app_config_file(self, tmp_path) -> Path:
        f = tmp_path / "application-configs.yml"
        f.write_text(textwrap.dedent("""\
            applications:
              app-new:
                provider: netatmo
                request_interval: 300
        """))
        return f

    @pytest.fixture()
    def mock_ingest_client(self) -> MagicMock:
        return MagicMock(spec=IngestClient)

    def test_starts_new_transport(self, app_config_file, mock_ingest_client):
        with patch("rime.ctrl.reconciler.provision_frost"), \
             patch("rime.ctrl.reconciler.load_sensor_configs", return_value=[]):
            diff = reconcile(
                app_config_path=app_config_file,
                sensor_config_paths=[],
                ingest_client=mock_ingest_client,
                running_app_config={},   # nothing running
            )

        assert "app-new" in diff.to_start
        mock_ingest_client.start_transport.assert_called_once_with(
            "app-new", {"provider": "netatmo", "request_interval": 300}
        )
        mock_ingest_client.stop_transport.assert_not_called()
        mock_ingest_client.restart_transport.assert_not_called()

    def test_stops_removed_transport(self, tmp_path, mock_ingest_client):
        config_file = tmp_path / "application-configs.yml"
        config_file.write_text("applications: {}\n")  # empty desired

        with patch("rime.ctrl.reconciler.provision_frost"), \
             patch("rime.ctrl.reconciler.load_sensor_configs", return_value=[]):
            diff = reconcile(
                app_config_path=config_file,
                sensor_config_paths=[],
                ingest_client=mock_ingest_client,
                running_app_config={"app-old": {"provider": "tts"}},
            )

        assert "app-old" in diff.to_stop
        mock_ingest_client.stop_transport.assert_called_once_with("app-old")
        mock_ingest_client.start_transport.assert_not_called()

    def test_restarts_changed_transport(self, tmp_path, mock_ingest_client):
        config_file = tmp_path / "application-configs.yml"
        config_file.write_text(textwrap.dedent("""\
            applications:
              app-a:
                provider: netatmo
                request_interval: 600
        """))

        with patch("rime.ctrl.reconciler.provision_frost"), \
             patch("rime.ctrl.reconciler.load_sensor_configs", return_value=[]):
            diff = reconcile(
                app_config_path=config_file,
                sensor_config_paths=[],
                ingest_client=mock_ingest_client,
                running_app_config={"app-a": {"provider": "netatmo", "request_interval": 300}},
            )

        assert "app-a" in diff.to_restart
        mock_ingest_client.restart_transport.assert_called_once_with(
            "app-a", {"provider": "netatmo", "request_interval": 600}
        )

    def test_no_ingest_calls_when_nothing_changes(self, tmp_path, mock_ingest_client):
        config = {"app-a": {"provider": "netatmo", "request_interval": 300}}
        config_file = tmp_path / "application-configs.yml"
        config_file.write_text(textwrap.dedent("""\
            applications:
              app-a:
                provider: netatmo
                request_interval: 300
        """))

        with patch("rime.ctrl.reconciler.provision_frost"), \
             patch("rime.ctrl.reconciler.load_sensor_configs", return_value=[]):
            diff = reconcile(
                app_config_path=config_file,
                sensor_config_paths=[],
                ingest_client=mock_ingest_client,
                running_app_config=config,
            )

        assert "app-a" in diff.unchanged
        mock_ingest_client.start_transport.assert_not_called()
        mock_ingest_client.stop_transport.assert_not_called()
        mock_ingest_client.restart_transport.assert_not_called()

    def test_reload_sensors_is_called_after_frost_provision(self, app_config_file, mock_ingest_client, tmp_path):
        sensor_dir = tmp_path / "sensor_configs"
        sensor_dir.mkdir()
        sensor_paths = [sensor_dir / "sensor-a.yml"]

        with patch("rime.ctrl.reconciler.provision_frost"), \
             patch("rime.ctrl.reconciler.load_sensor_configs", return_value=[]):
            reconcile(
                app_config_path=app_config_file,
                sensor_config_paths=sensor_paths,
                ingest_client=mock_ingest_client,
                sensor_config_dir=sensor_dir,
                running_app_config={},
            )

        mock_ingest_client.reload_sensors.assert_called_once_with(sensor_dir)

    def test_provision_frost_is_called(self, app_config_file, mock_ingest_client):
        mock_sensor = MagicMock()

        with patch("rime.ctrl.reconciler.provision_frost") as mock_provision, \
             patch("rime.ctrl.reconciler.load_sensor_configs", return_value=[mock_sensor]):
            reconcile(
                app_config_path=app_config_file,
                sensor_config_paths=[Path("fake.yml")],
                ingest_client=mock_ingest_client,
                running_app_config={},
            )

        mock_provision.assert_called_once_with([mock_sensor])


# ---------------------------------------------------------------------------
# IngestClient (HTTP contract)
# ---------------------------------------------------------------------------

class TestIngestClient:
    """Verify IngestClient sends correctly shaped requests."""

    @pytest.fixture()
    def ingest_client(self):
        return IngestClient("http://ingest:8001")

    def test_start_transport_posts_to_correct_url(self, ingest_client):
        with patch("rime.ctrl.reconciler.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            ingest_client.start_transport("app-a", {"provider": "netatmo"})

        mock_post.assert_called_once_with(
            "http://ingest:8001/transports/app-a/start",
            json={"config": {"provider": "netatmo"}},
            timeout=10,
        )

    def test_stop_transport_posts_to_correct_url(self, ingest_client):
        with patch("rime.ctrl.reconciler.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            ingest_client.stop_transport("app-a")

        mock_post.assert_called_once_with(
            "http://ingest:8001/transports/app-a/stop",
            timeout=10,
        )

    def test_reload_sensors_posts_to_correct_url(self, ingest_client):
        with patch("rime.ctrl.reconciler.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            ingest_client.reload_sensors(Path("/ops/sensor_configs"))

        mock_post.assert_called_once_with(
            "http://ingest:8001/sensors/reload",
            json={"sensor_config_dir": "/ops/sensor_configs"},
            timeout=10,
        )

    def test_get_running_config_calls_correct_url(self, ingest_client):
        with patch("rime.ctrl.reconciler.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = {
                "app-a": {"provider": "netatmo"}
            }
            result = ingest_client.get_running_config()

        mock_get.assert_called_once_with(
            "http://ingest:8001/transports/running-config",
            timeout=10,
        )
        assert result == {"app-a": {"provider": "netatmo"}}

    def test_restart_transport_posts_to_correct_url(self, ingest_client):
        with patch("rime.ctrl.reconciler.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            ingest_client.restart_transport("app-a", {"provider": "tts"})

        mock_post.assert_called_once_with(
            "http://ingest:8001/transports/app-a/restart",
            json={"config": {"provider": "tts"}},
            timeout=10,
        )

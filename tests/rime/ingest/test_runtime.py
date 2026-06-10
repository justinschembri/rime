"""Unit tests for IngestRuntime.

All tests use mock SensorTransport instances so no real providers,
MQTT brokers, or network connections are needed.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rime.ingest.runtime import IngestRuntime, _parse_app_config, _build_sensor_registry
from rime.transport import SensorTransport
from rime.transformers.types import SensorUUID, SupportedSensors


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_mock_transport(app_name: str, alive: bool = True) -> MagicMock:
    """Return a MagicMock that looks like a running SensorTransport."""
    t = MagicMock(spec=SensorTransport)
    t.app_name = app_name
    t.is_alive = alive
    t._thread = MagicMock(spec=threading.Thread)
    t.sensor_registry = {}
    return t


def _make_provider_registry_patch(app_name: str) -> dict:
    """Return a fake PROVIDER_REGISTRY with one mock provider class."""
    mock_class = MagicMock()
    mock_class.__name__ = "MockProvider"
    # from_config returns a mock transport
    mock_class.from_config.return_value = _make_mock_transport(app_name)
    # make issubclass(..., SensorTransport) return True
    mock_class.__mro__ = [mock_class, SensorTransport, object]
    return {"mockprovider": mock_class}


SIMPLE_APP_CONFIG = {
    "test-app": {
        "provider": "mockprovider",
        "request_interval": 300,
    }
}


@pytest.fixture()
def runtime() -> IngestRuntime:
    return IngestRuntime()


# ---------------------------------------------------------------------------
# _parse_app_config unit tests
# ---------------------------------------------------------------------------

class TestParseAppConfig:
    def test_raises_on_missing_provider_key(self):
        with pytest.raises(ValueError, match="missing required key 'provider'"):
            _parse_app_config({"bad-app": {"request_interval": 60}})

    def test_raises_on_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            _parse_app_config({"bad-app": {"provider": "nonexistent"}})

    def test_returns_transport_set(self):
        mock_transport = _make_mock_transport("test-app")
        mock_class = MagicMock()
        mock_class.__name__ = "MockProvider"
        mock_class.from_config.return_value = mock_transport

        with patch(
            "rime.ingest.runtime.PROVIDER_REGISTRY",
            {"mockprovider": mock_class},
        ), patch(
            "rime.ingest.runtime.issubclass", return_value=True
        ):
            result = _parse_app_config(SIMPLE_APP_CONFIG)

        assert len(result) == 1
        transport = next(iter(result))
        assert transport.app_name == "test-app"


# ---------------------------------------------------------------------------
# IngestRuntime.start_all
# ---------------------------------------------------------------------------

class TestStartAll:
    def test_start_all_populates_connections(self, runtime):
        mock_transport = _make_mock_transport("app-a")
        mock_class = MagicMock()
        mock_class.__name__ = "MockProvider"
        mock_class.from_config.return_value = mock_transport

        with patch("rime.ingest.runtime.PROVIDER_REGISTRY", {"mockprovider": mock_class}), \
             patch("rime.ingest.runtime.issubclass", return_value=True), \
             patch("rime.ingest.runtime._build_sensor_registry", return_value={}), \
             patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.expected_sensors = set()
            mock_netmon.connections = set()
            mock_netmon.push_success = {}
            mock_netmon.push_fail = {}

            runtime.start_all({"app-a": {"provider": "mockprovider"}}, [])

        assert "app-a" in runtime.transport_names
        mock_transport.start.assert_called_once()

    def test_start_all_with_empty_config_starts_nothing(self, runtime):
        with patch("rime.ingest.runtime._build_sensor_registry", return_value={}), \
             patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.expected_sensors = set()
            mock_netmon.connections = set()
            mock_netmon.set_starting_threads = MagicMock()

            runtime.start_all({}, [])

        assert runtime.transport_names == []


# ---------------------------------------------------------------------------
# IngestRuntime.start_transport
# ---------------------------------------------------------------------------

class TestStartTransport:
    def test_starts_new_transport(self, runtime):
        mock_transport = _make_mock_transport("new-app")
        mock_class = MagicMock()
        mock_class.__name__ = "MockProvider"
        mock_class.from_config.return_value = mock_transport
        cfg = {"provider": "mockprovider"}

        with patch("rime.ingest.runtime.PROVIDER_REGISTRY", {"mockprovider": mock_class}), \
             patch("rime.ingest.runtime.issubclass", return_value=True), \
             patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.connections = set()

            runtime.start_transport("new-app", cfg)

        assert "new-app" in runtime.transport_names
        assert runtime._configs["new-app"] == cfg
        mock_transport.start.assert_called_once()

    def test_raises_if_transport_already_running(self, runtime):
        mock_transport = _make_mock_transport("existing-app", alive=True)
        runtime._connections["existing-app"] = mock_transport

        with pytest.raises(ValueError, match="already running"):
            with patch("rime.ingest.runtime.PROVIDER_REGISTRY", {}), \
                 patch("rime.ingest.runtime.netmon"):
                runtime.start_transport("existing-app", {"provider": "mockprovider"})


# ---------------------------------------------------------------------------
# IngestRuntime.stop_transport
# ---------------------------------------------------------------------------

class TestStopTransport:
    def test_stops_running_transport(self, runtime):
        mock_transport = _make_mock_transport("app-b", alive=True)
        runtime._connections["app-b"] = mock_transport
        runtime._configs["app-b"] = {"provider": "netatmo"}

        with patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.connections = {mock_transport}
            runtime.stop_transport("app-b")

        mock_transport.stop.assert_called_once()
        assert "app-b" not in runtime.transport_names
        assert "app-b" not in runtime._configs

    def test_raises_on_unknown_transport(self, runtime):
        with pytest.raises(KeyError, match="Unknown transport"):
            runtime.stop_transport("does-not-exist")

    def test_removes_transport_even_if_already_dead(self, runtime):
        mock_transport = _make_mock_transport("dead-app", alive=False)
        runtime._connections["dead-app"] = mock_transport

        with patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.connections = set()
            runtime.stop_transport("dead-app")

        assert "dead-app" not in runtime.transport_names
        mock_transport.stop.assert_not_called()  # already dead, no stop called


# ---------------------------------------------------------------------------
# IngestRuntime.restart_transport
# ---------------------------------------------------------------------------

class TestRestartTransport:
    def test_restart_stops_old_and_starts_new(self, runtime):
        old_transport = _make_mock_transport("app-c", alive=True)
        runtime._connections["app-c"] = old_transport

        new_transport = _make_mock_transport("app-c", alive=True)
        mock_class = MagicMock()
        mock_class.__name__ = "MockProvider"
        mock_class.from_config.return_value = new_transport

        with patch("rime.ingest.runtime.PROVIDER_REGISTRY", {"mockprovider": mock_class}), \
             patch("rime.ingest.runtime.issubclass", return_value=True), \
             patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.connections = {old_transport}

            runtime.restart_transport("app-c", {"provider": "mockprovider"})

        old_transport.stop.assert_called_once()
        new_transport.start.assert_called_once()
        assert "app-c" in runtime.transport_names

    def test_raises_on_unknown_transport(self, runtime):
        with pytest.raises(KeyError, match="Unknown transport"):
            runtime.restart_transport("ghost", {"provider": "mockprovider"})


# ---------------------------------------------------------------------------
# IngestRuntime.get_running_app_config
# ---------------------------------------------------------------------------

class TestGetRunningAppConfig:
    def test_returns_stored_configs(self, runtime):
        cfg_a = {"provider": "netatmo", "request_interval": 300}
        cfg_b = {"provider": "tts", "max_retries": 5}
        runtime._configs["app-a"] = cfg_a
        runtime._configs["app-b"] = cfg_b

        result = runtime.get_running_app_config()

        assert result == {"app-a": cfg_a, "app-b": cfg_b}

    def test_returns_empty_when_no_transports(self, runtime):
        assert runtime.get_running_app_config() == {}

    def test_config_removed_after_stop(self, runtime):
        mock_transport = _make_mock_transport("app-x", alive=True)
        runtime._connections["app-x"] = mock_transport
        runtime._configs["app-x"] = {"provider": "netatmo"}

        with patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.connections = set()
            runtime.stop_transport("app-x")

        assert "app-x" not in runtime.get_running_app_config()


# ---------------------------------------------------------------------------
# IngestRuntime.update_sensor_registry
# ---------------------------------------------------------------------------

class TestUpdateSensorRegistry:
    def test_registry_is_updated(self, runtime):
        mock_transport = _make_mock_transport("app-d")
        runtime._connections["app-d"] = mock_transport

        fake_registry = {"sensor-uuid-1": MagicMock(spec=SupportedSensors)}

        with patch(
            "rime.ingest.runtime._build_sensor_registry",
            return_value=fake_registry,
        ), patch("rime.ingest.runtime.netmon") as mock_netmon:
            mock_netmon.expected_sensors = set()
            runtime.update_sensor_registry([Path("fake/sensor.yml")])

        assert runtime._sensor_registry == fake_registry
        assert mock_transport.sensor_registry == fake_registry


# ---------------------------------------------------------------------------
# IngestRuntime.get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_status_for_each_transport(self, runtime):
        mock_transport = _make_mock_transport("app-e", alive=True)
        runtime._connections["app-e"] = mock_transport

        with patch("rime.ingest.runtime.netmon") as mock_netmon:
            from datetime import datetime
            mock_netmon.start_time = datetime.now()
            mock_netmon.expected_sensors = {"sensor-1"}
            mock_netmon.push_success = {}
            mock_netmon.push_fail = {}

            result = runtime.get_status()

        assert len(result.transports) == 1
        assert result.transports[0].app_name == "app-e"
        assert result.transports[0].is_alive is True
        assert "sensor-1" in result.expected_sensors

    def test_returns_empty_when_no_transports(self, runtime):
        with patch("rime.ingest.runtime.netmon") as mock_netmon:
            from datetime import datetime
            mock_netmon.start_time = datetime.now()
            mock_netmon.expected_sensors = set()
            mock_netmon.push_success = {}
            mock_netmon.push_fail = {}

            result = runtime.get_status()

        assert result.transports == []

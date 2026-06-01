"""Unit tests for the ctrl __main__ entry point.

Tests cover path resolution and the cold-start reconcile behaviour.
The git poll loop is not tested here (it runs forever) — that logic
is covered by test_watcher.py.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rime.ctrl.__main__ import _resolve_paths, main


# ---------------------------------------------------------------------------
# _resolve_paths
# ---------------------------------------------------------------------------

class TestResolvePaths:
    def test_resolves_from_env_vars(self, tmp_path):
        app_config = tmp_path / "application-configs.yml"
        app_config.write_text("applications: {}\n")
        sensor_dir = tmp_path / "sensor_configs"
        sensor_dir.mkdir()

        env = {
            "RIME_OPS_PATH": str(tmp_path),
            "APP_CONFIG_FILE": str(app_config),
            "SENSOR_CONFIG_PATH": str(sensor_dir),
        }
        with patch.dict("os.environ", env, clear=False):
            resolved_app, resolved_sensors = _resolve_paths()

        assert resolved_app == app_config
        assert resolved_sensors == []  # empty dir

    def test_discovers_sensor_yaml_files(self, tmp_path):
        app_config = tmp_path / "application-configs.yml"
        app_config.write_text("applications: {}\n")
        sensor_dir = tmp_path / "sensor_configs"
        sensor_dir.mkdir()
        (sensor_dir / "sensor-a.yml").write_text("name: a\n")
        (sensor_dir / "sensor-b.yaml").write_text("name: b\n")
        (sensor_dir / "template.yml").write_text("name: template\n")  # must be excluded

        env = {
            "APP_CONFIG_FILE": str(app_config),
            "SENSOR_CONFIG_PATH": str(sensor_dir),
        }
        with patch.dict("os.environ", env, clear=False):
            _, sensor_paths = _resolve_paths()

        names = {p.name for p in sensor_paths}
        assert "sensor-a.yml" in names
        assert "sensor-b.yaml" in names
        assert "template.yml" not in names  # excluded

    def test_raises_when_app_config_missing(self, tmp_path):
        sensor_dir = tmp_path / "sensor_configs"
        sensor_dir.mkdir()

        env = {
            "APP_CONFIG_FILE": str(tmp_path / "does-not-exist.yml"),
            "SENSOR_CONFIG_PATH": str(sensor_dir),
        }
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(FileNotFoundError, match="Application config not found"):
                _resolve_paths()

    def test_raises_when_sensor_dir_missing(self, tmp_path):
        app_config = tmp_path / "application-configs.yml"
        app_config.write_text("applications: {}\n")

        env = {
            "APP_CONFIG_FILE": str(app_config),
            "SENSOR_CONFIG_PATH": str(tmp_path / "no-such-dir"),
        }
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(FileNotFoundError, match="Sensor config directory not found"):
                _resolve_paths()


# ---------------------------------------------------------------------------
# main — cold start behaviour
# ---------------------------------------------------------------------------

class TestMain:
    @pytest.fixture()
    def ops_dir(self, tmp_path) -> Path:
        """A minimal ops directory with valid config files."""
        app_config = tmp_path / "application-configs.yml"
        app_config.write_text(textwrap.dedent("""\
            applications:
              app-a:
                provider: netatmo
                request_interval: 300
        """))
        sensor_dir = tmp_path / "sensor_configs"
        sensor_dir.mkdir()
        return tmp_path

    def test_cold_start_calls_reconcile(self, ops_dir):
        env = {
            "APP_CONFIG_FILE": str(ops_dir / "application-configs.yml"),
            "SENSOR_CONFIG_PATH": str(ops_dir / "sensor_configs"),
            "INGEST_API_URL": "http://ingest:8001",
            "CTRL_GIT_WATCH": "false",  # don't enter the poll loop
        }
        mock_diff = MagicMock()
        mock_diff.to_start = {}
        mock_diff.to_stop = []
        mock_diff.to_restart = {}
        mock_diff.unchanged = ["app-a"]

        with patch.dict("os.environ", env, clear=False), \
             patch("rime.ctrl.__main__.reconcile", return_value=mock_diff) as mock_reconcile:
            main()

        mock_reconcile.assert_called_once()
        call_kwargs = mock_reconcile.call_args.kwargs
        assert call_kwargs["app_config_path"] == ops_dir / "application-configs.yml"

    def test_cold_start_raises_on_reconcile_failure(self, ops_dir):
        env = {
            "APP_CONFIG_FILE": str(ops_dir / "application-configs.yml"),
            "SENSOR_CONFIG_PATH": str(ops_dir / "sensor_configs"),
            "INGEST_API_URL": "http://ingest:8001",
            "CTRL_GIT_WATCH": "false",
        }
        with patch.dict("os.environ", env, clear=False), \
             patch(
                 "rime.ctrl.__main__.reconcile",
                 side_effect=ConnectionError("ingest unreachable"),
             ):
            with pytest.raises(ConnectionError, match="ingest unreachable"):
                main()

    def test_git_watch_disabled_exits_after_cold_start(self, ops_dir):
        """When CTRL_GIT_WATCH=false, main() returns after one reconcile."""
        env = {
            "APP_CONFIG_FILE": str(ops_dir / "application-configs.yml"),
            "SENSOR_CONFIG_PATH": str(ops_dir / "sensor_configs"),
            "CTRL_GIT_WATCH": "false",
        }
        mock_diff = MagicMock()
        mock_diff.to_start = {}
        mock_diff.to_stop = []
        mock_diff.to_restart = {}
        mock_diff.unchanged = []

        with patch.dict("os.environ", env, clear=False), \
             patch("rime.ctrl.__main__.reconcile", return_value=mock_diff):
            # Should return without hanging — if it enters the poll loop it
            # would block forever and the test would time out.
            main()

    def test_git_watch_skipped_when_not_a_git_repo(self, ops_dir):
        """Non-git ops directory: reconcile runs once, no crash."""
        env = {
            "APP_CONFIG_FILE": str(ops_dir / "application-configs.yml"),
            "SENSOR_CONFIG_PATH": str(ops_dir / "sensor_configs"),
            "CTRL_GIT_WATCH": "true",
            "RIME_OPS_PATH": str(ops_dir),
        }
        mock_diff = MagicMock()
        mock_diff.to_start = {}
        mock_diff.to_stop = []
        mock_diff.to_restart = {}
        mock_diff.unchanged = []

        with patch.dict("os.environ", env, clear=False), \
             patch("rime.ctrl.__main__.reconcile", return_value=mock_diff), \
             patch(
                 "rime.ctrl.__main__.GitWatcher.initialise",
                 side_effect=RuntimeError("not a git repo"),
             ):
            main()  # should return gracefully, not raise

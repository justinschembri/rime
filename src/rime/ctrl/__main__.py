"""Entry point for the rime-ctrl service.

Responsibilities:
  1. Cold start: provision FROST and sync ingest transports from config files.
  2. Poll loop: pull the ops git repo every CTRL_POLL_INTERVAL seconds;
     re-reconcile whenever new commits arrive.

Usage:
    python -m rime.ctrl

Environment variables:
    INGEST_API_URL          URL of the rime-ingest API
                            (default: http://localhost:8001)

    RIME_OPS_PATH           Path to the cloned rime-ops repository.
                            Must contain application-configs.yml and
                            a sensor_configs/ directory.
                            (default: value of APPLICATION_CONFIG_FILE's
                            parent, falling back to deploy/)

    APP_CONFIG_FILE         Path to application-configs.yml.
                            (default: <RIME_OPS_PATH>/application-configs.yml)

    SENSOR_CONFIG_PATH      Path to the sensor_configs directory.
                            (default: <RIME_OPS_PATH>/sensor_configs)

    CTRL_POLL_INTERVAL      Seconds between git polls (default: 60)

    CTRL_GIT_REMOTE         Git remote to pull from (default: origin)
    CTRL_GIT_BRANCH         Git branch to track (default: main)
    CTRL_GIT_WATCH          Set to "false" to disable git polling and
                            reconcile only on startup (default: true)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from rime.loggers import setup_loggers
from rime.ctrl.reconciler import IngestClient, reconcile
from rime.ctrl.watcher import GitWatcher

setup_loggers()
logger = logging.getLogger("ctrl.main")


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def _resolve_paths() -> tuple[Path, list[Path], Path]:
    """Resolve app config file and sensor config paths from environment.

    Returns:
        Tuple of (app_config_path, sensor_config_paths, sensor_config_dir).

    Raises:
        FileNotFoundError: If resolved paths do not exist.
    """
    # Determine the ops root directory
    ops_path_env = os.getenv("RIME_OPS_PATH")
    if ops_path_env:
        ops_path = Path(ops_path_env)
    else:
        # Fall back to the path already used by the existing deploy setup
        from rime.paths import VARIABLE_APPLICATION_CONFIG_FILE
        ops_path = VARIABLE_APPLICATION_CONFIG_FILE.parent

    # Application config file
    app_config_env = os.getenv("APP_CONFIG_FILE")
    app_config_path = (
        Path(app_config_env) if app_config_env
        else ops_path / "application-configs.yml"
    )

    # Sensor config directory
    sensor_path_env = os.getenv("SENSOR_CONFIG_PATH")
    sensor_config_dir = (
        Path(sensor_path_env) if sensor_path_env
        else ops_path / "sensor_configs"
    )

    if not app_config_path.exists():
        raise FileNotFoundError(
            f"Application config not found: {app_config_path}"
        )
    if not sensor_config_dir.exists():
        raise FileNotFoundError(
            f"Sensor config directory not found: {sensor_config_dir}"
        )

    sensor_config_paths = [
        p for ext in ("*.yml", "*.yaml", "*.YML", "*.YAML")
        for p in sensor_config_dir.rglob(ext)
    ]
    sensor_config_paths = list({
        p for p in sensor_config_paths if "template" not in p.stem
    })

    logger.info("App config: %s", app_config_path)
    logger.info("Sensor configs: %d file(s) in %s", len(sensor_config_paths), sensor_config_dir)

    return app_config_path, sensor_config_paths, sensor_config_dir


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ingest_url = os.getenv("INGEST_API_URL", "http://localhost:8001")
    poll_interval = int(os.getenv("CTRL_POLL_INTERVAL", "60"))
    git_remote = os.getenv("CTRL_GIT_REMOTE", "origin")
    git_branch = os.getenv("CTRL_GIT_BRANCH", "main")
    git_watch = os.getenv("CTRL_GIT_WATCH", "true").lower() != "false"

    ingest_client = IngestClient(ingest_url)

    # ------------------------------------------------------------------
    # Cold start reconcile
    # ------------------------------------------------------------------
    logger.info("rime-ctrl starting. Ingest API: %s", ingest_url)

    app_config_path, sensor_config_paths, sensor_config_dir = _resolve_paths()

    logger.info("Running cold-start reconcile...")
    try:
        diff = reconcile(
            app_config_path=app_config_path,
            sensor_config_paths=sensor_config_paths,
            ingest_client=ingest_client,
            sensor_config_dir=sensor_config_dir,
        )
        logger.info(
            "Cold-start reconcile complete. "
            "started=%s stopped=%s restarted=%s unchanged=%s",
            list(diff.to_start),
            diff.to_stop,
            list(diff.to_restart),
            diff.unchanged,
        )
    except Exception as exc:
        logger.error("Cold-start reconcile failed: %s", exc)
        raise

    # ------------------------------------------------------------------
    # Git poll loop
    # ------------------------------------------------------------------
    if not git_watch:
        logger.info("Git watching disabled (CTRL_GIT_WATCH=false). Exiting.")
        return

    ops_path_env = os.getenv("RIME_OPS_PATH")
    ops_path = (
        Path(ops_path_env) if ops_path_env
        else app_config_path.parent
    )

    watcher = GitWatcher(ops_path, remote=git_remote, branch=git_branch)

    # Check if this directory is actually a git repo before entering the loop
    try:
        watcher.initialise()
    except RuntimeError:
        logger.warning(
            "%s is not a git repository. "
            "Running without git watching — reconcile ran once on startup.",
            ops_path,
        )
        return

    logger.info(
        "Watching %s for changes (polling every %ds).", ops_path, poll_interval
    )

    while True:
        time.sleep(poll_interval)
        try:
            if watcher.has_changes():
                logger.info("Config change detected. Reconciling...")
                app_config_path, sensor_config_paths, sensor_config_dir = _resolve_paths()
                diff = reconcile(
                    app_config_path=app_config_path,
                    sensor_config_paths=sensor_config_paths,
                    ingest_client=ingest_client,
                    sensor_config_dir=sensor_config_dir,
                )
                logger.info(
                    "Reconcile complete. "
                    "started=%s stopped=%s restarted=%s unchanged=%s",
                    list(diff.to_start),
                    diff.to_stop,
                    list(diff.to_restart),
                    diff.unchanged,
                )
        except Exception as exc:
            logger.error("Reconcile failed: %s", exc)
            # Don't crash the loop — log and retry next interval


if __name__ == "__main__":
    main()

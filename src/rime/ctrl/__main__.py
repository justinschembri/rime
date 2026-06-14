"""Entry point for the rime-ctrl service.

Responsibilities:
  1. Cold start: provision FROST and sync ingest transports from config files.
  2. Serve the ctrl web API on CTRL_PORT (default 8002).
  3. Optionally: poll the ops git repo in a background thread and re-reconcile
     whenever new commits arrive (CTRL_GIT_WATCH=true, for pure GitOps mode).

Usage:
    python -m rime.ctrl

Environment variables:
    INGEST_API_URL          URL of the rime-ingest API
                            (default: http://localhost:8001)

    CTRL_HOST               Host to bind the ctrl API server
                            (default: 0.0.0.0)
    CTRL_PORT               Port for the ctrl API server
                            (default: 8002)

    RIME_OPS_PATH           Path to the ops directory (volume-mount or git clone).
                            Must contain application-configs.yml and
                            a sensor_configs/ subdirectory.
                            (default: APPLICATION_CONFIG_FILE's parent)

    APP_CONFIG_FILE         Path to application-configs.yml.
                            (default: <RIME_OPS_PATH>/application-configs.yml)

    SENSOR_CONFIG_PATH      Path to the sensor_configs directory.
                            (default: <RIME_OPS_PATH>/sensor_configs)

    FROST_ENDPOINT          Internal FROST base URL used by the /frost proxy.
                            (default: http://web:8080/FROST-Server/v1.1)

    CREDENTIALS_FILE        Path to application_credentials.json.
                            (default: rime.paths.CREDENTIALS_DIR/application_credentials.json)
    TOKENS_DIR              Directory containing OAuth token JSON files.
                            (default: rime.paths.TOKENS_DIR)

    CTRL_POLL_INTERVAL      Seconds between git polls (default: 60)
    CTRL_GIT_REMOTE         Git remote to pull from (default: origin)
    CTRL_GIT_BRANCH         Git branch to track (default: main)
    CTRL_GIT_WATCH          Set to "true" to enable git polling (for pure GitOps
                            deployments where the container owns the git clone).
                            (default: false — volume-mount mode)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import uvicorn

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
    ops_path_env = os.getenv("RIME_OPS_PATH")
    if ops_path_env:
        ops_path = Path(ops_path_env)
    else:
        from rime.paths import VARIABLE_APPLICATION_CONFIG_FILE
        ops_path = VARIABLE_APPLICATION_CONFIG_FILE.parent

    app_config_env = os.getenv("APP_CONFIG_FILE")
    app_config_path = (
        Path(app_config_env) if app_config_env
        else ops_path / "application-configs.yml"
    )

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

    sensor_config_paths = list({
        p
        for ext in ("*.yml", "*.yaml", "*.YML", "*.YAML")
        for p in sensor_config_dir.rglob(ext)
        if "template" not in p.stem
    })

    logger.info("App config: %s", app_config_path)
    logger.info("Sensor configs: %d file(s) in %s", len(sensor_config_paths), sensor_config_dir)

    return app_config_path, sensor_config_paths, sensor_config_dir


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ingest_url = os.getenv("INGEST_API_URL", "http://localhost:8001")
    ctrl_host = os.getenv("CTRL_HOST", "0.0.0.0")
    ctrl_port = int(os.getenv("CTRL_PORT", "8002"))
    frost_endpoint = os.getenv("FROST_ENDPOINT", "http://web:8080/FROST-Server/v1.1")
    poll_interval = int(os.getenv("CTRL_POLL_INTERVAL", "60"))
    git_remote = os.getenv("CTRL_GIT_REMOTE", "origin")
    git_branch = os.getenv("CTRL_GIT_BRANCH", "main")
    git_watch = os.getenv("CTRL_GIT_WATCH", "false").lower() == "true"

    ingest_client = IngestClient(ingest_url)

    # ------------------------------------------------------------------
    # Cold-start reconcile
    # ------------------------------------------------------------------
    logger.info("rime-ctrl starting. Ingest API: %s", ingest_url)

    app_config_path, sensor_config_paths, sensor_config_dir = _resolve_paths()

    credentials_file_env = os.getenv("CREDENTIALS_FILE")
    _credentials_path = Path(credentials_file_env) if credentials_file_env else None

    tokens_dir_env = os.getenv("TOKENS_DIR")
    _tokens_dir = Path(tokens_dir_env) if tokens_dir_env else None

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
            list(diff.to_start), diff.to_stop,
            list(diff.to_restart), diff.unchanged,
        )
    except Exception as exc:
        logger.error("Cold-start reconcile failed: %s", exc)
        raise

    # ------------------------------------------------------------------
    # Optional git-watch background thread (pure GitOps mode)
    # ------------------------------------------------------------------
    if git_watch:
        ops_path_env = os.getenv("RIME_OPS_PATH")
        ops_path = Path(ops_path_env) if ops_path_env else app_config_path.parent
        watcher = GitWatcher(ops_path, remote=git_remote, branch=git_branch)

        try:
            watcher.initialise()
        except RuntimeError:
            logger.warning(
                "%s is not a git repository. Git watching disabled.", ops_path
            )
        else:
            def _git_watch_loop() -> None:
                logger.info(
                    "Git watch active: polling %s every %ds.", ops_path, poll_interval
                )
                while True:
                    time.sleep(poll_interval)
                    try:
                        if watcher.has_changes():
                            logger.info("Config change detected. Reconciling...")
                            a, s, d = _resolve_paths()
                            reconcile(
                                app_config_path=a,
                                sensor_config_paths=s,
                                ingest_client=ingest_client,
                                sensor_config_dir=d,
                            )
                    except Exception as exc:
                        logger.error("Git-watch reconcile failed: %s", exc)

            t = threading.Thread(target=_git_watch_loop, daemon=True, name="git-watch")
            t.start()

    # ------------------------------------------------------------------
    # Serve the ctrl web API (blocks until the process is stopped)
    # ------------------------------------------------------------------
    from rime.ctrl.api import create_app

    ctrl_app = create_app(
        ingest_client=ingest_client,
        sensor_config_dir=sensor_config_dir,
        app_config_path=app_config_path,
        frost_endpoint=frost_endpoint,
        credentials_path=_credentials_path,
        tokens_dir=_tokens_dir,
    )

    logger.info("rime-ctrl API listening on %s:%d", ctrl_host, ctrl_port)
    uvicorn.run(ctrl_app, host=ctrl_host, port=ctrl_port)


if __name__ == "__main__":
    main()

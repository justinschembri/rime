"""Ctrl-plane reconciler.

Reconcile desired state (config files) against:
  1. FROST Server — provision / patch SensorThings entities.
  2. rime-ingest — start / stop / restart transports via the ingest API.

This module is the *only* place that reads config files and decides what
needs to change.  It calls into FROST and ingest; it never touches transport
threads directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import yaml

from rime.config import get_frost_auth_header, get_frost_root_url
from rime.frost.orchestrators import initial_setup
from rime.sta.extensions import SensorConfig

logger = logging.getLogger("ctrl.reconciler")


# ---------------------------------------------------------------------------
# Config loading helpers
# ---------------------------------------------------------------------------

def load_app_config(config_path: Path) -> dict[str, Any]:
    """Load and return the ``applications`` dict from an application config YAML.

    Args:
        config_path: Path to ``application-configs.yml``.

    Returns:
        The dict under the top-level ``applications`` key.

    Raises:
        ValueError: If the file is missing the ``applications`` key.
    """
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    if "applications" not in raw:
        raise ValueError(f"Missing 'applications' key in {config_path}")
    return raw["applications"]


def load_sensor_configs(sensor_config_paths: list[Path]) -> list[SensorConfig]:
    """Parse and return valid SensorConfig objects from a list of YAML paths."""
    configs = []
    for path in sensor_config_paths:
        sc = SensorConfig(path)
        if sc.is_valid:
            configs.append(sc)
        else:
            logger.warning("Invalid sensor config, skipping: %s", path)
    return configs


# ---------------------------------------------------------------------------
# Diff logic — determines what ingest needs to do
# ---------------------------------------------------------------------------

@dataclass
class TransportDiff:
    """Result of comparing desired vs running application configs."""
    to_start: dict[str, Any] = field(default_factory=dict)    # new apps
    to_stop: list[str] = field(default_factory=list)           # removed apps
    to_restart: dict[str, Any] = field(default_factory=dict)   # changed apps
    unchanged: list[str] = field(default_factory=list)         # no-op apps


def diff_app_configs(
    desired: dict[str, Any],
    running: dict[str, Any],
) -> TransportDiff:
    """Compute what transport changes are needed.

    Args:
        desired: Application config dict from YAML (desired state).
        running: Application config dict currently in use by ingest (actual state).

    Returns:
        A TransportDiff describing what needs to start, stop, or restart.
    """
    result = TransportDiff()
    desired_names = set(desired.keys())
    running_names = set(running.keys())

    result.to_start = {
        name: desired[name]
        for name in desired_names - running_names
    }
    result.to_stop = list(running_names - desired_names)

    for name in desired_names & running_names:
        if desired[name] != running[name]:
            result.to_restart[name] = desired[name]
        else:
            result.unchanged.append(name)

    return result


# ---------------------------------------------------------------------------
# FROST provisioning
# ---------------------------------------------------------------------------

def provision_frost(sensor_configs: list[SensorConfig]) -> None:
    """Idempotently provision all sensor configs as FROST entities.

    Safe to call on every reconcile — entities that already exist are skipped.

    Args:
        sensor_configs: List of valid SensorConfig objects to provision.
    """
    root_url, version = get_frost_root_url()
    auth_headers = get_frost_auth_header()

    for sc in sensor_configs:
        logger.info("Provisioning FROST entities for sensor: %s", sc.name)
        initial_setup(
            sc,
            root_url=root_url,
            version=version,
            auth_headers=auth_headers,
        )


# ---------------------------------------------------------------------------
# Ingest API client
# ---------------------------------------------------------------------------

class IngestClient:
    """Thin HTTP client for the rime-ingest transport API.

    Args:
        base_url: Base URL of the ingest service, e.g. ``http://ingest:8001``.
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def start_transport(self, app_name: str, config: dict[str, Any]) -> None:
        resp = requests.post(
            self._url(f"/transports/{app_name}/start"),
            json={"config": config},
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def stop_transport(self, app_name: str) -> None:
        resp = requests.post(
            self._url(f"/transports/{app_name}/stop"),
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def restart_transport(self, app_name: str, config: dict[str, Any]) -> None:
        resp = requests.post(
            self._url(f"/transports/{app_name}/restart"),
            json={"config": config},
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def get_running_config(self) -> dict[str, Any]:
        """Fetch the currently running application config from ingest status."""
        resp = requests.get(self._url("/transports"), timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # Convert transport status list back to a name-keyed dict
        return {t["app_name"]: t for t in data.get("transports", [])}


# ---------------------------------------------------------------------------
# Main reconcile entry point
# ---------------------------------------------------------------------------

def reconcile(
    app_config_path: Path,
    sensor_config_paths: list[Path],
    ingest_client: IngestClient,
    running_app_config: dict[str, Any] | None = None,
) -> TransportDiff:
    """Full reconciliation pass: provision FROST and sync ingest transports.

    Args:
        app_config_path: Path to ``application-configs.yml``.
        sensor_config_paths: List of sensor YAML file paths.
        ingest_client: Client for the ingest transport API.
        running_app_config: Currently active application config in ingest.
            If None, fetched live from the ingest API (use None in production;
            pass a dict in tests to avoid network calls).

    Returns:
        The TransportDiff that was applied.
    """
    # 1. Load desired state from config files
    desired_app_config = load_app_config(app_config_path)
    sensor_configs = load_sensor_configs(sensor_config_paths)

    # 2. Provision FROST (idempotent)
    provision_frost(sensor_configs)

    # 3. Diff desired vs running transports
    if running_app_config is None:
        running_app_config = ingest_client.get_running_config()

    diff = diff_app_configs(desired_app_config, running_app_config)

    # 4. Apply diff to ingest
    for name, cfg in diff.to_start.items():
        logger.info("Starting transport: %s", name)
        ingest_client.start_transport(name, cfg)

    for name in diff.to_stop:
        logger.info("Stopping transport: %s", name)
        ingest_client.stop_transport(name)

    for name, cfg in diff.to_restart.items():
        logger.info("Restarting transport: %s", name)
        ingest_client.restart_transport(name, cfg)

    if diff.unchanged:
        logger.info("Transports unchanged: %s", diff.unchanged)

    return diff

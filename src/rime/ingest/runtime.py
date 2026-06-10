"""IngestRuntime — lifecycle manager for sensor transport threads.

Owns the set of active SensorTransport connections and the sensor registry.
Exposes fine-grained control methods (start / stop / restart per transport)
that the ingest API and ctrl-plane reconciler call into.

This module intentionally has no knowledge of config files or FROST
provisioning — those are ctrl-plane concerns.  IngestRuntime only knows
about transports and sensors.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rime.monitor import netmon
from rime.providers.registry import PROVIDER_REGISTRY
from rime.sta.extensions import SensorConfig
from rime.transport import SensorTransport
from rime.transformers.types import SensorUUID, SupportedSensors

logger = logging.getLogger("ingest.runtime")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_app_config(app_config: dict[str, Any]) -> set[SensorTransport]:
    """Build transport instances from an already-parsed application config dict.

    Args:
        app_config: The dict under the ``applications`` key of the YAML file.

    Returns:
        Set of SensorTransport instances, one per application entry.

    Raises:
        ValueError: Unknown provider name or missing ``provider`` key.
    """
    connections: set[SensorTransport] = set()
    for app_name, cfg in app_config.items():
        provider_name = cfg.get("provider", "").strip().lower()
        if not provider_name:
            raise ValueError(
                f"Application '{app_name}' is missing required key 'provider'."
            )
        ProviderClass = PROVIDER_REGISTRY.get(provider_name)
        if ProviderClass is None:
            valid = ", ".join(sorted(PROVIDER_REGISTRY))
            raise ValueError(
                f"Unknown provider '{provider_name}' for '{app_name}'. "
                f"Valid: {valid}"
            )
        if not issubclass(ProviderClass, SensorTransport):
            raise ValueError(
                f"{ProviderClass.__name__} is not a SensorTransport subclass."
            )
        connections.add(ProviderClass.from_config(app_name, cfg))
    return connections


def _build_sensor_registry(
    sensor_config_paths: list[Path],
) -> dict[SensorUUID, SupportedSensors]:
    """Parse sensor YAML files and return a sensor UUID → model mapping.

    Invalid sensor configs are logged and skipped.
    """
    registry: dict[SensorUUID, SupportedSensors] = {}
    for path in sensor_config_paths:
        sc = SensorConfig(path)
        if not sc.is_valid:
            logger.warning("Invalid sensor config, skipping: %s", path)
            continue
        registry[sc.name] = SupportedSensors(sc.model)
        netmon.expected_sensors.add(sc.name)
    return registry


# ---------------------------------------------------------------------------
# Status snapshot
# ---------------------------------------------------------------------------

@dataclass
class TransportStatus:
    app_name: str
    is_alive: bool
    push_success: int
    push_fail: int


@dataclass
class RuntimeStatus:
    transports: list[TransportStatus] = field(default_factory=list)
    uptime_seconds: float = 0.0
    expected_sensors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# IngestRuntime
# ---------------------------------------------------------------------------

class IngestRuntime:
    """Manages transport thread lifecycle for the ingest service.

    Typical usage
    -------------
    On cold start (called by ctrl after FROST provisioning)::

        runtime = IngestRuntime()
        runtime.start_all(app_config_dict, sensor_config_paths)

    On config change (called by ctrl API endpoints)::

        runtime.start_transport("new-app", {"provider": "netatmo", ...})
        runtime.stop_transport("removed-app")
        runtime.restart_transport("changed-app", {"provider": "tts", ...})

    On sensor addition (sensor registry update only, no transport restart)::

        runtime.update_sensor_registry(new_sensor_config_paths)
    """

    def __init__(self) -> None:
        # app_name → transport instance
        self._connections: dict[str, SensorTransport] = {}
        # app_name → original config dict (used by ctrl to diff desired vs running)
        self._configs: dict[str, Any] = {}
        self._sensor_registry: dict[SensorUUID, SupportedSensors] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Cold start / full stop
    # ------------------------------------------------------------------

    def start_all(
        self,
        app_config: dict[str, Any],
        sensor_config_paths: list[Path],
    ) -> None:
        """Cold-start: build sensor registry and start all transports.

        Args:
            app_config: Dict of application entries (value of ``applications``
                key from the YAML config).
            sensor_config_paths: List of sensor YAML file paths.
        """
        self._sensor_registry = _build_sensor_registry(sensor_config_paths)
        transports = _parse_app_config(app_config)

        with self._lock:
            for transport in transports:
                transport.start(self._sensor_registry)
                self._connections[transport.app_name] = transport
                self._configs[transport.app_name] = app_config[transport.app_name]
                netmon.connections.add(transport)

        netmon.set_starting_threads(list(self._connections.keys()))
        logger.info(
            "Started %d transport(s): %s",
            len(self._connections),
            list(self._connections.keys()),
        )

    def stop_all(self) -> None:
        """Stop all running transports and clear state."""
        with self._lock:
            for transport in self._connections.values():
                if transport.is_alive:
                    transport.stop()
                    if transport._thread is not None:
                        transport._thread.join(timeout=5)
            self._connections.clear()
            netmon.connections.clear()
        logger.info("All transports stopped.")

    # ------------------------------------------------------------------
    # Per-transport control
    # ------------------------------------------------------------------

    def start_transport(
        self,
        app_name: str,
        app_config_entry: dict[str, Any],
    ) -> None:
        """Start a single new transport.

        Args:
            app_name: Unique application identifier.
            app_config_entry: Config dict for this application (the value
                under ``applications.<app_name>`` in the YAML).

        Raises:
            ValueError: Transport with this name is already running.
        """
        with self._lock:
            if app_name in self._connections and self._connections[app_name].is_alive:
                raise ValueError(f"Transport '{app_name}' is already running.")

        transports = _parse_app_config({app_name: app_config_entry})
        transport = next(iter(transports))

        with self._lock:
            transport.start(self._sensor_registry)
            self._connections[app_name] = transport
            self._configs[app_name] = app_config_entry
            netmon.connections.add(transport)

        logger.info("Started transport: %s", app_name)

    def stop_transport(self, app_name: str) -> None:
        """Stop a running transport.

        Args:
            app_name: Application identifier to stop.

        Raises:
            KeyError: No transport with this name is known.
        """
        with self._lock:
            transport = self._connections.get(app_name)
            if transport is None:
                raise KeyError(f"Unknown transport: '{app_name}'.")
            if transport.is_alive:
                transport.stop()
                if transport._thread is not None:
                    transport._thread.join(timeout=5)
            del self._connections[app_name]
            self._configs.pop(app_name, None)
            netmon.connections.discard(transport)

        logger.info("Stopped transport: %s", app_name)

    def restart_transport(
        self,
        app_name: str,
        app_config_entry: dict[str, Any],
    ) -> None:
        """Stop an existing transport and start it with new config.

        Args:
            app_name: Application identifier to restart.
            app_config_entry: Updated config dict for this application.

        Raises:
            KeyError: No transport with this name is known.
        """
        with self._lock:
            if app_name not in self._connections:
                raise KeyError(f"Unknown transport: '{app_name}'.")

        # stop the old one
        self.stop_transport(app_name)
        # start a fresh one with the new config
        self.start_transport(app_name, app_config_entry)
        logger.info("Restarted transport: %s", app_name)

    # ------------------------------------------------------------------
    # Sensor registry
    # ------------------------------------------------------------------

    def update_sensor_registry(self, sensor_config_paths: list[Path]) -> None:
        """Rebuild the sensor registry from an updated list of config paths.

        Running transports pick up the new registry on their next message
        because they hold a reference to the same dict object.

        Args:
            sensor_config_paths: Updated full list of sensor YAML paths.
        """
        new_registry = _build_sensor_registry(sensor_config_paths)
        with self._lock:
            self._sensor_registry.clear()
            self._sensor_registry.update(new_registry)
            # push the update into every running transport
            for transport in self._connections.values():
                transport.sensor_registry = self._sensor_registry
        logger.info(
            "Sensor registry updated: %d sensor(s).", len(self._sensor_registry)
        )

    # ------------------------------------------------------------------
    # Running config
    # ------------------------------------------------------------------

    def get_running_app_config(self) -> dict[str, Any]:
        """Return the original config dict for every active transport.

        This is what ctrl uses to diff desired state (YAML) against actual
        state (what ingest is currently running), so it must match the shape
        of the application-configs.yml ``applications`` entries exactly.
        """
        with self._lock:
            return dict(self._configs)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> RuntimeStatus:
        """Return a snapshot of current runtime health."""
        import time
        from datetime import datetime

        with self._lock:
            transport_statuses = [
                TransportStatus(
                    app_name=name,
                    is_alive=t.is_alive,
                    push_success=sum(
                        v for k, v in netmon.push_success.items()
                        if str(k).startswith(name)
                    ),
                    push_fail=sum(
                        v for k, v in netmon.push_fail.items()
                        if str(k).startswith(name)
                    ),
                )
                for name, t in self._connections.items()
            ]

        uptime = (datetime.now() - netmon.start_time).total_seconds()

        return RuntimeStatus(
            transports=transport_statuses,
            uptime_seconds=uptime,
            expected_sensors=list(netmon.expected_sensors),
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def transport_names(self) -> list[str]:
        """Names of all known transports (running or stopped)."""
        with self._lock:
            return list(self._connections.keys())

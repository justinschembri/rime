# standard
from typing import List, Optional
import logging
from pathlib import Path
import importlib
import yaml
import time
import threading
import os

# internal
from sensorthings_utils.loggers import setup_loggers  # noqa: F401
from sensorthings_utils.paths import RUNTIME_APPLICATION_CONFIG_FILE
from sensorthings_utils.config import (
    generate_sensor_config_files,
    get_frost_auth_header,
    get_frost_root_url,
)
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.frost.orchestrators import initial_setup
from sensorthings_utils.transport import SensorTransport
from sensorthings_utils.monitor import netmon
from sensorthings_utils.transformers.types import SensorUUID, SupportedSensors


# import from config.py:
setup_loggers()
main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")

def parse_application_config(config_path: Path) -> set[SensorTransport]:
    """
    Parse application YAML config and return set of transport instances.

    Args:
        config_path: Path to the YAML application configuration file

    Returns:
        Set of transport instances.
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    connections = set()
    providers_module = importlib.import_module("sensorthings_utils.providers")

    for app_name, app_config in config["applications"].items():
        class_name = app_config["connection_class"]

        try:
            # `providers_module` exposes every provider class as an attribute
            # via its __init__, so YAML can refer to them by name.
            ProviderClass = getattr(providers_module, class_name)
        except AttributeError:
            raise ValueError(
                f"Provider class '{class_name}' not found in "
                "sensorthings_utils.providers"
            )

        if not issubclass(ProviderClass, SensorTransport):
            raise ValueError(
                f"{class_name} is not a valid SensorTransport subclass"
            )
        connections.add(ProviderClass.from_config(app_name, app_config))

    return connections


def _setup_sensor_arrangements(
    sensor_config: SensorConfig,
    root_url: str,
    version: str,
) -> None:
    """Provision a SensorConfig as FROST entities (idempotent).

    Args:
        sensor_config: Parsed sensor configuration.
        root_url: FROST server root, e.g. ``http://host/FROST-Server``.
        version: SensorThings API version string, e.g. ``"v1.1"``.
    """
    if not sensor_config.is_valid:
        netmon.add_count("sensor_config_fail", 1)
        main_logger.warning(
            f"{sensor_config._filepath} is an invalid sensor configuration file."
        )
        return None

    initial_setup(
        sensor_config,
        root_url=root_url,
        version=version,
        auth_headers=get_frost_auth_header(),
    )


def push_available(
    sensor_config_paths: List[Path] = generate_sensor_config_files(),
    exclude: Optional[List[SensorUUID]] = None,
    frost_endpoint: Optional[str] = None,
    start_delay: int = 30,
) -> None:
    """Start app threads and begin collecting data, pushing to FROST server.

    Args:
        sensor_config_paths: List of sensor configuration file paths.
        exclude: Sensor UUIDs to skip.
        frost_endpoint: Override FROST endpoint (``http://host/FROST-Server/vX.Y``).
            When omitted, ``FROST_ENDPOINT`` env var or the compiled default is used.
        start_delay: Seconds to wait before starting the collection loop.
    """
    if frost_endpoint:
        os.environ["FROST_ENDPOINT"] = frost_endpoint

    root_url, version = get_frost_root_url()
    event_logger.info(
        f"Sensor stream starts in {start_delay}s, target: {root_url}/{version}."
    )
    time.sleep(start_delay)
    # INITIAL SETUP ############################################################
    sensor_registry: dict[SensorUUID, SupportedSensors] = {}
    for f in sensor_config_paths:
        if exclude and f.name in exclude:
            continue
        sensor_config = SensorConfig(f)
        sensor_registry[sensor_config.name] = SupportedSensors(sensor_config.model)
        netmon.expected_sensors.add(sensor_config.name)
        _setup_sensor_arrangements(sensor_config, root_url, version)
    # generate a list of connections
    sensor_connections = parse_application_config(RUNTIME_APPLICATION_CONFIG_FILE)

    netmon.set_starting_threads([_.app_name for _ in sensor_connections])

    for connection in sensor_connections:
        connection.start(sensor_registry)
        # network monitor will be responsible for restarting dead threads:
        netmon.connections.add(connection)

    event_logger.info(
        f"Started {threading.active_count()-1} application threads: "
        + f"{set([i.name for i in threading.enumerate()][1:])}"
    )

    try:
        while True:
            # TODO: network_monitor should write to a metrics file for eventual
            # integration with monitoring tools.
            netmon.report(interval=5)
    except KeyboardInterrupt:
        for conn in sensor_connections:
            if conn.is_alive:
                event_logger.info(f"Stopping thread for {conn.app_name}")
                conn.stop()
                if conn._thread is not None:
                    conn._thread.join(5)

    event_logger.info("Successfully shutdown connections.")
    return None


if __name__ == "__main__":
    push_available()

"""Runtime path configuration for rime-ingest.

External data directories are set via environment variables. In production,
``deploy/`` compose files mount host paths into the container defaults below.
The ingest package does not assume a monorepo layout.
"""

from __future__ import annotations

import os
from pathlib import Path

import dotenv

__all__ = [
    "PACKAGE_DIR",
    "RUNTIME_DIR",
    "LOGS_DIR",
    "DOWNLOADS_DIR",
    "CREDENTIALS_DIR",
    "TOKENS_DIR",
    "SENSOR_CONFIG_PATH",
    "APPLICATION_CONFIG_FILE",
    "DECODERS_DIR",
    "ENV_FILE",
    # Back-compat aliases
    "VARIABLE_SENSOR_CONFIG_PATH",
    "VARIABLE_APPLICATION_CONFIG_FILE",
    "RUNTIME_SENSOR_CONFIG_PATH",
]

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent
_CONTAINER = bool(os.getenv("CONTAINER_ENVIRONMENT"))


def _runtime_path(env_key: str, container_default: str, local_default: Path) -> Path:
    override = os.getenv(env_key)
    if override:
        return Path(override)
    if _CONTAINER:
        return Path(container_default)
    return local_default


RUNTIME_DIR = _runtime_path("RIME_RUNTIME_DIR", "/app/runtime", PACKAGE_DIR / "runtime")
LOGS_DIR = _runtime_path("RIME_LOGS_DIR", "/app/logs", PACKAGE_DIR / "logs")
DOWNLOADS_DIR = _runtime_path(
    "RIME_DOWNLOADS_DIR", "/app/downloads", PACKAGE_DIR / "downloads"
)
CREDENTIALS_DIR = _runtime_path(
    "RIME_CREDENTIALS_DIR",
    "/app/runtime/secrets/credentials",
    RUNTIME_DIR / "secrets" / "credentials",
)
TOKENS_DIR = _runtime_path(
    "RIME_TOKENS_DIR",
    "/app/runtime/secrets/tokens",
    RUNTIME_DIR / "secrets" / "tokens",
)
SENSOR_CONFIG_PATH = _runtime_path(
    "SENSOR_CONFIG_PATH",
    "/app/runtime/sensor_configs",
    RUNTIME_DIR / "sensor_configs",
)
APPLICATION_CONFIG_FILE = _runtime_path(
    "APPLICATION_CONFIG_FILE",
    "/app/runtime/application-configs.yml",
    RUNTIME_DIR / "application-configs.yml",
)
DECODERS_DIR = Path(__file__).parent / "transformers" / "decoders"
ENV_FILE = RUNTIME_DIR / ".env"

dotenv.load_dotenv(ENV_FILE)

# Back-compat aliases used across the codebase
VARIABLE_SENSOR_CONFIG_PATH = SENSOR_CONFIG_PATH
VARIABLE_APPLICATION_CONFIG_FILE = APPLICATION_CONFIG_FILE
RUNTIME_SENSOR_CONFIG_PATH = SENSOR_CONFIG_PATH

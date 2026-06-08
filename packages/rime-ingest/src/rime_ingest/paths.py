"""Runtime path configuration for rime-ingest.

External data directories are set via environment variables. In production,
``deploy/`` compose files mount host paths into the container defaults below.

When developing from the monorepo (``deploy/`` exists next to ``packages/``),
local defaults point at ``deploy/`` so ``rime setup``, ``rime start``, and tests
work without extra env vars. Standalone package installs fall back to
``packages/rime-ingest/runtime/``.
"""

from __future__ import annotations

import os
from pathlib import Path

import dotenv

__all__ = [
    "PACKAGE_DIR",
    "ROOT_DIR",
    "DEPLOY_DIR",
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

# Monorepo root: packages/rime-ingest → packages → repo root
ROOT_DIR = PACKAGE_DIR.parent.parent
_deploy_candidate = ROOT_DIR / "deploy"
DEPLOY_DIR = _deploy_candidate if _deploy_candidate.is_dir() else None


def _local_runtime_base() -> Path:
    """Return deploy/ when developing in the monorepo, else package runtime/."""
    if DEPLOY_DIR and not _CONTAINER:
        return DEPLOY_DIR
    return PACKAGE_DIR / "runtime"


def _runtime_path(env_key: str, container_default: str, local_default: Path) -> Path:
    override = os.getenv(env_key)
    if override:
        return Path(override)
    if _CONTAINER:
        return Path(container_default)
    return local_default


_local = _local_runtime_base()

RUNTIME_DIR = _runtime_path("RIME_RUNTIME_DIR", "/app/runtime", _local)
LOGS_DIR = _runtime_path("RIME_LOGS_DIR", "/app/logs", PACKAGE_DIR / "logs")
DOWNLOADS_DIR = _runtime_path(
    "RIME_DOWNLOADS_DIR", "/app/downloads", PACKAGE_DIR / "downloads"
)
CREDENTIALS_DIR = _runtime_path(
    "RIME_CREDENTIALS_DIR",
    "/app/runtime/secrets/credentials",
    _local / "secrets" / "credentials",
)
TOKENS_DIR = _runtime_path(
    "RIME_TOKENS_DIR",
    "/app/runtime/secrets/tokens",
    _local / "secrets" / "tokens",
)
SENSOR_CONFIG_PATH = _runtime_path(
    "SENSOR_CONFIG_PATH",
    "/app/runtime/sensor_configs",
    _local / "sensor_configs",
)
APPLICATION_CONFIG_FILE = _runtime_path(
    "APPLICATION_CONFIG_FILE",
    "/app/runtime/application-configs.yml",
    _local / "application-configs.yml",
)
DECODERS_DIR = Path(__file__).parent / "transformers" / "decoders"
ENV_FILE = RUNTIME_DIR / ".env"

dotenv.load_dotenv(ENV_FILE)

# Back-compat aliases used across the codebase
VARIABLE_SENSOR_CONFIG_PATH = SENSOR_CONFIG_PATH
VARIABLE_APPLICATION_CONFIG_FILE = APPLICATION_CONFIG_FILE
RUNTIME_SENSOR_CONFIG_PATH = SENSOR_CONFIG_PATH

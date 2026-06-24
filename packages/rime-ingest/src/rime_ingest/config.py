"""Global RIME configuration, including credential management."""

# standard
import json
from pathlib import Path
from collections import defaultdict
from typing import List, Literal
import os
import base64
from functools import lru_cache
import logging
import dotenv
from .paths import (
        RUNTIME_SENSOR_CONFIG_PATH,
        CREDENTIALS_DIR,
        ENV_FILE,
        )

event_logger = logging.getLogger("events")
# ENVIRONMENT  #################################################################
CONTAINER_ENVIRONMENT = bool(os.getenv("CONTAINER_ENVIRONMENT"))
if not os.getenv("CONTAINER_ENVIRONMENT"):
    dotenv.load_dotenv(ENV_FILE)  # docker-compose makes .env redundant


def get_frost_credentials() -> dict[str, str]:
    """Read FROST credentials from Docker secret or local credentials file.
    
    Returns an empty dict if the credentials file does not exist or cannot be
    parsed — callers that need auth will receive None from get_frost_auth_header
    and should omit the Authorization header (anonymous / read-only mode).
    """
    if CONTAINER_ENVIRONMENT:
        secret_file = Path("/run/secrets/frost_credentials")
    else:
        secret_file = CREDENTIALS_DIR / "frost_credentials.json"
    try:
        with open(secret_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}


@lru_cache(maxsize=1)
def get_frost_auth_header(kind: Literal["read", "write"]) -> str | None:
    """Return base64-encoded credentials for FROST authorization headers.
    
    Returns None when credentials are not configured (anonymous mode).
    """
    credentials = get_frost_credentials()
    frost_user = credentials.get(f"frost_{kind}_user")
    frost_password = credentials.get(f"frost_{kind}_password")
    if not frost_user or not frost_password:
        return None
    return base64.b64encode(f"{frost_user}:{frost_password}".encode()).decode("utf-8")


FROST_ROOT_DEFAULT = "http://localhost:8080/FROST-Server"
FROST_VERSION_DEFAULT = "v1.1"
FROST_ENDPOINT_DEFAULT = "http://localhost:8080/FROST-Server/v1.1"


def get_frost_root_url() -> tuple[str, str]:
    """Return ``(root_url, version)`` from environment variables or defaults.

    Resolution order:
    1. ``FROST_ROOT_URL`` + ``FROST_VERSION`` env vars (explicit split form).
    2. ``FROST_ENDPOINT`` env var (legacy combined form, e.g.
       ``http://host/FROST-Server/v1.1``); the trailing ``/vX.Y`` segment is
       split off to derive root and version.
    3. Module-level defaults ``FROST_ROOT_DEFAULT`` / ``FROST_VERSION_DEFAULT``.
    """
    import re
    root = os.getenv("FROST_ROOT_URL")
    version = os.getenv("FROST_VERSION", FROST_VERSION_DEFAULT)
    if root:
        return root, version
    endpoint = os.getenv("FROST_ENDPOINT")
    if endpoint:
        m = re.match(r"^(.*?)/(v[\d.]+)$", endpoint)
        if m:
            return m.group(1), m.group(2)
        return endpoint, version
    return FROST_ROOT_DEFAULT, version


def generate_sensor_config_files() -> List[Path]:
    """
    Return path to yaml configs found in `CONFIG_PATHS`.

    :return: List of all the (non template) yaml or yml files user places in
        `CONFIG_PATHS`
    :rtype: List[Path]
    """
    sensor_configs: List[Path] = []

    # in a container environment we will always want to use the container 
    # deployment directory which

    for f in RUNTIME_SENSOR_CONFIG_PATH.rglob("*.*ml"):
        if "template" not in f.stem:
            sensor_configs.append(f)

    if not sensor_configs:
        raise AttributeError(f"No sensor configs found in {RUNTIME_SENSOR_CONFIG_PATH}.")

    return sensor_configs




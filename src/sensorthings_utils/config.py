"""Global st-utils configuration, including credential management."""

# standard
import json
from pathlib import Path
from typing import List
import os
import base64
from functools import lru_cache
import dotenv
from .paths import (
        RUNTIME_SENSOR_CONFIG_PATH,
        CREDENTIALS_DIR,
        ENV_FILE,
        )
# ENVIRONMENT  #################################################################
CONTAINER_ENVIRONMENT = bool(os.getenv("CONTAINER_ENVIRONMENT"))
if not os.getenv("CONTAINER_ENVIRONMENT"):
    dotenv.load_dotenv(ENV_FILE)  # docker-compose makes .env redundant


def get_frost_credentials() -> tuple[str, str]:
    """Read FROST password from Docker secret or environment variable."""
    if CONTAINER_ENVIRONMENT:
        secret_file = Path("/run/secrets/frost_credentials") 
    else:
        secret_file = CREDENTIALS_DIR / "frost_credentials.json"
    try:
        with open(secret_file, "r") as f:
            credentials = json.load(f)
    except Exception:
        print("Starting stu setup.")
        from .cli.credentials import setup_frost_credentials
        setup_frost_credentials()
        with open(secret_file, "r") as f:
            credentials = json.load(f)

    return (credentials["frost_username"], credentials["frost_password"])


@lru_cache(maxsize=1)
def get_frost_auth_header() -> str:
    """Return base64-encoded credentials for FROST authorization headers."""
    frost_user, frost_password = get_frost_credentials()
    return base64.b64encode(f"{frost_user}:{frost_password}".encode()).decode("utf-8")


FROST_ROOT_DEFAULT = "http://localhost:8080/FROST-Server"
FROST_VERSION_DEFAULT = "v1.1"
FROST_ENDPOINT_DEFAULT = "http://localhost:8080/FROST-Server/v1.1"


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




"""FROST interaction helpers."""
#standard
import logging
#external
import requests

from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
#internal
from .types import FrostEndpoints, FrostVersions
#logging

event_logger = logging.getLogger("events")

def check_frost_connection(
        root_url:str = FROST_ROOT_DEFAULT,
        version:str = FROST_VERSION_DEFAULT
        ) -> bool:
    """Check connectivity and accessibility of a FROST srever instance."""

    root_url = root_url.rstrip("/")
    version = version.lstrip("v")
    ver = FrostVersions(version)

    base_url = root_url + "/v" + ver.value
    try:
        for endpoint in FrostEndpoints:
            url = base_url + endpoint.value    
            response = requests.get(url)
            response.raise_for_status()
    except Exception as e:
        event_logger.critical(f"FROST Connection failed: {e} for {base_url}.")
        return False

    event_logger.info(f"FROST read connectivity confirmed at {base_url}")
    return True



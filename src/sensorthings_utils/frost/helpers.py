"""FROST interaction helpers."""
#standard
import logging
#external
import requests
#internal
from .types import FrostEndpoints, FrostVersions
from .errors import FrostConnectionError
#logging

event_logger = logging.getLogger("events")

def _check_frost_connection(root_url:str, version:str) -> bool:
    """Check connectivity and accessibility of a FROST srever instance."""

    root_url = root_url.rstrip("/")
    version = version.lstrip("v")
    v = FrostVersions(version)

    base_url = root_url + "/v" + v.value
    try:
        for endpoint in FrostEndpoints:
            url = base_url + endpoint.value    
            response = requests.get(url)
            response.raise_for_status()
    except Exception as e:
        raise FrostConnectionError(e, base_url) from None

    event_logger.info(f"FROST read connectivity confirmed at {base_url}")
    return True


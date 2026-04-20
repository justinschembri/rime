"""Execute POST requests with local or external FROST servers."""

# standard
import json
from typing import Any, Mapping

# external
import requests

from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from sensorthings_utils.frost import UrlStr
from sensorthings_utils.frosty.types import FrostVersions
from sensorthings_utils.sensor_things.core import Observation, SensorThingsObject

# internal
from .errors import FrostRequestError


def _general_post(
    url: str,
    payload: Mapping[str, Any] | str,
    *,
    auth_headers: str | None = None,
    content_type: str = "application/json",
) -> requests.Response:
    """
    Execute a POST request against a FROST endpoint.

    Accepts structured payloads (mapping/list) and serializes them to JSON bytes.
    String payloads are UTF-8 encoded directly.
    """
    request_data = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": content_type}
    if auth_headers:
        headers["Authorization"] = f"Basic {auth_headers}"

    try:
        response = requests.post(url=url, data=request_data, headers=headers)
        response.raise_for_status()
        return response
    except Exception as exc:
        raise FrostRequestError(exc, url)

def make_frost_entity(
        payload: Mapping[str, Any] | SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        ) -> UrlStr:
    ...

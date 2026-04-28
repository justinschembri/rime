"""Execute POST requests with local or external FROST servers."""

# standard
import json
from typing import Any, Mapping
import logging
# external
import requests
from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from sensorthings_utils.frosty.bridges import ENTITY_TO_FROST_ENDPOINT
from sensorthings_utils.frosty.helpers import check_object_existence
from sensorthings_utils.frosty.sanitization import sanitize_root_url
from sensorthings_utils.frosty.types import FrostUrl
from sensorthings_utils.sensor_things.core import Observation, SensorThingsObject

# internal
from .errors import FrostRequestError

main_logger = logging.getLogger("main")

def general_post(
    url: str,
    payload: SensorThingsObject | Observation | Mapping[str, Any] | str,
    *,
    auth_headers: str | None = None,
    content_type: str = "application/json",
) -> FrostUrl:
    """
    Execute a native POST request against a FROST endpoint.

    Accepts structured payloads (mapping/list) and serializes them to JSON bytes.
    String payloads are UTF-8 encoded directly.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, (SensorThingsObject, Observation)):
        payload = payload.as_frost_entity()
    request_payload = json.dumps(payload).encode("utf-8")
    # checks: linked objects
    # observation: datastream required field
    headers = {"Content-Type": content_type}
    if auth_headers:
        headers["Authorization"] = f"Basic {auth_headers}"

    try:
        response = requests.post(url=url, data=request_payload, headers=headers)
        response.raise_for_status()
        return response.headers["Location"]
    except Exception as exc:
        raise FrostRequestError(exc, url)

def make_frost_entity(
        st_object: SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> FrostUrl | None:
        root_url, version = sanitize_root_url(root_url, version)
        if check_object_existence(st_object, root_url, version):
            main_logger.info(
                    f"Creation skipped: {st_object.entity_type.value} exists."
                    )
            return None
        endpoint = ENTITY_TO_FROST_ENDPOINT[st_object.entity_type].value
        url = f"{root_url}/v{version}{endpoint}"
        response = general_post(url, st_object, auth_headers=auth_headers)
        return response



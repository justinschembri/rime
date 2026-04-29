"""Execute POST requests with local or external FROST servers."""

# standard
import json
import logging
from datetime import datetime, date
from typing import Any, Mapping, Optional
# external
import requests
from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT, get_frost_auth_header, get_frost_root_url
from sensorthings_utils.frost.bridges import ENTITY_TO_FROST_ENDPOINT
from sensorthings_utils.frost.helpers import check_object_existence
from sensorthings_utils.frost.sanitization import rewrite_to_internal, sanitize_root_url
from sensorthings_utils.frost.types import FrostEntityRef, FrostUrl
from sensorthings_utils.sensor_things.core import Observation, SensorThingsObject
from sensorthings_utils.transformers.types import ObservedProperties, SensorUUID

# internal
from .errors import FrostRequestError

main_logger = logging.getLogger("main")


def _json_default(obj: Any) -> str:
    """Fallback JSON serializer for types stdlib json cannot handle."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def general_post(
    url: str,
    payload: SensorThingsObject | Observation | Mapping[str, Any] | str,
    *,
    auth_headers: str | None = None,
    content_type: str = "application/json",
) -> FrostEntityRef:
    """
    Execute a native POST request against a FROST endpoint.

    Accepts structured payloads (mapping/list) and serializes them to JSON bytes.
    String payloads are UTF-8 encoded directly.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, (SensorThingsObject, Observation)):
        payload = payload.as_frost_entity()
    request_payload = json.dumps(payload, default=_json_default).encode("utf-8")
    # checks: linked objects
    # observation: datastream required field
    headers = {"Content-Type": content_type}
    if auth_headers:
        headers["Authorization"] = f"Basic {auth_headers}"

    try:
        response = requests.post(url=url, data=request_payload, headers=headers)
        response.raise_for_status()
        return FrostEntityRef.from_frost_url(response.headers["Location"])
    except requests.HTTPError as exc:
        response_text = exc.response.text if exc.response is not None else ""
        detail = f"{exc} - response body: {response_text}"
        raise FrostRequestError(detail, url)
    except Exception as exc:
        raise FrostRequestError(exc, url)

def make_frost_entity(
    st_object: SensorThingsObject | Observation,
    root_url: str = FROST_ROOT_DEFAULT,
    version: str | float | int = FROST_VERSION_DEFAULT,
    auth_headers: Optional[str] = None,
    *,
    endpoint: Optional[FrostUrl] = None,
) -> FrostEntityRef:
    root_url, version = sanitize_root_url(root_url, version)
    existing_entity = check_object_existence(st_object, root_url, version)
    if existing_entity:
        main_logger.info(
            f"Skipping creation {st_object} exists at: {existing_entity}"
        )
        return existing_entity
    endpoint_tail = ENTITY_TO_FROST_ENDPOINT[st_object.entity_type].value
    if not endpoint:
        post_url = f"{root_url}/v{version}{endpoint_tail}"
    else:
        endpoint = rewrite_to_internal(endpoint, root_url)
        post_url = f"{endpoint}{endpoint_tail}"
    response = general_post(post_url, st_object, auth_headers=auth_headers)
    return response


def frost_observation_upload(
        sensor_name: SensorUUID,
        observation_set: tuple[Observation, ObservedProperties],
        root_url: str | None = None,
        version: str | None = None,
        auth_headers: Optional[str] = None,
) -> FrostEntityRef:
    """Upload a single Observation to the matching Datastream on the FROST server.

    Uses ``make_frost_entity`` internally, so duplicate observations (e.g. from
    a pull-model connection returning the same payload twice) are silently
    skipped rather than re-posted.

    ``root_url`` and ``version`` default to whatever ``get_frost_root_url()``
    returns (env-var aware), so callers that set ``FROST_ENDPOINT`` do not need
    to pass them explicitly.
    """
    # Deferred import: get.py imports helpers.py, which imports this module.
    from sensorthings_utils.frost.get import find_datastream_observations_url
    _root, _version = get_frost_root_url()
    root_url = root_url or _root
    version = version or _version
    auth_headers = auth_headers or get_frost_auth_header()

    observation, datastream_name = observation_set
    observations_url = find_datastream_observations_url(
        sensor_name, datastream_name, root_url, version
    )
    if not observations_url:
        raise FrostRequestError(
            f"Datastream '{datastream_name}' not found for sensor '{sensor_name}'.",
            f"{root_url}/v{version}/Sensors",
        )
    return make_frost_entity(
        observation,
        root_url=root_url,
        version=version,
        auth_headers=auth_headers,
        endpoint=observations_url,
    )



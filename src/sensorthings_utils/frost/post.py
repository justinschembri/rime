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
    """Fallback serializer passed to ``json.dumps`` for non-standard types.

    Currently handles ``datetime`` and ``date`` by converting them to ISO 8601
    strings. All other types raise ``TypeError``.

    Args:
        obj: Object that the standard JSON encoder could not serialize.

    Returns:
        ISO 8601 string for date/datetime objects.

    Raises:
        TypeError: For any type that is not explicitly handled.
    """
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
    """POST a payload to a FROST endpoint and return the created entity reference.

    Accepts domain objects, mappings, or raw JSON strings and normalises them
    before sending. The ``Location`` header from the 201 response is parsed into
    a typed ``FrostEntityRef``.

    Args:
        url: Full endpoint URL to POST to.
        payload: Entity to create. ``SensorThingsObject`` / ``Observation``
            instances are serialised via ``as_frost_entity()``; strings are
            parsed as JSON; mappings are used directly.
        auth_headers: Base64-encoded credentials for the ``Authorization``
            header. Omit when the server requires no auth.
        content_type: MIME type for the request body.

    Returns:
        ``FrostEntityRef`` parsed from the response ``Location`` header.

    Raises:
        FrostRequestError: On HTTP errors (includes response body) or any other
            connection failure.
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
    """Create a SensorThings entity on FROST, skipping it if it already exists.

    Checks for an equivalent entity via ``check_object_existence`` before
    POSTing. When ``endpoint`` is supplied the URL is rewritten to the internal
    root before use, allowing correct behaviour in containerised deployments.

    Args:
        st_object: The domain object to create.
        root_url: FROST server root URL, without the version segment.
        version: API version.
        auth_headers: Base64-encoded credentials for the ``Authorization``
            header.
        endpoint: Override the default collection URL (e.g. to post an
            Observation directly to a Datastream's navigation link).

    Returns:
        Reference to the existing or newly created entity.
    """
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
    """Upload a single Observation to the appropriate Datastream on FROST.

    Resolves the correct ``Observations`` navigation URL from the sensor and
    datastream names, then delegates to ``make_frost_entity``, which silently
    skips duplicates. Connection config defaults to env-var values so callers
    that set ``FROST_ENDPOINT`` do not need to pass them explicitly.

    Args:
        sensor_name: Unique name of the sensor that owns the datastream.
        observation_set: Tuple of ``(Observation, datastream_name)`` produced
            by a transformer.
        root_url: FROST server root URL. Defaults to ``FROST_ENDPOINT`` env var.
        version: API version. Defaults to ``FROST_VERSION`` env var.
        auth_headers: Base64-encoded credentials. Defaults to
            ``FROST_AUTH_HEADER`` env var.

    Returns:
        Reference to the existing or newly created Observation entity.

    Raises:
        FrostRequestError: When no matching Datastream is found for the given
            sensor/datastream name pair, or on any HTTP error.
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



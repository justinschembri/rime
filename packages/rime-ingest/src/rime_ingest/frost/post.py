"""Execute POST requests with local or external FROST servers."""

# standard
import json
import logging
from datetime import datetime, date
from typing import Any, Mapping, Optional
# external
import requests
from rime_ingest.config import FROST_ROOT_DEFAULT, FROST_VERSION, get_frost_auth_header, get_frost_root_url
from rime_ingest.frost.bridges import ENTITY_TO_FROST_ENDPOINT
from rime_ingest.frost.helpers import check_object_existence
from rime_ingest.frost.sanitization import rewrite_to_internal, sanitize_root_url
from rime_ingest.frost.types import FrostEntityRef, FrostUrl, FrostVersions
from rime_ingest.sta.core import Observation, SensorThingsObject
from rime_ingest.transformers.types import SensorUUID

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
    version: str | float | int | FrostVersions = FROST_VERSION,
    read_auth_headers: Optional[str] = None,
    write_auth_headers: Optional[str] = None,
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
        endpoint: Override the default collection URL (e.g. parent Thing URL for
            a Location, or Datastream URL for an Observation — ``make_frost_entity``
            appends the plural segment for ``st_object.entity_type``).

    Returns:
        Reference to the existing or newly created entity.
    """
    root_url, version = sanitize_root_url(root_url, version)
    existing_entity = check_object_existence(
        st_object, root_url, version, auth_headers=read_auth_headers
    )
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
    response = general_post(post_url, st_object, auth_headers=write_auth_headers)
    return response


def frost_observation_upload(
        sensor_name: SensorUUID,
        observation_set: tuple[Observation, str],
        root_url: str | None = None,
        version: str | None = None,
        read_auth_headers: Optional[str] = None,
        write_auth_headers: Optional[str] = None,
) -> FrostEntityRef:
    """Upload a single Observation to the appropriate Datastream on FROST.

    Resolves the Datastream entity URL from the sensor and datastream names,
    then delegates to ``make_frost_entity``, which appends ``/Observations`` and
    silently skips duplicates. Connection config defaults to env-var values so callers
    that set ``FROST_ENDPOINT`` do not need to pass them explicitly.

    Args:
        sensor_name: Unique name of the sensor that owns the datastream.
        observation_set: Tuple of ``(Observation, datastream_name_str)``
            produced by a transformer (``datastream`` is the ``.value`` of an
            ``ObservedProperties`` enum member, i.e. a plain string).
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
    from rime_ingest.frost.get import find_datastream_observations_url
    _root, _version = get_frost_root_url()
    root_url = root_url or _root
    version = version or _version
    write_auth = write_auth_headers or get_frost_auth_header("write")
    read_auth = read_auth_headers or get_frost_auth_header("read")

    observation, datastream_name = observation_set
    datastream_url = find_datastream_observations_url(
        sensor_name, datastream_name, root_url, version, auth_headers=read_auth
    )
    if not datastream_url:
        raise FrostRequestError(
            f"Datastream '{datastream_name}' not found for sensor '{sensor_name}'.",
            f"{root_url}/v{version}/Sensors",
        )
    return make_frost_entity(
        observation,
        root_url=root_url,
        version=version,
        read_auth_headers=read_auth,
        write_auth_headers=write_auth,
        endpoint=datastream_url,
    )



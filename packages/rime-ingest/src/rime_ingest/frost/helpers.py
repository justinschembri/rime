"""FROST interaction helpers."""
#standard
import logging

from rime_ingest.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from rime_ingest.frost.get import frost_entity_lookup, frost_object_lookup, general_frost_get
from rime_ingest.frost.sanitization import sanitize_root_url
from rime_ingest.sta.core import Datastream, Observation, SensorThingsObject, UnLinkedSensorThingsObjects
from rime_ingest.sta.schema import SensorThingsEntity, SensorThingsEntityGroups
#internal
from .odata import ODataParams, odata_filter_name_eq
from .types import FrostEndpoints, FrostEntityRef
#logging

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")

def check_frost_connection(
        root_url:str = FROST_ROOT_DEFAULT,
        version:str = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> bool:
    """Probe every FROST entity endpoint to verify read connectivity.

    Performs a GET against each endpoint in ``FrostEndpoints`` and logs the
    outcome. Intended as a startup preflight check.

    Args:
        root_url: FROST server root URL, without the version segment.
        version: API version.
        auth_headers: Base64-encoded credentials for the ``Authorization`` header.

    Returns:
        ``True`` when all endpoints respond with a 2xx status;
        ``False`` on any connection or HTTP error.
    """
    root_url, version = sanitize_root_url(root_url, version)
    base_url = f"{root_url}/v{version}"
    try:
        for endpoint in FrostEndpoints:
            url = base_url + endpoint.value
            general_frost_get(url, auth_headers=auth_headers)
    except Exception as e:
        event_logger.critical(f"FROST Connection failed: {e} for {base_url}.")
        return False

    event_logger.info(f"FROST read connectivity confirmed at {base_url}")
    return True

def _check_unlinked_object_exists(
        st_object: UnLinkedSensorThingsObjects,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> None | FrostEntityRef:
    """Check whether an unlinked SensorThings object exists on the FROST server.

    Compares content fields via ``partial_eq``, which ignores ``id``, ``links``,
    and ``iot_links``. Not intended for ``Datastream`` or ``Observation``
    objects; ``check_object_existence`` dispatches those to dedicated checkers.

    Args:
        st_object: The unlinked object to search for (e.g. a ``Thing``,
            ``Sensor``, or ``ObservedProperty``).
        root_url: FROST server root URL, without the version segment.
        version: API version.

    Returns:
        A ``FrostEntityRef`` for the first matching entity, or ``None`` when no
        match is found. Logs a warning when more than one candidate exists.
    """
    response = frost_object_lookup(st_object, root_url, version, auth_headers=auth_headers)
    if not response:
        return None
    cls = type(st_object)
    matches: list[FrostEntityRef] = []
    for r in response:
        if st_object.partial_eq(cls.from_frost_entity(r)):
            matches.append(FrostEntityRef.from_frost_url(r["@iot.selfLink"]))
    if len(matches) > 1:
        main_logger.warning(
            f"Found more than one candidate match for {st_object}. "
            "Consider squashing database duplicates. Returned first match."
        )
    if matches:
        return matches[0]
    return None

def _check_datastream_object_exists(
        st_datastream: Datastream,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> None | FrostEntityRef:
    """Check whether a content-equivalent Datastream with its linked Sensor exists.

    Matches on both the Datastream's own fields (via ``partial_eq``) and its
    linked Sensor, using OData ``$expand=Sensor($select=name)`` because the
    singular ``/Datastreams({id})/Sensor`` relationship cannot be navigated via
    ``sanitize_get_request``.

    When ``iot_links[Sensors][0]`` is a ``FrostEntityRef`` (post-attach), the
    Sensor is matched by ``@iot.id``; when it is a plain string (pre-attach,
    from YAML), it is matched by name.

    Args:
        st_datastream: The Datastream to search for.
        root_url: FROST server root URL, without the version segment.
        version: API version.

    Returns:
        A ``FrostEntityRef`` for the matching Datastream, or ``None``.

    Raises:
        ValueError: If ``st_datastream.iot_links[Sensors]`` is missing or
            malformed.
    """
    # Invariant: Datastream has exactly one linked Sensor. We cannot check if
    # a datastream exists without this link.
    # iot_links[SENSORS][0] is either a name str (pre-attach, from YAML) or a
    # FrostEntityRef (post-attach). Extract a string name for comparison.
    sensor_bucket = (st_datastream.iot_links or {}).get(SensorThingsEntityGroups.SENSORS)
    if not sensor_bucket or not isinstance(sensor_bucket, list):
        raise ValueError(
            f"Datastream '{st_datastream.name}' is missing iot_links[Sensors]."
        )
    sensor_entry = sensor_bucket[0]
    if isinstance(sensor_entry, FrostEntityRef):
        sensor_name = sensor_entry.iot_id  # matched by @iot.id in expanded Sensor
        expand_select = f"Sensor($select=@iot.id,name)"
    else:
        sensor_name = sensor_entry  # plain name string from YAML
        expand_select = "Sensor($select=name)"

    matches = frost_entity_lookup(
        first_entity=SensorThingsEntity.DATASTREAM,
        root_url=root_url,
        version=version,
        params={
            ODataParams.FILTER: odata_filter_name_eq(st_datastream.name),
            ODataParams.EXPAND: expand_select,
        },
        auth_headers=auth_headers,
    )
    if not matches:
        return None

    for match in matches:
        candidate = Datastream.from_frost_entity(match)
        if not st_datastream.partial_eq(candidate):
            continue
        linked_sensor = match.get("Sensor") or {}
        if isinstance(sensor_entry, FrostEntityRef):
            if linked_sensor.get("@iot.id") == sensor_name:
                return FrostEntityRef.from_frost_url(match["@iot.selfLink"])
        else:
            if linked_sensor.get("name") == sensor_name:
                return FrostEntityRef.from_frost_url(match["@iot.selfLink"])

    return None

def _check_observation_object_exists(
        st_observation: Observation,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> None | FrostEntityRef:
    """Check whether a content-equivalent Observation exists on the FROST server.

    Matches on all observation content fields (``phenomenonTime``,
    ``resultTime``, ``result``, ``validTime``) via ``partial_eq``, so two
    observations at the same instant but with different ``result`` values are
    correctly treated as distinct.

    Args:
        st_observation: The Observation to search for.
        root_url: FROST server root URL, without the version segment.
        version: API version.

    Returns:
        A ``FrostEntityRef`` for the first matching entity, or ``None``.
    """
    #TODO: test the real robustness of this function!
    matches = frost_object_lookup(st_observation, root_url, version, auth_headers=auth_headers)
    if not matches:
        return None
    for match in matches:
        if st_observation.partial_eq(Observation.from_frost_entity(match)):
            return FrostEntityRef.from_frost_url(match["@iot.selfLink"])
    return None

def check_object_existence(
        st_object: SensorThingsObject | Observation,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> None | FrostEntityRef:
    """Route an existence check to the appropriate type-specific checker.

    Dispatches to ``_check_datastream_object_exists``,
    ``_check_observation_object_exists``, or
    ``_check_unlinked_object_exists`` based on the runtime type of
    ``st_object``.

    Args:
        st_object: The domain object to look up on the server.
        root_url: FROST server root URL, without the version segment.
        version: API version.
        auth_headers: Base64-encoded credentials for the ``Authorization`` header.

    Returns:
        A ``FrostEntityRef`` when a matching entity exists, otherwise ``None``.

    Raises:
        ValueError: For unsupported object types.
    """

    if isinstance(st_object, Datastream):
        return _check_datastream_object_exists(
            st_object, root_url, version, auth_headers=auth_headers
        )
    elif isinstance(st_object, Observation):
        return _check_observation_object_exists(
            st_object, root_url, version, auth_headers=auth_headers
        )
    elif isinstance(st_object, UnLinkedSensorThingsObjects):
        return _check_unlinked_object_exists(
            st_object, root_url, version, auth_headers=auth_headers
        )
    else:
        raise ValueError(f"Received unexpected object type: {type(st_object)}")


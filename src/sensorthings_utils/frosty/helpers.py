"""FROST interaction helpers."""
#standard
import logging
#external
import requests

from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from sensorthings_utils.frosty.get import frost_entity_lookup, frost_object_lookup
from sensorthings_utils.sensor_things.core import Datastream, Observation, SensorThingsObject, UnLinkedSensorThingsObjects
from sensorthings_utils.sensor_things.schema import SENSOR_THINGS_ENTITY_FIELDS, SensorThingsEntity
#internal
from .types import FrostEndpoints, FrostEntityRef, FrostParams, FrostVersions
#logging

main_logger = logging.getLogger("main")
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

def _check_unlinked_object_exists(
        st_object: UnLinkedSensorThingsObjects,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> None | FrostEntityRef:
    """
    Check if an unlinked SensorThings object exists in a given FROST instance.

    Compares content fields via `partial_eq` (ignores `id`, `links`,
    `iot_links`). Should not be used for Datastream or Observation objects;
    `check_object_existence` dispatches those to dedicated checkers.
    """
    response = frost_object_lookup(st_object, root_url, version, object_fields_only=False)
    if not response:
        return None
    cls = type(st_object)
    for r in response:
        candidate_matches = 0
        if st_object.partial_eq(cls.from_frost_entity(r)):
            candidate_matches += 1
        if candidate_matches > 1:
            main_logger.warning(
                    f"Found more than one candidate match for {st_object}"
                    "Consider squashing database duplicates. Returned last match."
                    )
        if candidate_matches:
            url = r["@iot.selfLink"]
            return FrostEntityRef.from_frost_url(url)
    return None

def _check_datastream_object_exists(
        st_datastream: Datastream,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> bool:
    """Check whether a Datastream with matching content and linked Sensor exists.

    Matches both on the Datastream's own content (via `partial_eq`) and on
    the linked Sensor's name. Uses OData `$expand=Sensor($select=name)`
    because `/Datastreams({id})/Sensor` (singular) cannot be reached via
    the plural-only `sanitize_get_request` helper.
    """
    # Invariant: Datastream has exactly one linked Sensor.
    sensor = st_datastream.links[SensorThingsEntity.SENSOR][0]

    content_fields = SENSOR_THINGS_ENTITY_FIELDS[SensorThingsEntity.DATASTREAM]
    matches = frost_entity_lookup(
        first_entity=SensorThingsEntity.DATASTREAM,
        root_url=root_url,
        version=version,
        params={
            FrostParams.SELECT: ",".join(("@iot.id", *content_fields)),
            FrostParams.FILTER: f"name eq '{st_datastream.name}'",
            FrostParams.EXPAND: "Sensor($select=name)",
        },
    )
    if not matches:
        return False

    for match in matches:
        candidate = Datastream.from_frost_entity(match)
        if not st_datastream.partial_eq(candidate):
            continue
        linked_sensor = match.get("Sensor") or {}
        if linked_sensor.get("name") == sensor.name:
            return True

    return False

def _check_observation_object_exists(
        st_observation: Observation,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> bool:
    """
    Check if an Observation with matching content exists on the FROST server.

    Matches on the content fields enumerated in
    `SENSOR_THINGS_ENTITY_FIELDS[OBSERVATION]` (phenomenonTime, resultTime,
    result, validTime) rather than just phenomenonTime, so that two
    observations at the same instant but with different `result` values are
    correctly treated as different.
    """
    #TODO: test the real robustness of this function!
    matches = frost_object_lookup(st_observation, root_url, version, object_fields_only=True)
    if not matches:
        return False
    for match in matches:
        if st_observation.partial_eq(Observation.from_frost_entity(match)):
            return True
    return False

def check_object_existence(
        st_object: SensorThingsObject | Observation,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> bool:

    if isinstance(st_object, Datastream):
        return _check_datastream_object_exists(st_object, root_url, version)
    elif isinstance(st_object, Observation):
        return _check_observation_object_exists(st_object, root_url, version)
    elif isinstance(st_object, UnLinkedSensorThingsObjects):
        return _check_unlinked_object_exists(st_object, root_url, version)
    else:
        raise ValueError(f"Received unexpected object type: {type(st_object)}")


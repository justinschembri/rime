"""Execute GET requests with local or external FROST servers."""
#standard
from datetime import datetime
from collections.abc import Iterator
#external
#internal
import json
from typing import Optional, Mapping, Any, Literal, overload

import requests
from sensorthings_utils.config import (
    FROST_ROOT_DEFAULT,
    FROST_VERSION_DEFAULT,
)
from .errors import FrostRequestError
from .sanitization import (
    merge_filter,
    merge_order_by,
    sanitize_request,
    to_odata_datetime,
)
from .types import FrostParams, FrostResultPageIterator, FrostVersions
from sensorthings_utils.sensor_things.core import (
        Datastream,
        Observation,
        SensorThingsObject, 
        UnLinkedSensorThingsObjects, 
        )
from sensorthings_utils.sensor_things.schema import (
    SENSOR_THINGS_ENTITY_FIELDS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)


def _general_request(
        url, 
        params: Optional[Mapping[str | FrostParams, Any]] = None
        ) -> dict[str, Any]:
    response = requests.get(url, params=params) #type: ignore
    response.raise_for_status()
    json_response = response.json() 
    return json_response

@overload
def frost_entity_lookup(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        as_generator: Literal[True] = True,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
        ) -> FrostResultPageIterator | None:
    ...

@overload
def frost_entity_lookup(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        as_generator: Literal[False],
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
        ) -> list[dict[str, Any]] | None:
    ...

def frost_entity_lookup(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        as_generator: bool = True,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = ""
        ) -> FrostResultPageIterator | list[dict[str, Any]] | None:
    """
    Query a FROST server and return data as a dict object.
    
    This is a general querying tool for FROST over HTTP. Entity names and param
    keys are checked but parameter values are not.

    Args:
        root_url: the FROST url **without** the version,
        version: the FROST server version,
        first_entity: the type of the first entity you want, must be a 
            SensorThingsEntityGroups enum (e.g., Things, Sensors, Datastreams)
        params: optional OData params, must be FrostParams.
        first_entity_id: If you want to query the entity which is related to 
            another one, you must supply the ID of the first entity.
        second_entity: the child entity you're looking for. For example, if you
            want the Locations of Things(1), the first entity would be Things
            and the second would be Locations.

        as_generator: if True, return an iterator over pages; if False, return
            one merged list from all `value` pages.

    Returns:
        - Generator mode: iterator over each FROST `value` page.
        - List mode: one merged list from `value`.
        - None: when no results are returned.
    """

    url, params = sanitize_request(
        root_url=root_url,
        version=version,
        first_entity=first_entity,
        params=params,
        first_entity_id=first_entity_id,
        second_entity=second_entity,
    )
    try:
        response = _general_request(url, params)
        if not response["value"]:
            return None

        def _iter_pages(initial_response: dict[str, Any]) -> Iterator[list[dict[str, Any]]]:
            current_response = initial_response
            while True:
                page = current_response.get("value")
                if not isinstance(page, list):
                    raise TypeError("Expected FROST page response to contain list `value`.")
                yield page

                next_link = current_response.get("@iot.nextLink")
                if not next_link:
                    break
                current_response = _general_request(next_link)

        page_iterator = _iter_pages(response)
        if as_generator:
            return page_iterator

        data: list[dict[str, Any]] = []
        for page in page_iterator:
            data.extend(page)
        return data
    except Exception as e:
        raise FrostRequestError(e, url)

def frost_object_lookup(
        st_object: SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        *,
        as_generator: bool = True,
        ) -> FrostResultPageIterator | list[dict[str, Any]] | None:
    """Lookup up an equivalent SensorThingsObject in a FROST instance."""

    if isinstance(st_object, Observation):
        filter_string = f"phenomenonTime eq {st_object.phenomenonTime}"
    elif isinstance(st_object, SensorThingsObject):
        filter_string = f"name eq '{st_object.name}'"

    entity = SensorThingsEntity(st_object.as_entity)
    params = {
            FrostParams.SELECT:",".join(SENSOR_THINGS_ENTITY_FIELDS[entity]),
            FrostParams.FILTER:filter_string
            }

    response = frost_entity_lookup(
            entity,
            root_url=root_url,
            version=version,
            params=params,
            as_generator=as_generator
            )

    if not response:
        return None

    return response


def get_frost_datastream_observations(
        datastream_id: int | str,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        verbose: bool = False,
        *,
        time_start: Optional[datetime | str] = None,
        time_end: Optional[datetime | str] = None,
        result_min: Optional[int | float] = None,
        result_max: Optional[int | float] = None,
        result_eq: Optional[int | float] = None,
        order_by: Optional[str] = "phenomenonTime",
        descending: bool = True,
        ) -> list[dict[str, Any]]:
    """
    Query `Datastreams(<id>)/Observations` with optional convenience filters.

    All filter helper arguments are optional.
    """

    params_map: dict[str, Any] = {}
    if not verbose:
        params_map["$select"] = "@iot.id,phenomenonTime,resultTime,result"

    filter_clauses: list[str] = []
    if time_start is not None:
        filter_clauses.append(f"phenomenonTime ge {to_odata_datetime(time_start)}")
    if time_end is not None:
        filter_clauses.append(f"phenomenonTime le {to_odata_datetime(time_end)}")
    if result_min is not None:
        filter_clauses.append(f"result ge {result_min}")
    if result_max is not None:
        filter_clauses.append(f"result le {result_max}")
    if result_eq is not None:
        filter_clauses.append(f"result eq {result_eq}")

    if filter_clauses:
        params_map = merge_filter(params_map, " and ".join(filter_clauses))
    params_map = merge_order_by(params_map, order_by=order_by, descending=descending)

    lookup_result = frost_entity_lookup(
        root_url=root_url,
        version=version,
        first_entity=SensorThingsEntityGroups.DATASTREAMS,
        first_entity_id=datastream_id,
        second_entity=SensorThingsEntityGroups.OBSERVATIONS,
        params=params_map,
        as_generator=False,
    )
    if lookup_result is None:
        return []
    if not isinstance(lookup_result, list):
        raise TypeError("Expected list response from frost_entity_lookup with as_generator=False.")
    return lookup_result

def _check_unlinked_object_exists(
        st_object: UnLinkedSensorThingsObjects,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> bool:
    """
    Check if an unlinked SensorThings Thing exists in a given FROST instance.
    
    This checker only compares the field values of the object do decide if an
    object already exists. Should not be used for Datastream objects.
    """
    #firstly, check if an object with the same name exists, and keep only the
    #properties we need:
    response = frost_object_lookup(st_object, root_url, version)
    if not response:
        return False
    # next, check if the values held in the object are equivalent to the values
    # held in the response of:
    st_object_dict = st_object.model_dump(
            include=set(SENSOR_THINGS_ENTITY_FIELDS[st_object.as_entity]))
    st_object_dumps = json.dumps(
            st_object_dict, 
            sort_keys=True, 
            separators=(",", ":"), 
            default=str
            )
    for results in response:
        for r in results:
            r_dumps = json.dumps(
                    r, 
                    sort_keys=True, 
                    separators=(",", ":"), 
                    default=str)
            if r_dumps == st_object_dumps:
                    return True
    
    return False

def _check_datastream_object_exists(
        st_datastream: Datastream,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> bool:
    # Invariant: Datastream has exactly one linked Sensor.
    sensor = st_datastream.links[SensorThingsEntity.SENSOR][0]

    # lookup candidate datastreams:
    matches = frost_object_lookup(
            st_datastream, 
            root_url, 
            version, 
            as_generator=False
            )
    if not matches:
        return False

    # for each datastream returned, lookup Sensor, check if it matches expected sensor:
    for match in matches:
        datastream_id = match.get("@iot.id")
        if datastream_id is None:
            continue

        linked_sensors = frost_entity_lookup(
            first_entity=SensorThingsEntityGroups.DATASTREAMS,
            root_url=root_url,
            version=version,
            first_entity_id=datastream_id,
            second_entity=SensorThingsEntityGroups.SENSORS,
            as_generator=False,
        )
        if not linked_sensors:
            continue

        linked_sensor_name = linked_sensors[0]["name"]
        if linked_sensor_name == sensor.name:
            return True

    return False

def _check_observation_object_exists(
        st_observation: Observation,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ):

    matches = frost_object_lookup(
            st_observation, 
            root_url, 
            version, 
            as_generator=False
            )
    if not matches:
        return False
    
    return True

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

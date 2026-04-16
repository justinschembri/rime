"""Execute GET requests with local or external FROST servers."""
#standard
from datetime import datetime
#external
#internal
import json
from typing import Optional, Mapping, Any

import requests
from sensorthings_utils.config import (
    CONTAINER_ENVIRONMENT,
    FROST_ROOT_DEFAULT,
    FROST_VERSION_DEFAULT,
)
from sensorthings_utils.frost import UrlStr
from .errors import FrostNoResultsError, FrostRequestError
from .sanitization import (
    merge_filter,
    merge_order_by,
    sanitize_request,
    to_odata_datetime,
)
from .types import FrostParams, FrostResultPageIterator, FrostVersions
from sensorthings_utils.sensor_things.core import (
        SENSOR_THINGS_ENTITY_FIELDS, 
        Datastream, 
        Observation, 
        UnLinkedSensorThingsObjects, 
        SensorThingsEntity,
        SensorThingsEntityGroups
        )


def _general_request(
        url, 
        params: Optional[Mapping[str | FrostParams, Any]] = None
        ) -> dict[str, Any]:
    response = requests.get(url, params=params) #type: ignore
    response.raise_for_status()
    json_response = response.json() 
    return json_response

def iter_frost_value_pages(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = ""
        ) -> FrostResultPageIterator | None:
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

    Returns:
        Iterator for JSON like data returned from the FROST server, one-level deep:
            {"values": list[dict[str, Any]]}. FROST sever returns include 100 
            items per page, and this iterator serves those pages.
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
        while True:
            page = response.get("value")
            if not isinstance(page, list):
                raise TypeError("Expected FROST page response to contain list `value`.")
            yield page

            next_link = response.get("@iot.nextLink")
            if not next_link:
                break
            response = _general_request(next_link)
    except Exception as e:
        raise FrostRequestError(e, url)

def get_frost_values(
        paginated_iterator: FrostResultPageIterator 
        ) -> dict[str, Any]:
    """
    Merge FROST result values into one object.

    Args:
        paginated_iterator: Iterator ,

    Returns:
        JSON like data returned from the FROST server, one-level deep:
            {"values": list[dict[str, Any]]}
    """
    data: dict[str, Any] = {"value": []}
    for page in paginated_iterator: 
        data["value"].extend(page)
    return data

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
        ) -> dict[str, Any]:
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

    return get_frost_values(
        iter_frost_value_pages(
            root_url=root_url,
            version=version,
            first_entity=SensorThingsEntityGroups.DATASTREAMS,
            first_entity_id=datastream_id,
            second_entity=SensorThingsEntityGroups.OBSERVATIONS,
            params=params_map,
        )
    )

def _check_unlinked_object_exists(
        st_object: UnLinkedSensorThingsObjects,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ) -> bool:
    """
    Check if a possibly unlinked SensorThings Thing exists in a given FROST 
    instance.
    
    This checker only compares the field values of the object do decide if an
    object already exists. Should not be used for Datastream objects.
    """
    #firstly, check if an object with the same name exists, and keep only the
    #properties we need:
    entity = SensorThingsEntity(st_object.as_entity)
    params = {
            FrostParams.SELECT:",".join(SENSOR_THINGS_ENTITY_FIELDS[entity]),
            FrostParams.FILTER:f"name eq '{st_object.name}'"
            }
    
    response = iter_frost_value_pages(
            st_object.as_entity,
            root_url=root_url,
            version=version,
            params=params
            )
    if not response:
        return False
    # next, check if the values held in the object are equivalent to the values
    # held in the response of:
    st_object_dict = st_object.model_dump(
            include=set(SENSOR_THINGS_ENTITY_FIELDS[entity]))
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

def check_linked_object_exists(
        st_object: LinkedSensorThingsObjects,
        root_url:str = FROST_ROOT_DEFAULT,
        version: str = FROST_VERSION_DEFAULT
        ):
    #first, treat as unlinked:
    if _check_unlinked_object_exists(st_object):
        return True


"""Execute GET requests with local or external FROST servers."""
#standard
from datetime import datetime
#external
#internal
from typing import Optional, Mapping, Any

import requests
from sensorthings_utils.frost.errors import FrostRequestError
from sensorthings_utils.frost.sanitization import (
    merge_filter,
    merge_order_by,
    sanitize_request,
    to_odata_datetime,
)
from sensorthings_utils.frost.types import FrostParams, FrostVersions
from sensorthings_utils.sensor_things.core import SensorThingsEntities

def _general_request(
        url, 
        params: Optional[Mapping[str | FrostParams, Any]] = None
        ) -> dict[str, Any]:
    response = requests.get(url, params=params) #type: ignore
    response.raise_for_status()
    json_response = response.json() 
    return json_response

def get_frost_values(
        root_url: str,
        version: str | float | int | FrostVersions,
        first_entity: str | SensorThingsEntities,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntities] = ""
        ) -> dict[str, Any]:
    """
    Query a FROST server and return data as a dict object.
    
    This is a general querying tool for FROST over HTTP. Entity names and param
    keys are checked but parameter values are not.

    Args:
        root_url: the FROST url **without** the version,
        version: the FROST server version,
        first_entity: the type of the first entity you want, must be a 
            SensorThingsEntities enum (e.g., Things, Sensors, Datastreams)
        params: optional OData params, must be FrostParams.
        first_entity_id: If you want to query the entity which is related to 
            another one, you must supply the ID of the first entity.
        second_entity: the child entity you're looking for. For example, if you
            want the Locations of Things(1), the first entity would be Things
            and the second would be Locations.

    Returns:
        JSON like data returned from the FROST server, one-level deep:
            {"values": list[dict[str, Any]]}
    """
    url, params = sanitize_request(
        root_url=root_url,
        version=version,
        first_entity=first_entity,
        params=params,
        first_entity_id=first_entity_id,
        second_entity=second_entity,
    )
    
    # e.g.: https://multicare.bk.tudelft.nl/FROST-Server/v1.1/Locations(1)/Things
    data = {} # nesting to maintain FROST structure
    try:
        response = _general_request(url, params)
        data["value"] = response["value"]
        while response.get("@iot.nextLink"):
            response = _general_request(response["@iot.nextLink"])
            data["value"].append(response["value"])
    except Exception as e:
        raise FrostRequestError(e, url)

    return data

def get_frost_datastream_observations(
        root_url: str,
        version: str | float | int | FrostVersions,
        datastream_id: int | str,
        *,
        time_start: Optional[datetime | str] = None,
        time_end: Optional[datetime | str] = None,
        result_min: Optional[int | float] = None,
        result_max: Optional[int | float] = None,
        result_eq: Optional[int | float] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        ) -> dict[str, Any]:
    """
    Query `Datastreams(<id>)/Observations` with optional convenience filters.

    All filter helper arguments are optional.
    """

    params_map: dict[str, Any] = {}
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
        root_url=root_url,
        version=version,
        first_entity=SensorThingsEntities.DATASTREAMS,
        first_entity_id=datastream_id,
        second_entity=SensorThingsEntities.OBSERVATIONS,
        params=params_map,
    )

"""Execute GET requests with local or external FROST servers."""
#standard
#external
#internal
from typing import Optional, Mapping, Any

import requests
from sensorthings_utils.frost.errors import FrostRequestError
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
    # sanitize
    root_url = root_url.rstrip("/")
    first_entity = SensorThingsEntities(first_entity).value
    version = FrostVersions(str(version).lstrip("v")).value
    if params:
        params = {FrostParams(i).value:j for i,j in params.items()}
    if second_entity and first_entity_id:
        second_entity = SensorThingsEntities(second_entity).value
        first_entity_id = f"({str(first_entity_id).strip('()')})"

    url = (
            f"{root_url}/v{version}/{first_entity}{first_entity_id}/{second_entity}"
            ).rstrip("/")
    
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


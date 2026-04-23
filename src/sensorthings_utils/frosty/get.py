"""Execute GET requests with local or external FROST servers."""
# standard
from datetime import datetime
from typing import Optional, Mapping, Any, cast
# external
import requests
# internal
from sensorthings_utils.config import (
    FROST_ROOT_DEFAULT,
    FROST_VERSION_DEFAULT,
)
from sensorthings_utils.sensor_things.core import (
    Observation,
    SensorThingsObject,
)
from sensorthings_utils.sensor_things.schema import (
    SENSOR_THINGS_ENTITY_FIELDS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)
from .errors import FrostRequestError
from .sanitization import (
    merge_filter,
    merge_order_by,
    sanitize_get_request,
    to_odata_datetime,
)
from .types import FrostParams, FrostResultPageIterator, FrostVersions


def general_frost_get(
    url: str,
    params: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    response = requests.get(url, params=params) #type: ignore
    response.raise_for_status()
    json_response = response.json() 
    return json_response

def frost_entity_lookup_pages(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = ""
        ) -> FrostResultPageIterator:
    """
    Query a FROST server and return unpacked `value` pages.
    
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
        Iterator over each FROST `value` page (possibly empty when the server
        returns no rows). Callers that merge pages should treat an exhausted
        iterator with no yields as no results.
    """

    url, sanitized_params = sanitize_get_request(
        root_url=root_url,
        version=version,
        first_entity=first_entity,
        params=params,
        first_entity_id=first_entity_id,
        second_entity=second_entity,
    )
    try:
        response = general_frost_get(url, sanitized_params)

        while True:
            page = response.get("value")
            if not page:
                return
            yield page 

            next_link = response.get("@iot.nextLink")
            if not next_link:
                break
            response = general_frost_get(next_link)

    except Exception as e:
        raise FrostRequestError(e, url)

def frost_entity_lookup(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | FrostParams, Any]] = None,
        *,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
        ) -> list[dict[str, Any]] | None:
    """Wrapper over `frost_entity_lookup_pages` that merges all pages into one list."""
    pages = frost_entity_lookup_pages(
        first_entity=first_entity,
        root_url=root_url,
        version=version,
        params=params,
        first_entity_id=first_entity_id,
        second_entity=second_entity,
    )
    data: list[dict[str, Any]] = []
    for page in pages:
        data.extend(page)
    return data if data else None


def frost_object_lookup_pages(
        st_object: SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        ) -> FrostResultPageIterator:
    """Lookup equivalent SensorThingsObject values and return paged iterator."""

    if isinstance(st_object, Observation):
        if st_object.phenomenonTime is None:
            raise ValueError(
                "Cannot look up an Observation without a phenomenonTime."
            )
        filter_string = (
            f"phenomenonTime eq {to_odata_datetime(st_object.phenomenonTime)}"
        )
    elif isinstance(st_object, SensorThingsObject):
        filter_string = f"name eq '{st_object.name}'"

    entity = SensorThingsEntity(st_object.entity_type)
    # `@iot.id` is required by downstream callers (e.g.
    # `_check_datastream_object_exists` needs it to follow navigation
    # links). FROST will only include it in a `$select`ed response when it
    # is named explicitly.
    select_fields = ("@iot.id", *SENSOR_THINGS_ENTITY_FIELDS[entity])
    params: dict[str | FrostParams, Any] = {
        FrostParams.SELECT: ",".join(select_fields),
        FrostParams.FILTER: filter_string,
    }

    return frost_entity_lookup_pages(
            entity,
            root_url=root_url,
            version=version,
            params=params,
            )


def frost_object_lookup(
        st_object: SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        ) -> list[dict[str, Any]] | None:
    """Wrapper over `frost_object_lookup_pages` that merges all pages into one list."""
    pages = frost_object_lookup_pages(
        st_object=st_object,
        root_url=root_url,
        version=version,
    )
    data: list[dict[str, Any]] = []
    for page in pages:
        data.extend(page)
    return data if data else None


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
        params=cast(Mapping[str | FrostParams, Any], params_map),
    )
    if not lookup_result:
        return []
    if not isinstance(lookup_result, list):
        raise TypeError("Expected list response from frost_entity_lookup.")
    return lookup_result


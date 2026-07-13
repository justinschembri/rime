"""Execute GET requests with local or external FROST servers."""
# standard
from datetime import datetime
from typing import Optional, Mapping, Any, cast
# external
import requests
# internal
from rime_ingest.config import (
    FROST_ROOT_DEFAULT,
    FROST_VERSION_DEFAULT,
)
from rime_ingest.sta.core import Observation, SensorThingsObject
from rime_ingest.sta.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)
from .errors import FrostRequestError
from .odata import (
    ODataParams,
    merge_filter,
    merge_order_by,
    odata_eq,
    odata_le,
    odata_filter_name_eq,
    odata_filter_phenomenon_time_eq,
    odata_filter_phenomenon_time_ge,
    odata_filter_phenomenon_time_le,
)
from .sanitization import (
    rewrite_to_internal,
    sanitize_get_request,
    sanitize_root_url,
)
from .types import FrostResultPageIterator, FrostUrl, FrostVersions


def general_frost_get(
    url: str,
    params: Optional[Mapping[str, Any]] = None,
    auth_headers: str | None = None,
) -> dict[str, Any]:
    """Execute a raw GET request and return the parsed JSON body.

    Args:
        url: Fully-qualified URL to request.
        params: Optional query-string parameters to append.
        auth_headers: Base64-encoded credentials for the ``Authorization``
            header. Omit when the server requires no auth.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        FrostRequestError: On any HTTP or connection error.
    """
    headers: dict[str, str] = {}
    if auth_headers:
        headers["Authorization"] = f"Basic {auth_headers}"
    try:
        response = requests.get(url, params=params, headers=headers or None)  # type: ignore[arg-type]
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise FrostRequestError(exc, url)

def frost_entity_lookup_pages(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | ODataParams, Any]] = None,
        *,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
        auth_headers: str | None = None,
        ) -> FrostResultPageIterator:
    """Query a FROST endpoint and yield each page of ``value`` rows.

    Handles OData ``@iot.nextLink`` pagination automatically, rewriting each
    next-page URL to the internal ``root_url`` so that containerised deployments
    with a public ``serviceRootUrl`` never make requests outside the container
    network. Entity names and param keys are validated; param values are passed
    through as-is.

    Args:
        first_entity: The primary entity collection to query (e.g. ``Things``,
            ``Sensors``). Accepts singular, plural, or enum forms.
        root_url: FROST server root URL, without the version segment.
        version: API version (e.g. ``"1.1"``).
        params: Optional OData query params; keys must be ``ODataParams`` values
            or their string equivalents.
        first_entity_id: ID of the first entity when traversing a relationship
            (e.g. ``Things(42)/Locations`` requires ``first_entity_id=42``).
        second_entity: Child entity collection to retrieve from the first entity.
        auth_headers: Base64-encoded credentials for the ``Authorization`` header.

    Yields:
        Each ``value`` page as a list of dicts. Exhausts without yielding when
        the server returns no rows.

    Raises:
        FrostRequestError: On any HTTP or connection error.
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
        response = general_frost_get(url, sanitized_params, auth_headers=auth_headers)

        while True:
            page = response.get("value")
            if not page:
                return
            yield page 

            next_link = response.get("@iot.nextLink")
            if not next_link:
                break
            response = general_frost_get(
                rewrite_to_internal(next_link, url),
                auth_headers=auth_headers,
            )

    except Exception as e:
        raise FrostRequestError(e, url)

def frost_entity_lookup(
        first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        params: Optional[Mapping[str | ODataParams, Any]] = None,
        *,
        first_entity_id: Optional[int | str] = "",
        second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
        auth_headers: str | None = None,
        ) -> list[dict[str, Any]] | None:
    """Merge all pages from ``frost_entity_lookup_pages`` into a single list.

    Accepts the same arguments as ``frost_entity_lookup_pages``.

    Returns:
        Flat list of entity dicts, or ``None`` when the server returns no rows.
    """
    pages = frost_entity_lookup_pages(
        first_entity=first_entity,
        root_url=root_url,
        version=version,
        params=params,
        first_entity_id=first_entity_id,
        second_entity=second_entity,
        auth_headers=auth_headers,
    )
    data: list[dict[str, Any]] = []
    for page in pages:
        data.extend(page)
    return data if data else None


def frost_object_lookup_pages(
        st_object: SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> FrostResultPageIterator:
    """Yield FROST pages matching an in-memory SensorThings object.

    Builds the appropriate OData ``$filter`` automatically: observations are
    matched by ``phenomenonTime``; all other objects are matched by ``name``.

    Args:
        st_object: The object to search for on the server.
        root_url: FROST server root URL, without the version segment.
        version: API version.

    Yields:
        Each ``value`` page from the server.

    Raises:
        ValueError: If ``st_object`` is an ``Observation`` without a
            ``phenomenonTime``.
    """
    if isinstance(st_object, Observation):
        if st_object.phenomenonTime is None:
            raise ValueError(
                "Cannot look up an Observation without a phenomenonTime."
            )
        filter_string = odata_filter_phenomenon_time_eq(st_object.phenomenonTime)
    else:
        filter_string = odata_filter_name_eq(st_object.name)

    params: dict[ODataParams, Any] = {
        ODataParams.FILTER: filter_string,
    }

    return frost_entity_lookup_pages(
            st_object.entity_type,
            root_url=root_url,
            version=version,
            params=params,
            auth_headers=auth_headers,
            )


def frost_object_lookup(
        st_object: SensorThingsObject | Observation,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
        ) -> list[dict[str, Any]] | None:
    """Merge all pages from ``frost_object_lookup_pages`` into a single list.

    Args:
        st_object: The object to search for on the server.
        root_url: FROST server root URL, without the version segment.
        version: API version.

    Returns:
        Flat list of matching entity dicts, or ``None`` when nothing is found.
    """
    pages = frost_object_lookup_pages(
        st_object=st_object,
        root_url=root_url,
        version=version,
        auth_headers=auth_headers,
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
        auth_headers: str | None = None,
        ) -> list[dict[str, Any]]:
    """Return all observations for a datastream with optional filter helpers.

    By default selects only ``@iot.id``, ``phenomenonTime``, ``resultTime``,
    and ``result``. Set ``verbose=True`` to retrieve all fields.

    Args:
        datastream_id: The ``@iot.id`` of the target Datastream.
        root_url: FROST server root URL, without the version segment.
        version: API version.
        verbose: When ``True``, omit the ``$select`` restriction.
        time_start: Lower bound for ``phenomenonTime`` (inclusive).
        time_end: Upper bound for ``phenomenonTime`` (inclusive).
        result_min: Lower bound for ``result`` (inclusive).
        result_max: Upper bound for ``result`` (inclusive).
        result_eq: Exact value for ``result``.
        order_by: Field to sort by (default ``phenomenonTime``).
        descending: Sort direction; ``True`` for descending.

    Returns:
        List of observation dicts. Empty list when none match.

    Raises:
        TypeError: If the underlying lookup returns an unexpected type.
    """

    params_map: dict[ODataParams, Any] = {}
    if not verbose:
        params_map[ODataParams.SELECT] = "@iot.id,phenomenonTime,resultTime,result"

    filter_clauses: list[str] = []
    if time_start is not None:
        filter_clauses.append(odata_filter_phenomenon_time_ge(time_start))
    if time_end is not None:
        filter_clauses.append(odata_filter_phenomenon_time_le(time_end))
    if result_min is not None:
        filter_clauses.append(odata_eq("result", result_min))
    if result_max is not None:
        filter_clauses.append(odata_le("result", result_max))
    if result_eq is not None:
        filter_clauses.append(odata_eq("result", result_eq))

    if filter_clauses:
        params_map = merge_filter(params_map, " and ".join(filter_clauses))
    params_map = merge_order_by(params_map, order_by=order_by, descending=descending)

    lookup_result = frost_entity_lookup(
        root_url=root_url,
        version=version,
        first_entity=SensorThingsEntityGroups.DATASTREAMS,
        first_entity_id=datastream_id,
        second_entity=SensorThingsEntityGroups.OBSERVATIONS,
        params=cast(Mapping[str | ODataParams, Any], params_map),
        auth_headers=auth_headers,
    )
    if not lookup_result:
        return []
    if not isinstance(lookup_result, list):
        raise TypeError("Expected list response from frost_entity_lookup.")
    return lookup_result


def find_datastream_observations_url(
        sensor_name: str,
        datastream_name: str,
        root_url: str = FROST_ROOT_DEFAULT,
        version: str | float | int | FrostVersions = FROST_VERSION_DEFAULT,
        auth_headers: str | None = None,
) -> FrostUrl | None:
    """Resolve the Datastream entity URL for posting Observations.

    Looks up the Sensor by ``sensor_name``, then the Datastream under that sensor
    whose STA ``name`` equals ``datastream_name`` (OData ``$filter``). A sensor
    may own many Datastreams; **the disambiguator is ``datastream_name``**, which
    must match each stream's ``name`` field (aligned with sensor YAML /
    transformers).

    Returns the Datastream's ``@iot.selfLink``, or builds
    ``{root}/v{version}/Datastreams(id)``, **without** a trailing ``/Observations``.
    ``make_frost_entity`` appends ``/Observations`` when posting — same contract
    as posting a Location under a Thing.

    URLs are passed through ``rewrite_to_internal`` for containerised deployments.

    Args:
        sensor_name: Name of the target Sensor entity.
        datastream_name: ``name`` of the target Datastream under that sensor.
        root_url: FROST server root URL, used to rewrite links.
        version: SensorThings API version.

    Returns:
        Internal Datastream URL, or ``None`` if the sensor or datastream is not
        found on the server.
    """
    sensors = frost_entity_lookup(
        first_entity=SensorThingsEntity.SENSOR,
        root_url=root_url,
        version=version,
        params={ODataParams.FILTER: odata_filter_name_eq(sensor_name)},
        auth_headers=auth_headers,
    )
    if not sensors:
        return None

    sensor_id = sensors[0].get("@iot.id")
    if sensor_id is None:
        return None

    datastreams = frost_entity_lookup(
        first_entity=SensorThingsEntity.SENSOR,
        first_entity_id=sensor_id,
        second_entity=SensorThingsEntityGroups.DATASTREAMS,
        root_url=root_url,
        version=version,
        params={ODataParams.FILTER: odata_filter_name_eq(datastream_name)},
        auth_headers=auth_headers,
    )
    if not datastreams:
        return None

    ds = datastreams[0]
    self_link = ds.get("@iot.selfLink")
    if isinstance(self_link, str) and self_link:
        return rewrite_to_internal(self_link, root_url)

    ds_id = ds.get("@iot.id")
    if ds_id is None:
        return None
    norm_root, ver_str = sanitize_root_url(root_url, version)
    constructed = f"{norm_root}/v{ver_str}/Datastreams({ds_id})"
    return rewrite_to_internal(constructed, root_url)

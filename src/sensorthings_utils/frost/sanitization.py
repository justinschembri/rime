"""Sanitization and query-building helpers for FROST requests."""
#standard
from datetime import datetime
#internal
from typing import Optional, Mapping, Any

from sensorthings_utils.frost.types import FrostParams, FrostVersions
from sensorthings_utils.sensor_things.core import SensorThingsEntities

def to_odata_datetime(value: datetime | str) -> str:
    """Convert datetime-like values into OData datetime string format."""

    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

def sanitize_request(
    root_url: str,
    version: str | float | int | FrostVersions,
    first_entity: str | SensorThingsEntities,
    params: Optional[Mapping[str | FrostParams, Any]] = None,
    *,
    first_entity_id: Optional[int | str] = "",
    second_entity: Optional[str | SensorThingsEntities] = "",
) -> tuple[str, dict[str, Any] | None]:
    """Normalize request URL and parameter keys for FROST queries."""

    normalized_root = root_url.rstrip("/")
    normalized_first_entity = SensorThingsEntities(first_entity).value
    normalized_version = FrostVersions(str(version).lstrip("v")).value
    normalized_second_entity = ""
    normalized_first_entity_id = ""

    if second_entity:
        normalized_second_entity = SensorThingsEntities(second_entity).value
    if first_entity_id not in ("", None):
        normalized_first_entity_id = f"({str(first_entity_id).strip('()')})"

    normalized_params: dict[str, Any] | None = None
    if params:
        normalized_params = {FrostParams(key).value: value for key, value in params.items()}

    url = (
        f"{normalized_root}/v{normalized_version}/"
        f"{normalized_first_entity}{normalized_first_entity_id}/{normalized_second_entity}"
    ).rstrip("/")
    return url, normalized_params

def merge_filter(params: dict[str, Any], extra_filter: str) -> dict[str, Any]:
    """Merge generated filter text with an existing $filter if present."""

    existing_filter = params.get(FrostParams.FILTER.value)
    if existing_filter:
        params[FrostParams.FILTER.value] = f"({existing_filter}) and ({extra_filter})"
    else:
        params[FrostParams.FILTER.value] = extra_filter
    return params

def merge_order_by(
    params: dict[str, Any],
    order_by: Optional[str],
    descending: bool,
) -> dict[str, Any]:
    """Apply a single orderBy argument to OData params."""

    if not order_by:
        return params
    direction = "desc" if descending else "asc"
    params[FrostParams.ORDER.value] = f"{order_by} {direction}"
    return params

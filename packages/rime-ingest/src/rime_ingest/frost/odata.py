"""OData query helpers and SensorThings value formatters for FROST GET requests."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

PhenomenonTime = datetime | str | Tuple[datetime, datetime]


class ODataParams(Enum):
    """OData query parameter keys accepted by FROST."""

    TOP = "$top"
    SKIP = "$skip"
    COUNT = "$count"
    ORDER = "$orderBy"
    EXPAND = "$expand"
    SELECT = "$select"
    FILTER = "$filter"


def to_odata_datetime(value: datetime | str) -> str:
    """Convert a datetime or string into an OData-compatible datetime literal."""
    if isinstance(value, datetime):
        iso = value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.isoformat()
    else:
        iso = str(value)
    return iso.replace("+00:00", "Z")


def format_phenomenon_time(value: PhenomenonTime) -> str:
    """Serialize a point or interval phenomenonTime for FROST / OData."""
    if isinstance(value, tuple):
        start, end = value
        start_s = to_odata_datetime(start) if isinstance(start, datetime) else str(start)
        end_s = to_odata_datetime(end) if isinstance(end, datetime) else str(end)
        return f"{start_s}/{end_s}"
    if isinstance(value, datetime):
        return to_odata_datetime(value)
    return str(value)


def odata_string_literal(value: str) -> str:
    """Quote a string literal for use in an OData ``$filter`` expression."""
    return "'" + value.replace("'", "''") + "'"


def odata_eq(field: str, value: str | int | float) -> str:
    if isinstance(value, str):
        return f"{field} eq {odata_string_literal(value)}"
    return f"{field} eq {value}"


def odata_ge(field: str, value: datetime | str | int | float) -> str:
    if isinstance(value, (datetime, str)):
        return f"{field} ge {to_odata_datetime(value)}"
    return f"{field} ge {value}"


def odata_le(field: str, value: datetime | str | int | float) -> str:
    if isinstance(value, (datetime, str)):
        return f"{field} le {to_odata_datetime(value)}"
    return f"{field} le {value}"


def odata_filter_name_eq(name: str) -> str:
    return odata_eq("name", name)


def odata_filter_phenomenon_time_eq(phenomenon_time: PhenomenonTime) -> str:
    """Build an OData ``$filter`` clause for an exact ``phenomenonTime`` match.

    Datetime literals must be unquoted (unlike string fields such as ``name``).
    """
    return (
        "phenomenonTime eq "
        f"{to_odata_datetime(format_phenomenon_time(phenomenon_time))}"
    )


def odata_filter_phenomenon_time_ge(value: datetime | str) -> str:
    return odata_ge("phenomenonTime", value)


def odata_filter_phenomenon_time_le(value: datetime | str) -> str:
    return odata_le("phenomenonTime", value)


def normalize_odata_param_key(key: str | ODataParams) -> str:
    if isinstance(key, ODataParams):
        return key.value
    for member in ODataParams:
        if member.value == key:
            return key
    return ODataParams(key).value


def normalize_odata_params(
    params: Mapping[str | ODataParams, Any],
) -> dict[str, Any]:
    """Validate OData param keys and normalise them to ``$token`` strings."""
    return {normalize_odata_param_key(key): value for key, value in params.items()}


def merge_filter(params: dict[str | ODataParams, Any], extra_filter: str) -> dict[str | ODataParams, Any]:
    """Merge an additional OData filter clause into an existing params dict."""
    existing_filter = params.get(ODataParams.FILTER)
    if existing_filter is None:
        existing_filter = params.get(ODataParams.FILTER.value)
    if existing_filter:
        params[ODataParams.FILTER] = f"({existing_filter}) and ({extra_filter})"
    else:
        params[ODataParams.FILTER] = extra_filter
    params.pop(ODataParams.FILTER.value, None)
    return params


def merge_order_by(
    params: dict[str | ODataParams, Any],
    order_by: Optional[str],
    descending: bool,
) -> dict[str | ODataParams, Any]:
    """Set the ``$orderBy`` clause in an OData params dict."""
    if not order_by:
        return params
    direction = "desc" if descending else "asc"
    params[ODataParams.ORDER] = f"{order_by} {direction}"
    params.pop(ODataParams.ORDER.value, None)
    return params

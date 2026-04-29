"""Sanitization and query-building helpers for FROST requests."""
#standard
from datetime import datetime
from urllib.parse import urlparse
#internal
from typing import Optional, Mapping, Any

from .types import FrostParams, FrostVersions
from sensorthings_utils.sensor_things.schema import (
    ENTITIES_TO_ENTITY_GROUPS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

def to_odata_datetime(value: datetime | str) -> str:
    """Convert datetime-like values into OData datetime string format."""

    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

def sanitize_get_request(
    root_url: str,
    version: str | float | int,
    first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
    params: Optional[Mapping[str | FrostParams, Any]] = None,
    *,
    first_entity_id: Optional[int | str] = "",
    second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
) -> tuple[str, dict[str, Any] | None]:
    """Normalize GET request URL, entities, and OData parameter keys.

    - Accepts singular or plural SensorThings entity identifiers and normalizes
      them to plural endpoint names used in FROST URLs.
    - Sanitizes `root_url` + `version` into canonical form (`.../vX.Y/...`).
    - Normalizes query-param keys to official OData tokens via `FrostParams`.
    """
    try:
        normalized_first_entity = SensorThingsEntityGroups(first_entity).value
    except ValueError:
        normalized_first_entity = ENTITIES_TO_ENTITY_GROUPS[
            SensorThingsEntity(first_entity)
        ].value
    normalized_second_entity = ""
    normalized_first_entity_id = ""

    if second_entity:
        try:
            normalized_second_entity = SensorThingsEntityGroups(second_entity).value
        except ValueError:
            normalized_second_entity = ENTITIES_TO_ENTITY_GROUPS[
                SensorThingsEntity(second_entity)
            ].value
    if first_entity_id not in ("", None):
        normalized_first_entity_id = f"({str(first_entity_id).strip('()')})"

    normalized_params: dict[str, Any] | None = None
    if params:
        normalized_params = {FrostParams(key).value: value for key, value in params.items()}
    
    sanitized_root, sanitized_version = sanitize_root_url(root_url, version)
    url = (
        f"{sanitized_root}/v{sanitized_version}/"
        f"{normalized_first_entity}{normalized_first_entity_id}/{normalized_second_entity}"
    ).rstrip("/")
    return url, normalized_params

def sanitize_root_url(
        root_url:str,
        version: str | int | float
        )-> tuple[str, str]:
    normalized_root = str(root_url.rstrip("/"))
    normalized_version = FrostVersions(str(version).lstrip("v")).value
    return (normalized_root, normalized_version)

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


def rewrite_to_internal(nav_url: str, internal_root: str) -> str:
    """Rewrite a FROST navigation link to use the internal root URL.

    FROST embeds its ``serviceRootUrl`` into every ``@iot.navigationLink`` and
    ``@iot.selfLink`` it returns.  In containerised deployments the public URL
    (e.g. ``https://multicare.bk.tudelft.nl/FROST-Server``) differs from the
    address the python-app uses to reach FROST internally
    (e.g. ``http://web:8080/FROST-Server``).  This function replaces the
    origin + base-path portion of a server-issued URL with the internal root,
    leaving the version + entity path intact.

    When both roots share the same origin (local development) the function is
    effectively a no-op.
    """
    internal = urlparse(internal_root.rstrip("/"))
    nav = urlparse(nav_url)
    internal_base = internal.path.rstrip("/")
    nav_path = nav.path

    # In the common case, nav links and internal roots share the same base path
    # (e.g. "/FROST-Server"). If not, fall back to preserving the full nav path
    # to avoid producing malformed URLs.
    if internal_base and nav_path.startswith(internal_base):
        suffix = nav_path[len(internal_base):]
    else:
        version_idx = nav_path.find("/v")
        suffix = nav_path[version_idx:] if version_idx != -1 else nav_path

    rewritten_path = f"{internal_base}{suffix}"
    rewritten = f"{internal.scheme}://{internal.netloc}{rewritten_path}"
    if nav.query:
        rewritten = f"{rewritten}?{nav.query}"
    return rewritten

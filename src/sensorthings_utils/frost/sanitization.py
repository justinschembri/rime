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
    """Convert a datetime or string into an OData-compatible datetime string.

    ``datetime`` objects are converted via ``isoformat()``; strings are passed
    through unchanged so that callers can supply pre-formatted values directly.

    Args:
        value: A ``datetime`` instance or an already-formatted string.

    Returns:
        ISO 8601 string suitable for use in OData ``$filter`` expressions.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

def sanitize_get_request(
    root_url: str,
    version: str | float | int | FrostVersions ,
    first_entity: str | SensorThingsEntityGroups | SensorThingsEntity,
    params: Optional[Mapping[str | FrostParams, Any]] = None,
    *,
    first_entity_id: Optional[int | str] = "",
    second_entity: Optional[str | SensorThingsEntityGroups | SensorThingsEntity] = "",
) -> tuple[str, dict[str, Any] | None]:
    """Build and normalise a FROST GET request URL and its OData params.

    Accepts singular or plural SensorThings entity names (as strings or enums)
    and normalises them to the plural endpoint form used in FROST URLs. The
    ``root_url`` and ``version`` are canonicalised, and all param keys are
    validated and converted to their official OData ``$token`` strings.

    Args:
        root_url: FROST server root URL, without the version segment.
        version: API version (e.g. ``1``, ``1.1``, ``"v1.1"``).
        first_entity: Primary entity collection to query.
        params: Optional OData query params; keys must be ``FrostParams``
            values or their string equivalents.
        first_entity_id: ID of the first entity for relationship traversal.
        second_entity: Child entity collection to retrieve.

    Returns:
        A tuple of ``(url, normalised_params)`` ready to pass to
        ``general_frost_get``.

    Raises:
        ValueError: When an entity name cannot be resolved to a known
            ``SensorThingsEntityGroups`` or ``SensorThingsEntity``.
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
        version: str | int | float | FrostVersions
        )-> tuple[str, str]:
    """Strip trailing slashes from ``root_url`` and normalise ``version``.

    Args:
        root_url: Raw FROST server root URL.
        version: Version as a number or string (with or without a leading
            ``v``).

    Returns:
        Tuple of ``(clean_root_url, version_string)`` where the version string
        matches the ``FrostVersions`` enum value (e.g. ``"1.1"``).

    Raises:
        ValueError: When ``version`` does not match a known ``FrostVersions``.
    """
    normalized_root = str(root_url.rstrip("/"))
    normalized_version = FrostVersions(str(version).lstrip("v")).value
    return (normalized_root, normalized_version)

def merge_filter(params: dict[str, Any], extra_filter: str) -> dict[str, Any]:
    """Merge an additional OData filter clause into an existing params dict.

    When a ``$filter`` key is already present, both clauses are wrapped in
    parentheses and joined with ``and``. Otherwise the new filter is inserted
    directly.

    Args:
        params: Existing OData params dict (mutated in place).
        extra_filter: OData filter expression to add.

    Returns:
        The updated ``params`` dict.
    """

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
    """Set the ``$orderBy`` clause in an OData params dict.

    Args:
        params: Existing OData params dict (mutated in place).
        order_by: Field name to sort by. When ``None`` or empty the params dict
            is returned unchanged.
        descending: ``True`` for ``desc``, ``False`` for ``asc``.

    Returns:
        The updated ``params`` dict.
    """

    if not order_by:
        return params
    direction = "desc" if descending else "asc"
    params[FrostParams.ORDER.value] = f"{order_by} {direction}"
    return params


def rewrite_to_internal(nav_url: str, internal_root: str) -> str:
    """Rewrite a FROST navigation link to use the internal root URL.

    FROST embeds its ``serviceRootUrl`` into every ``@iot.navigationLink`` and
    ``@iot.selfLink`` it returns. In containerised deployments the public URL
    (e.g. ``https://multicare.bk.tudelft.nl/FROST-Server``) differs from the
    address the Python app uses to reach FROST internally
    (e.g. ``http://web:8080/FROST-Server``). This function replaces the
    origin and base-path with ``internal_root``, leaving the version and entity
    path intact. When both roots share the same origin the function is a no-op.

    Args:
        nav_url: Server-issued navigation or self link to rewrite.
        internal_root: The root URL the app should use to contact FROST.

    Returns:
        Rewritten URL using the internal scheme, host, and base path.
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

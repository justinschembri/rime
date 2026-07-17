"""FROST / SensorThings API version handling and OData annotation field names.

STA 1.x uses ``@iot.*`` control information; STA 2.0 aligns with OData 4.01
(``id``, ``@id``, ``@navigationLink``, ``@nextLink``, ``@count``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class FrostVersions(StrEnum):
    """Supported FROST Server API versions.

    Members are plain version stems (no leading ``v``), so they interpolate
    directly into URLs: ``f"/v{FrostVersions.v1_1}/Things"`` → ``/v1.1/Things``.
    """

    v1 = "1.0"
    v1_1 = "1.1"
    v2 = "2.0"

    @classmethod
    def parse(cls, version: str | int | float | FrostVersions) -> FrostVersions:
        """Normalize a version string/number/enum into a ``FrostVersions`` member.

        Accepts values with or without a leading ``v`` (e.g. ``"v1.1"``,
        ``"1.1"``, ``1.1``).
        """
        if isinstance(version, FrostVersions):
            return version
        return cls(str(version).lstrip("v"))


@dataclass(frozen=True, slots=True)
class FrostODataFields:
    """OData annotation / id property names for a single STA version."""

    id: str
    self_link: str
    next_link: str
    count: str
    nav_link_suffix: str


def odata_fields_for(
    version: str | int | float | FrostVersions | None = None,
) -> FrostODataFields:
    """Return OData field names for ``version`` (default: active ``FROST_VERSION``)."""
    resolved = (
        FrostVersions.parse(version)
        if version is not None
        else FROST_VERSION
    )
    if resolved == FrostVersions.v2:
        return FrostODataFields(
            id="id",
            self_link="@id",
            next_link="@nextLink",
            count="@count",
            nav_link_suffix="@navigationLink",
        )
    return FrostODataFields(
        id="@iot.id",
        self_link="@iot.selfLink",
        next_link="@iot.nextLink",
        count="@iot.count",
        nav_link_suffix="@iot.navigationLink",
    )


# Populated by ``configure_frost_version`` (called at import and again from
# config after dotenv / when the resolved endpoint version is known).
FROST_VERSION: FrostVersions
FROST_ID_FIELD: str
FROST_SELF_LINK_FIELD: str
FROST_NEXT_LINK_FIELD: str
FROST_COUNT_FIELD: str
FROST_NAV_LINK_SUFFIX: str


def configure_frost_version(
    version: str | int | float | FrostVersions | None = None,
) -> FrostVersions:
    """Set module-level ``FROST_VERSION`` and OData annotation field names.

    When ``version`` is omitted, reads ``FROST_VERSION`` from the environment
    (default ``v1.1``). Call this whenever the active endpoint version is
    resolved (e.g. from ``FROST_ENDPOINT``) so field names stay in sync.
    """
    global FROST_VERSION, FROST_ID_FIELD, FROST_SELF_LINK_FIELD
    global FROST_NEXT_LINK_FIELD, FROST_COUNT_FIELD, FROST_NAV_LINK_SUFFIX

    FROST_VERSION = FrostVersions.parse(
        version if version is not None else os.getenv("FROST_VERSION", "v1.1")
    )
    fields = odata_fields_for(FROST_VERSION)
    FROST_ID_FIELD = fields.id
    FROST_SELF_LINK_FIELD = fields.self_link
    FROST_NEXT_LINK_FIELD = fields.next_link
    FROST_COUNT_FIELD = fields.count
    FROST_NAV_LINK_SUFFIX = fields.nav_link_suffix
    return FROST_VERSION


configure_frost_version()

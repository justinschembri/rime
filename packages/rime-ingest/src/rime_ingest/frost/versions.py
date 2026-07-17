"""FROST / SensorThings API version handling and OData annotation field names.

STA 1.x uses ``@iot.*`` control information; STA 2.0 aligns with OData 4.01
(``id``, ``@id``, ``@navigationLink``, ``@nextLink``, ``@count``).
"""

from __future__ import annotations

import os
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


# Populated by ``configure_frost_version`` (called at import and again from
# config after dotenv so local ``.env`` wins outside containers).
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
    (default ``v1.1``).
    """
    global FROST_VERSION, FROST_ID_FIELD, FROST_SELF_LINK_FIELD
    global FROST_NEXT_LINK_FIELD, FROST_COUNT_FIELD, FROST_NAV_LINK_SUFFIX

    FROST_VERSION = FrostVersions.parse(
        version if version is not None else os.getenv("FROST_VERSION", "v1.1")
    )
    if FROST_VERSION == FrostVersions.v2:
        FROST_ID_FIELD = "id"
        FROST_SELF_LINK_FIELD = "@id"
        FROST_NEXT_LINK_FIELD = "@nextLink"
        FROST_COUNT_FIELD = "@count"
        FROST_NAV_LINK_SUFFIX = "@navigationLink"
    else:
        FROST_ID_FIELD = "@iot.id"
        FROST_SELF_LINK_FIELD = "@iot.selfLink"
        FROST_NEXT_LINK_FIELD = "@iot.nextLink"
        FROST_COUNT_FIELD = "@iot.count"
        FROST_NAV_LINK_SUFFIX = "@iot.navigationLink"
    return FROST_VERSION


configure_frost_version()

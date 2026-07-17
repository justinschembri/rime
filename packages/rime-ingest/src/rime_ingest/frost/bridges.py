"""Lookup tables mapping SensorThings domain types to FROST wire-protocol values.

These dicts are the single source of truth for converting between the
OGC SensorThings API entity model (as represented by the local enums) and the
URL path segments / navigation-link keys used by FROST Server responses.
"""

from __future__ import annotations

from rime_ingest.sta.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

from .types import FrostEndpoints
from . import versions as frost_versions

# Entity / group name as it appears before the navigation-link annotation
# suffix (``@iot.navigationLink`` in STA 1.x, ``@navigationLink`` in STA 2.0).
_NAV_LINK_NAME_TO_ENTITY: dict[str, SensorThingsEntity | SensorThingsEntityGroups] = {
    "Sensor": SensorThingsEntity.SENSOR,
    "Sensors": SensorThingsEntityGroups.SENSORS,
    "Thing": SensorThingsEntity.THING,
    "Things": SensorThingsEntityGroups.THINGS,
    "Location": SensorThingsEntity.LOCATION,
    "Locations": SensorThingsEntityGroups.LOCATIONS,
    "HistoricalLocation": SensorThingsEntity.HISTORICALLOCATION,
    "HistoricalLocations": SensorThingsEntityGroups.HISTORICALLOCATIONS,
    "Datastream": SensorThingsEntity.DATASTREAM,
    "Datastreams": SensorThingsEntityGroups.DATASTREAMS,
    "Observation": SensorThingsEntity.OBSERVATION,
    "Observations": SensorThingsEntityGroups.OBSERVATIONS,
    "ObservedProperty": SensorThingsEntity.OBSERVEDPROPERTY,
    "ObservedProperties": SensorThingsEntityGroups.OBSERVEDPROPERTIES,
    "FeatureOfInterest": SensorThingsEntity.FEATUREOFINTEREST,
    "FeaturesOfInterest": SensorThingsEntityGroups.FEATURESOFINTEREST,
}


def navigation_link_to_entity(
    key: str,
) -> SensorThingsEntity | SensorThingsEntityGroups | None:
    """Resolve a FROST navigation-link response key to a local entity enum.

    Accepts both STA 1.x (``Thing@iot.navigationLink``) and STA 2.0
    (``Thing@navigationLink``) forms. Preferential match uses the active
    ``FROST_NAV_LINK_SUFFIX``; the alternate suffix is also recognised so
    payloads survive a version mismatch during migration.
    """
    for suffix in (
        frost_versions.FROST_NAV_LINK_SUFFIX,
        "@iot.navigationLink",
        "@navigationLink",
    ):
        if key.endswith(suffix):
            return _NAV_LINK_NAME_TO_ENTITY.get(key[: -len(suffix)])
    return None


def __getattr__(name: str):
    # Lazily keyed with the active version's suffix. Prefer
    # ``navigation_link_to_entity`` (handles both suffixes).
    if name == "NAVIGATION_LINKS_TO_ENTITY":
        return {
            f"{n}{frost_versions.FROST_NAV_LINK_SUFFIX}": e
            for n, e in _NAV_LINK_NAME_TO_ENTITY.items()
        }
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


ENTITY_TO_FROST_ENDPOINT: dict[SensorThingsEntity, FrostEndpoints] = {
    # Maps each singular entity type to the plural FROST endpoint used for
    # POST requests and URL construction.
    SensorThingsEntity.SENSOR: FrostEndpoints.SENSORS,
    SensorThingsEntity.THING: FrostEndpoints.THINGS,
    SensorThingsEntity.LOCATION: FrostEndpoints.LOCATIONS,
    SensorThingsEntity.HISTORICALLOCATION: FrostEndpoints.HISTORICALLOCATIONS,
    SensorThingsEntity.DATASTREAM: FrostEndpoints.DATASTREAMS,
    SensorThingsEntity.OBSERVATION: FrostEndpoints.OBSERVATIONS,
    SensorThingsEntity.OBSERVEDPROPERTY: FrostEndpoints.OBSERVEDPROPERTIES,
    SensorThingsEntity.FEATUREOFINTEREST: FrostEndpoints.FEATURESOFINTEREST,
}

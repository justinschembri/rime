"""Lookup tables mapping SensorThings domain types to FROST wire-protocol values.

These dicts are the single source of truth for converting between the
OGC SensorThings API entity model (as represented by the local enums) and the
URL path segments / navigation-link keys used by FROST Server responses.
"""

from __future__ import annotations

from dataclasses import dataclass

from rime_ingest.sta.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

from .types import FrostEndpoints
from . import versions as frost_versions
from .versions import FrostVersions

#TODO: Perhaps these mappings are just generally convoluted.

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
    "Feature": SensorThingsEntity.FEATURE,
    "Features": SensorThingsEntityGroups.FEATURES,
    "FeatureType": SensorThingsEntity.FEATURE_TYPE,
    "FeatureTypes": SensorThingsEntityGroups.FEATURE_TYPES,
    # STA 2.* Datastream ↔ Feature role names (navigation properties).
    "UltimateFeatureOfInterest": SensorThingsEntityGroups.ULTIMATE_FEATURES_OF_INTEREST,
    "UltimateFeaturesOfInterest": SensorThingsEntityGroups.FEATURES,
    "ProximateFeatureOfInterest": SensorThingsEntity.FEATURE,
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
    SensorThingsEntity.FEATURE: FrostEndpoints.FEATURES,
    SensorThingsEntity.FEATURE_TYPE: FrostEndpoints.FEATURETYPES,
}


@dataclass(frozen=True, slots=True)
class DatastreamLinkBinding:
    """How a Datastream relationship is expressed in a create/update JSON body.

    Attributes:
        field: Navigation property name on the Datastream payload.
        as_collection: When true, the linked ref is wrapped in a JSON array
            (many-to-many / collection navigation, e.g. STA 2.x
            ``ObservedProperties``).
    """

    field: str
    as_collection: bool = False


_DATASTREAM_LINK_BINDINGS_V1: dict[SensorThingsEntityGroups, DatastreamLinkBinding] = {
    SensorThingsEntityGroups.SENSORS: DatastreamLinkBinding("Sensor"),
    SensorThingsEntityGroups.THINGS: DatastreamLinkBinding("Thing"),
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: DatastreamLinkBinding(
        "ObservedProperty"
    ),
}

_DATASTREAM_LINK_BINDINGS_V2: dict[SensorThingsEntityGroups, DatastreamLinkBinding] = {
    SensorThingsEntityGroups.SENSORS: DatastreamLinkBinding("Sensor"),
    SensorThingsEntityGroups.THINGS: DatastreamLinkBinding("Thing"),
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: DatastreamLinkBinding(
        "ObservedProperties", as_collection=True
    ),
}


def datastream_link_bindings(
    version: str | int | float | FrostVersions | None = None,
) -> dict[SensorThingsEntityGroups, DatastreamLinkBinding]:
    """Return Datastream→related-entity wire bindings for ``version``."""
    resolved = (
        FrostVersions.safe_parse(version)
        if version is not None
        else frost_versions.FROST_VERSION
    )
    if resolved == FrostVersions.v2:
        return _DATASTREAM_LINK_BINDINGS_V2
    return _DATASTREAM_LINK_BINDINGS_V1

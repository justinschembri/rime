"""Centralized SensorThings mapping constants."""

from __future__ import annotations

from rime_ingest.frost.versions import FrostVersions, FROST_VERSION
from rime_ingest.sta.core import (
    DatastreamV1,
    DatastreamV2,
    Feature,
    FeatureOfInterest,
    FeatureType,
    LocationV1,
    LocationV2,
    Observation,
    ObservationV1,
    ObservationV2,
    ObservedPropertyV1,
    ObservedPropertyV2,
    SensorThingsObject,
    SensorV1,
    SensorV2,
    ThingV1,
    ThingV2,
)
from rime_ingest.sta.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

SensorThingsObjectMapKey = SensorThingsEntity | SensorThingsEntityGroups
SensorThingsClassMap = dict[
    SensorThingsObjectMapKey, type[SensorThingsObject | Observation]
]

_CLASS_MAP_V1: SensorThingsClassMap = {
    SensorThingsEntity.SENSOR: SensorV1,
    SensorThingsEntityGroups.SENSORS: SensorV1,
    SensorThingsEntity.THING: ThingV1,
    SensorThingsEntityGroups.THINGS: ThingV1,
    SensorThingsEntity.LOCATION: LocationV1,
    SensorThingsEntityGroups.LOCATIONS: LocationV1,
    SensorThingsEntity.HISTORICALLOCATION: LocationV1,
    SensorThingsEntityGroups.HISTORICALLOCATIONS: LocationV1,
    SensorThingsEntity.DATASTREAM: DatastreamV1,
    SensorThingsEntityGroups.DATASTREAMS: DatastreamV1,
    SensorThingsEntity.OBSERVATION: ObservationV1,
    SensorThingsEntityGroups.OBSERVATIONS: ObservationV1,
    SensorThingsEntity.OBSERVEDPROPERTY: ObservedPropertyV1,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: ObservedPropertyV1,
    SensorThingsEntity.FEATUREOFINTEREST: FeatureOfInterest,
    SensorThingsEntityGroups.FEATURESOFINTEREST: FeatureOfInterest,
}

_CLASS_MAP_V2: SensorThingsClassMap = {
    SensorThingsEntity.SENSOR: SensorV2,
    SensorThingsEntityGroups.SENSORS: SensorV2,
    SensorThingsEntity.THING: ThingV2,
    SensorThingsEntityGroups.THINGS: ThingV2,
    SensorThingsEntity.LOCATION: LocationV2,
    SensorThingsEntityGroups.LOCATIONS: LocationV2,
    SensorThingsEntity.HISTORICALLOCATION: LocationV2,
    SensorThingsEntityGroups.HISTORICALLOCATIONS: LocationV2,
    SensorThingsEntity.DATASTREAM: DatastreamV2,
    SensorThingsEntityGroups.DATASTREAMS: DatastreamV2,
    SensorThingsEntity.OBSERVATION: ObservationV2,
    SensorThingsEntityGroups.OBSERVATIONS: ObservationV2,
    SensorThingsEntity.OBSERVEDPROPERTY: ObservedPropertyV2,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: ObservedPropertyV2,
    SensorThingsEntity.FEATURE: Feature,
    SensorThingsEntityGroups.FEATURES: Feature,
    SensorThingsEntity.FEATURETYPE: FeatureType,
    SensorThingsEntityGroups.FEATURETYPES: FeatureType,
    # Tolerate configs / lookups that still say FeatureOfInterest under v2.
    SensorThingsEntity.FEATUREOFINTEREST: Feature,
    SensorThingsEntityGroups.FEATURESOFINTEREST: Feature,
}


def class_map_for(
    version: str | int | float | FrostVersions | None = None,
) -> SensorThingsClassMap:
    """Return the concrete STA class map for ``version`` (default: process FROST_VERSION)."""
    resolved = (
        FrostVersions.safe_parse(version) if version is not None else FROST_VERSION
    )
    if resolved == FrostVersions.v2:
        return _CLASS_MAP_V2
    return _CLASS_MAP_V1


def __getattr__(name: str):
    # Lazy so import-time FROST_VERSION / dotenv reconfigure is respected.
    if name == "SENSOR_THINGS_CLASS_MAP":
        return class_map_for()
    raise AttributeError(f"module {__name__!r} has no attribute {name}")

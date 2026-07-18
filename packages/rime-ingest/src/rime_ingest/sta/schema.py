"""
Enums and schema contracts for SensorThings models/config ingestion.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Tuple

from rime_ingest.frost.versions import FrostVersions, FROST_VERSION


class SensorThingsEntity(Enum):
    """Single entities from the SensorThings information model."""

    SENSOR = "Sensor"
    THING = "Thing"
    LOCATION = "Location"
    HISTORICALLOCATION = "HistoricalLocation"
    DATASTREAM = "Datastream"
    OBSERVATION = "Observation"
    OBSERVEDPROPERTY = "ObservedProperty"
    FEATUREOFINTEREST = "FeatureOfInterest"  # STA 1.x
    FEATURE = "Feature"  # STA 2.0 (replaces FeatureOfInterest)
    FEATURETYPE = "FeatureType"  # STA 2.0


class SensorThingsEntityGroups(Enum):
    """Entity groups from the SensorThings information model."""

    SENSORS = "Sensors"
    THINGS = "Things"
    LOCATIONS = "Locations"
    HISTORICALLOCATIONS = "HistoricalLocations"
    DATASTREAMS = "Datastreams"
    OBSERVATIONS = "Observations"
    OBSERVEDPROPERTIES = "ObservedProperties"
    FEATURESOFINTEREST = "FeaturesOfInterest"  # STA 1.x
    FEATURES = "Features"  # STA 2.0
    FEATURETYPES = "FeatureTypes"  # STA 2.0


# mapping groups (i.e. plural nouns such as Sensors) to entities (i.e. singular)
ENTITY_GROUPS_TO_ENTITIES: Dict[SensorThingsEntityGroups, SensorThingsEntity] = {
    SensorThingsEntityGroups.SENSORS: SensorThingsEntity.SENSOR,
    SensorThingsEntityGroups.THINGS: SensorThingsEntity.THING,
    SensorThingsEntityGroups.LOCATIONS: SensorThingsEntity.LOCATION,
    SensorThingsEntityGroups.HISTORICALLOCATIONS: SensorThingsEntity.HISTORICALLOCATION,
    SensorThingsEntityGroups.DATASTREAMS: SensorThingsEntity.DATASTREAM,
    SensorThingsEntityGroups.OBSERVATIONS: SensorThingsEntity.OBSERVATION,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: SensorThingsEntity.OBSERVEDPROPERTY,
    SensorThingsEntityGroups.FEATURESOFINTEREST: SensorThingsEntity.FEATUREOFINTEREST,
    SensorThingsEntityGroups.FEATURES: SensorThingsEntity.FEATURE,
    SensorThingsEntityGroups.FEATURETYPES: SensorThingsEntity.FEATURETYPE,
}


# inverse of ENTITY_GROUPS_TO_ENTITIES, useful when a singular entity ref must
# be slotted into a group-keyed iot_links bucket (e.g. a Datastream's Sensor).
ENTITIES_TO_ENTITY_GROUPS: Dict[SensorThingsEntity, SensorThingsEntityGroups] = {
    entity: group for group, entity in ENTITY_GROUPS_TO_ENTITIES.items()
}


# Wire / equality content fields per entity for STA 1.x (kept for callers that
# still index by entity enum rather than concrete class).
SENSOR_THINGS_ENTITY_FIELDS_V1: Dict[SensorThingsEntity, Tuple[str, ...]] = {
    SensorThingsEntity.THING: ("name", "description", "properties"),
    SensorThingsEntity.LOCATION: (
        "name",
        "description",
        "encodingType",
        "location",
        "properties",
    ),
    SensorThingsEntity.SENSOR: (
        "name",
        "description",
        "encodingType",
        "metadata",
        "properties",
    ),
    SensorThingsEntity.FEATUREOFINTEREST: (
        "name",
        "description",
        "encodingType",
        "feature",
        "properties",
    ),
    SensorThingsEntity.OBSERVEDPROPERTY: (
        "name",
        "description",
        "definition",
        "properties",
    ),
    SensorThingsEntity.DATASTREAM: (
        "name",
        "description",
        "observationType",
        "unitOfMeasurement",
        "properties",
    ),
    SensorThingsEntity.OBSERVATION: (
        "phenomenonTime",
        "resultTime",
        "result",
        "validTime",
        "parameters",
    ),
}

SENSOR_THINGS_ENTITY_FIELDS_V2: Dict[SensorThingsEntity, Tuple[str, ...]] = {
    SensorThingsEntity.THING: ("name", "description", "definition", "properties"),
    SensorThingsEntity.LOCATION: (
        "name",
        "description",
        "definition",
        "encodingType",
        "location",
        "properties",
    ),
    SensorThingsEntity.SENSOR: (
        "name",
        "description",
        "definition",
        "encodingType",
        "metadata",
        "properties",
    ),
    SensorThingsEntity.FEATURE: (
        "name",
        "description",
        "definition",
        "encodingType",
        "feature",
        "properties",
    ),
    SensorThingsEntity.FEATURETYPE: (
        "name",
        "description",
        "definition",
        "properties",
    ),
    SensorThingsEntity.OBSERVEDPROPERTY: (
        "name",
        "description",
        "definition",
        "properties",
    ),
    SensorThingsEntity.DATASTREAM: (
        "name",
        "description",
        "definition",
        "resultType",
        "resultEncoding",
        "properties",
    ),
    SensorThingsEntity.OBSERVATION: (
        "phenomenonTime",
        "resultTime",
        "result",
        "validTime",
        "properties",
    ),
}


def entity_fields_for(
    version: str | int | float | FrostVersions | None = None,
) -> Dict[SensorThingsEntity, Tuple[str, ...]]:
    """Return content-field tuples for the given STA version."""
    resolved = (
        FrostVersions.safe_parse(version) if version is not None else FROST_VERSION
    )
    if resolved == FrostVersions.v2:
        return SENSOR_THINGS_ENTITY_FIELDS_V2
    return SENSOR_THINGS_ENTITY_FIELDS_V1


# Back-compat alias: defaults to the active process version.
SENSOR_THINGS_ENTITY_FIELDS: Dict[SensorThingsEntity, Tuple[str, ...]] = (
    SENSOR_THINGS_ENTITY_FIELDS_V1
)


# these are the multiplicity relations between SensorThings entities. For example
# a Thing can have HistoricalLocations, Locations and Datastreams:
SENSOR_THINGS_MULTIPLICITIES = {
    SensorThingsEntity.SENSOR: [SensorThingsEntityGroups.DATASTREAMS],
    SensorThingsEntity.THING: [
        SensorThingsEntityGroups.HISTORICALLOCATIONS,
        SensorThingsEntityGroups.LOCATIONS,
        SensorThingsEntityGroups.DATASTREAMS,
    ],
    SensorThingsEntity.LOCATION: [
        SensorThingsEntityGroups.HISTORICALLOCATIONS,
        SensorThingsEntityGroups.THINGS,
    ],
    SensorThingsEntity.HISTORICALLOCATION: [
        SensorThingsEntity.THING,
        SensorThingsEntityGroups.LOCATIONS,
    ],
    SensorThingsEntity.DATASTREAM: [
        SensorThingsEntity.OBSERVEDPROPERTY,
        SensorThingsEntity.SENSOR,
        SensorThingsEntity.THING,
        SensorThingsEntityGroups.OBSERVATIONS,
    ],
    SensorThingsEntity.OBSERVATION: [
        SensorThingsEntity.DATASTREAM,
        SensorThingsEntity.FEATUREOFINTEREST,
    ],
    SensorThingsEntity.OBSERVEDPROPERTY: [SensorThingsEntityGroups.DATASTREAMS],
    SensorThingsEntity.FEATUREOFINTEREST: [SensorThingsEntityGroups.OBSERVATIONS],
    SensorThingsEntity.FEATURE: [SensorThingsEntityGroups.OBSERVATIONS],
}


CONFIG_YAML_REQUIRED_ENTITY_GROUPS: Tuple[SensorThingsEntityGroups, ...] = (
    SensorThingsEntityGroups.SENSORS,
    SensorThingsEntityGroups.THINGS,
    SensorThingsEntityGroups.LOCATIONS,
    SensorThingsEntityGroups.DATASTREAMS,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES,
)


_CONFIG_YAML_COMMON: Dict[SensorThingsEntityGroups, Dict[str, Any]] = {
    SensorThingsEntityGroups.SENSORS: {
        "name": str,
        "description": (str, dict, type(None)),
        "properties": (str, dict, type(None)),
        "encodingType": str,
        "metadata": str,
        "iot_links": dict,
    },
    SensorThingsEntityGroups.THINGS: {
        "name": str,
        "description": (str, type(None)),
        "properties": (str, dict, type(None)),
        "iot_links": dict,
    },
    SensorThingsEntityGroups.LOCATIONS: {
        "name": str,
        "description": (str, type(None)),
        "properties": (str, dict, type(None)),
        "encodingType": str,
        "location": dict,
        "iot_links": dict,
    },
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: {
        "name": str,
        "definition": str,
        "description": (str, type(None)),
        "properties": (str, type(None), dict),
    },
}

CONFIG_YAML_EXPECTED_CLASS_FIELDS_V1: Dict[SensorThingsEntityGroups, Dict[str, Any]] = {
    **_CONFIG_YAML_COMMON,
    SensorThingsEntityGroups.SENSORS: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.SENSORS],
        "description": (str, dict),  # mandatory in practice for v1 templates
    },
    SensorThingsEntityGroups.THINGS: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.THINGS],
        "description": str,
    },
    SensorThingsEntityGroups.LOCATIONS: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.LOCATIONS],
        "description": str,
    },
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.OBSERVEDPROPERTIES],
        "description": str,
    },
    SensorThingsEntityGroups.DATASTREAMS: {
        "name": str,
        "description": str,
        "observationType": str,
        "unitOfMeasurement": dict,
        "observedArea": dict,
        "phenomenon_time": (str, type(None)),
        "result_time": (str, type(None)),
        "properties": (dict, type(None)),
        "iot_links": dict,
    },
}

CONFIG_YAML_EXPECTED_CLASS_FIELDS_V2: Dict[SensorThingsEntityGroups, Dict[str, Any]] = {
    **_CONFIG_YAML_COMMON,
    SensorThingsEntityGroups.SENSORS: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.SENSORS],
        "definition": (str, type(None)),
    },
    SensorThingsEntityGroups.THINGS: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.THINGS],
        "definition": (str, type(None)),
    },
    SensorThingsEntityGroups.LOCATIONS: {
        **_CONFIG_YAML_COMMON[SensorThingsEntityGroups.LOCATIONS],
        "definition": (str, type(None)),
    },
    SensorThingsEntityGroups.DATASTREAMS: {
        "name": str,
        "description": (str, type(None)),
        "definition": (str, type(None)),
        "resultType": dict,
        "resultEncoding": (dict, type(None)),
        "observedArea": dict,
        "phenomenon_time": (str, type(None)),
        "result_time": (str, type(None)),
        "properties": (dict, type(None)),
        "iot_links": dict,
    },
}


def config_yaml_expected_fields(
    version: str | int | float | FrostVersions | None = None,
) -> Dict[SensorThingsEntityGroups, Dict[str, Any]]:
    resolved = (
        FrostVersions.safe_parse(version) if version is not None else FROST_VERSION
    )
    if resolved == FrostVersions.v2:
        return CONFIG_YAML_EXPECTED_CLASS_FIELDS_V2
    return CONFIG_YAML_EXPECTED_CLASS_FIELDS_V1


# Back-compat: process-default (usually v1.1 at import).
CONFIG_YAML_EXPECTED_CLASS_FIELDS = CONFIG_YAML_EXPECTED_CLASS_FIELDS_V1


CONFIG_YAML_EXPECTED_IOT_LINK_GROUPS: Dict[
    SensorThingsEntityGroups, Tuple[SensorThingsEntityGroups, ...]
] = {
    SensorThingsEntityGroups.SENSORS: (SensorThingsEntityGroups.DATASTREAMS,),
    SensorThingsEntityGroups.THINGS: (
        SensorThingsEntityGroups.DATASTREAMS,
        SensorThingsEntityGroups.LOCATIONS,
    ),
    SensorThingsEntityGroups.LOCATIONS: (SensorThingsEntityGroups.THINGS,),
    SensorThingsEntityGroups.DATASTREAMS: (
        SensorThingsEntityGroups.OBSERVEDPROPERTIES,
        SensorThingsEntityGroups.SENSORS,
        SensorThingsEntityGroups.THINGS,
    ),
}

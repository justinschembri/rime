"""
Enums and schema contracts for SensorThings models/config ingestion.
"""

from enum import Enum
from typing import Any, Dict, Tuple


class SensorThingsEntity(Enum):
    """Single entities from the SensorThings information model."""

    SENSOR = "Sensor"
    THING = "Thing"
    LOCATION = "Location"
    HISTORICALLOCATIONS = "HistoricalLocation"
    DATASTREAM = "Datastream"
    OBSERVATION = "Observation"
    OBSERVEDPROPERTY = "ObservedProperty"
    FEATUREOFINTEREST = "FeatureOfInterest"


class SensorThingsEntityGroups(Enum):
    """Entity groups from the SensorThings information model."""

    SENSORS = "Sensors"
    THINGS = "Things"
    LOCATIONS = "Locations"
    HISTORICALLOCATIONS = "HistoricalLocations"
    DATASTREAMS = "Datastreams"
    OBSERVATIONS = "Observations"
    OBSERVEDPROPERTIES = "ObservedProperties"
    FEATURESOFINTEREST = "FeaturesOfInterest"


# mapping groups (i.e. plural nouns such as Sensors) to entities (i.e. singular)
ENTITY_GROUPS_TO_ENTITIES: Dict[SensorThingsEntityGroups, SensorThingsEntity] = {
    SensorThingsEntityGroups.SENSORS: SensorThingsEntity.SENSOR,
    SensorThingsEntityGroups.THINGS: SensorThingsEntity.THING,
    SensorThingsEntityGroups.LOCATIONS: SensorThingsEntity.LOCATION,
    SensorThingsEntityGroups.HISTORICALLOCATIONS: SensorThingsEntity.HISTORICALLOCATIONS,
    SensorThingsEntityGroups.DATASTREAMS: SensorThingsEntity.DATASTREAM,
    SensorThingsEntityGroups.OBSERVATIONS: SensorThingsEntity.OBSERVATION,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: SensorThingsEntity.OBSERVEDPROPERTY,
    SensorThingsEntityGroups.FEATURESOFINTEREST: SensorThingsEntity.FEATUREOFINTEREST,
}


# permissible fields for SensorThings objects:
SENSOR_THINGS_ENTITY_FIELDS: Dict[SensorThingsEntity, Tuple[str, ...]] = {
    SensorThingsEntity.THING: (
        "name",
        "description",
        "properties",
    ),
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
    ),
}


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
    SensorThingsEntity.HISTORICALLOCATIONS: [
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
}


CONFIG_YAML_REQUIRED_ENTITY_GROUPS: Tuple[SensorThingsEntityGroups, ...] = (
    SensorThingsEntityGroups.SENSORS,
    SensorThingsEntityGroups.THINGS,
    SensorThingsEntityGroups.LOCATIONS,
    SensorThingsEntityGroups.DATASTREAMS,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES,
)


CONFIG_YAML_EXPECTED_CLASS_FIELDS: Dict[SensorThingsEntityGroups, Dict[str, Any]] = {
    SensorThingsEntityGroups.SENSORS: {
        "name": str,
        "description": (str, dict),
        "properties": (str, dict),
        "encodingType": str,
        "metadata": str,
        "iot_links": dict,
    },
    SensorThingsEntityGroups.THINGS: {
        "name": str,
        "description": str,
        "properties": (str, dict, type(None)),
        "iot_links": dict,
    },
    SensorThingsEntityGroups.LOCATIONS: {
        "name": str,
        "description": str,
        "properties": (str, dict, type(None)),
        "encodingType": str,
        "location": dict,
        "iot_links": dict,
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
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: {
        "name": str,
        "definition": str,
        "description": str,
        "properties": (str, type(None)),
    },
}


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

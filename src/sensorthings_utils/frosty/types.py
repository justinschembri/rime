"""FROST server types."""
#standard
from typing import Iterator, Any
from enum import Enum

from sensorthings_utils.sensor_things.schema import SensorThingsEntity, SensorThingsEntityGroups
#internal
#external

FrostUrl = str

class FrostVersions(Enum):
    v1 = "1"
    v1_1 = "1.1"

class FrostEndpoints(Enum):
    """FROST Server entity endpoints. Camelcase for conistency."""
    DATASTREAMS = "/Datastreams"
    FEATURESOFINTEREST = "/FeaturesOfInterest"
    HISTORICALLOCATIONS = "/HistoricalLocations"
    LOCATIONS = "/Locations"
    OBSERVATIONS = "/Observations"
    OBSERVEDPROPERTIES = "/ObservedProperties"
    SENSORS = "/Sensors"
    THINGS = "/Things"

class FrostParams(Enum):
    """FROST Server query params."""
    TOP="$top"
    SKIP="$skip"
    COUNT="$count"
    ORDER="$orderBy"
    EXPAND="$expand"
    SELECT="$select"
    FILTER="$filter"
    
NAVIGATION_LINKS_TO_ENTITY:dict[str, SensorThingsEntity | SensorThingsEntityGroups] = {
        "Sensor@iot.navigationLink" : SensorThingsEntity.SENSOR,
        "Sensors@iot.navigationLink" : SensorThingsEntityGroups.SENSORS,
        "Thing@iot.navigationLink" : SensorThingsEntity.THING,
        "Things@iot.navigationLink" : SensorThingsEntityGroups.THINGS,
        "Location@iot.navigationLink" : SensorThingsEntity.LOCATION,
        "Locations@iot.navigationLink" : SensorThingsEntityGroups.LOCATIONS,
        "HistoricalLocation@iot.navigationLink" : SensorThingsEntity.HISTORICALLOCATION,
        "HistoricalLocations@iot.navigationLink" : SensorThingsEntityGroups.HISTORICALLOCATIONS,
        "Datastream@iot.navigationLink" : SensorThingsEntity.DATASTREAM,
        "Datastreams@iot.navigationLink" : SensorThingsEntityGroups.DATASTREAMS,
        "Observation@iot.navigationLink" : SensorThingsEntity.OBSERVATION,
        "Observations@iot.navigationLink" : SensorThingsEntityGroups.OBSERVATIONS,
        "ObservedProperty@iot.navigationLink" : SensorThingsEntity.OBSERVEDPROPERTY,
        "ObservedProperties@iot.navigationLink" : SensorThingsEntityGroups.OBSERVEDPROPERTIES,
        "FeatureOfInterest@iot.navigationLink" : SensorThingsEntity.FEATUREOFINTEREST,
        "FeaturesOfInterest@iot.navigationLink" : SensorThingsEntityGroups.FEATURESOFINTEREST,
        }  

ENTITY_TO_FROST_ENDPOINT: dict[SensorThingsEntity, FrostEndpoints] = {
    SensorThingsEntity.SENSOR: FrostEndpoints.SENSORS,
    SensorThingsEntity.THING: FrostEndpoints.THINGS,
    SensorThingsEntity.LOCATION: FrostEndpoints.LOCATIONS,
    SensorThingsEntity.HISTORICALLOCATION: FrostEndpoints.HISTORICALLOCATIONS,
    SensorThingsEntity.DATASTREAM: FrostEndpoints.DATASTREAMS,
    SensorThingsEntity.OBSERVATION: FrostEndpoints.OBSERVATIONS,
    SensorThingsEntity.OBSERVEDPROPERTY: FrostEndpoints.OBSERVEDPROPERTIES,
    SensorThingsEntity.FEATUREOFINTEREST: FrostEndpoints.FEATURESOFINTEREST,
}

FrostResultPageIterator = Iterator[list[dict[str, Any]]]


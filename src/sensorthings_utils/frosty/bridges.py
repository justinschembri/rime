"""Bridge mappings between SensorThings domain and FROST wire protocol."""

from sensorthings_utils.sensor_things.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

from .types import FrostEndpoints

NAVIGATION_LINKS_TO_ENTITY: dict[str, SensorThingsEntity | SensorThingsEntityGroups] = {
    "Sensor@iot.navigationLink": SensorThingsEntity.SENSOR,
    "Sensors@iot.navigationLink": SensorThingsEntityGroups.SENSORS,
    "Thing@iot.navigationLink": SensorThingsEntity.THING,
    "Things@iot.navigationLink": SensorThingsEntityGroups.THINGS,
    "Location@iot.navigationLink": SensorThingsEntity.LOCATION,
    "Locations@iot.navigationLink": SensorThingsEntityGroups.LOCATIONS,
    "HistoricalLocation@iot.navigationLink": SensorThingsEntity.HISTORICALLOCATION,
    "HistoricalLocations@iot.navigationLink": SensorThingsEntityGroups.HISTORICALLOCATIONS,
    "Datastream@iot.navigationLink": SensorThingsEntity.DATASTREAM,
    "Datastreams@iot.navigationLink": SensorThingsEntityGroups.DATASTREAMS,
    "Observation@iot.navigationLink": SensorThingsEntity.OBSERVATION,
    "Observations@iot.navigationLink": SensorThingsEntityGroups.OBSERVATIONS,
    "ObservedProperty@iot.navigationLink": SensorThingsEntity.OBSERVEDPROPERTY,
    "ObservedProperties@iot.navigationLink": SensorThingsEntityGroups.OBSERVEDPROPERTIES,
    "FeatureOfInterest@iot.navigationLink": SensorThingsEntity.FEATUREOFINTEREST,
    "FeaturesOfInterest@iot.navigationLink": SensorThingsEntityGroups.FEATURESOFINTEREST,
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

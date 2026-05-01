"""Lookup tables mapping SensorThings domain types to FROST wire-protocol values.

These dicts are the single source of truth for converting between the
OGC SensorThings API entity model (as represented by the local enums) and the
URL path segments / navigation-link keys used by FROST Server responses.
"""

from rime.sensor_things.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

from .types import FrostEndpoints

NAVIGATION_LINKS_TO_ENTITY: dict[str, SensorThingsEntity | SensorThingsEntityGroups] = {
    # Maps the ``@iot.navigationLink`` key suffix returned by FROST to the
    # corresponding local entity enum. Singular keys resolve to
    # ``SensorThingsEntity``; plural keys to ``SensorThingsEntityGroups``.
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

"""Centralized SensorThings mapping constants."""

from rime_ingest.sta.core import (
    Datastream,
    Location,
    Observation,
    ObservedProperty,
    Sensor,
    SensorThingsObject,
    Thing,
)
from rime_ingest.sta.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

SensorThingsObjectMapKey = SensorThingsEntity | SensorThingsEntityGroups
SensorThingsClassMap = dict[SensorThingsObjectMapKey, type[SensorThingsObject | Observation]]

SENSOR_THINGS_CLASS_MAP: SensorThingsClassMap = {
    SensorThingsEntity.SENSOR: Sensor,
    SensorThingsEntityGroups.SENSORS: Sensor,
    SensorThingsEntity.THING: Thing,
    SensorThingsEntityGroups.THINGS: Thing,
    SensorThingsEntity.LOCATION: Location,
    SensorThingsEntityGroups.LOCATIONS: Location,
    SensorThingsEntity.HISTORICALLOCATION: Location,
    SensorThingsEntityGroups.HISTORICALLOCATIONS: Location,
    SensorThingsEntity.DATASTREAM: Datastream,
    SensorThingsEntityGroups.DATASTREAMS: Datastream,
    SensorThingsEntity.OBSERVATION: Observation,
    SensorThingsEntityGroups.OBSERVATIONS: Observation,
    SensorThingsEntity.OBSERVEDPROPERTY: ObservedProperty,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: ObservedProperty,
    SensorThingsEntity.FEATUREOFINTEREST: Thing,
    SensorThingsEntityGroups.FEATURESOFINTEREST: Thing,
}

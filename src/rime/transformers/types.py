"""Canonical data-types involved in various transformations."""

# standard
# external
from enum import Enum
# internal

SensorUUID = str


class CanonicalDatastreams(Enum):
    """
    Enumerations for various canonical datastream names. It is imperative that
    datastream names passed in the ingest application match the names of Datastream
    entity in the FROST server. Thus:
    
    - This enum should be called by a `Normalizer` sublcass when applying the
    `.to_stObservation` method. 

    - The initial set-up which creates a FROST entity from a `SensorConfig` only
    allows datastream names which are part of this enum.
    """
    PHENOMENON_TIME = "phenomenon_time"
    BATTERY_LEVEL = "battery_level"
    HUMIDITY_INDOOR = "humidity"
    CO2_INDOOR = "co2"
    TEMP_IN = "temperature_indoor"
    LIGHT_LVL_IN = "light_level"
    PIR = "passive_infrared"
    PM10 = "particulate_matter_10"
    PM_2PT5 = "particulate_matter_2_5"
    G_PRESSURE_IN = "gauge_pressure"
    A_PRESSURE_IN = "absolute_pressure"
    NOISE_IN = "noise"
    TVOC = "total_volatile_organic_compounds"


class SupportedSensors(Enum):
    MILESIGHT_AM103L = "milesight.am103l"
    MILESIGHT_AM308L = "milesight.am308l"
    NETATMO_NWS03 = "netatmo.nws03"
    KINEMETRICS_ETNA2 = "kinemetrics.etna2"

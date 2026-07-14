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
    BATTERY_VOLTAGE = "battery_voltage"
    HUMIDITY_INDOOR = "humidity"
    AIR_HUMIDITY = "humidity_air"
    CO2_INDOOR = "co2"
    TEMP_IN = "temperature_indoor"
    AIR_TEMPERATURE = "temperature_air"
    LIGHT_LVL_IN = "light_level"
    PIR = "passive_infrared"
    PM10 = "particulate_matter_10"
    PM_2PT5 = "particulate_matter_2_5"
    G_PRESSURE_IN = "gauge_pressure"
    A_PRESSURE_IN = "absolute_pressure"
    NOISE_IN = "noise"
    TVOC = "total_volatile_organic_compounds"
    HNE = "HNE"
    HNN = "HNN"
    HNZ = "HNZ"

class SupportedSensors(Enum):
    MILESIGHT_AM103L = "milesight.am103l"
    MILESIGHT_AM308L = "milesight.am308l"
    NETATMO_NWS03 = "netatmo.nws03"
    KINEMETRICS_ETNA2 = "kinemetrics.etna2"
    DRAGINO_LSN50V2_S31 = "dragino.lsn50v2-s31" 

class SupportedProviders(Enum):
    NETATMO = "netatmo"
    THE_THINGS_NETWORK = "ttn"
    RIME_HTTP = "rime-http"

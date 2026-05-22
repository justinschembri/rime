# standard
import logging
from typing import Callable

# internal
from ..types import CanonicalDatastreams
from .core import Normalizer

logger = logging.getLogger(__name__)


class MilesightAm103lNormalizer(Normalizer):
    battery: int
    co2: float
    humidity: float
    temperature: float

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "battery": CanonicalDatastreams.BATTERY_LEVEL,
        "co2": CanonicalDatastreams.CO2_INDOOR,
        "humidity": CanonicalDatastreams.HUMIDITY_INDOOR,
        "temperature": CanonicalDatastreams.TEMP_IN,
    }

    TRANSFORM: dict[str, Callable] = {}


class MilesightAm308lNormalizer(Normalizer):
    battery: int
    co2: float
    humidity: float
    light_level: int
    pir: str
    pm10: int
    pm2_5: int
    pressure: float
    temperature: float
    tvoc: float

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "battery": CanonicalDatastreams.BATTERY_LEVEL,
        "co2": CanonicalDatastreams.CO2_INDOOR,
        "humidity": CanonicalDatastreams.HUMIDITY_INDOOR,
        "light_level": CanonicalDatastreams.LIGHT_LVL_IN,
        "pir": CanonicalDatastreams.PIR,
        "pm10": CanonicalDatastreams.PM10,
        "pm2_5": CanonicalDatastreams.PM_2PT5,
        "pressure": CanonicalDatastreams.G_PRESSURE_IN,
        "temperature": CanonicalDatastreams.TEMP_IN,
        "tvoc": CanonicalDatastreams.TVOC,
    }

    TRANSFORM: dict[str, Callable] = {
        "pir": lambda x: True if x == "trigger" else False,
    }

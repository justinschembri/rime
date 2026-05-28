# standard
import logging
from typing import Callable

# internal
from ..types import CanonicalDatastreams
from .core import Normalizer

logger = logging.getLogger(__name__)


class KinemetricsEtna2(Normalizer):
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


# standard
import logging
from typing import Callable

# internal
from ..types import CanonicalDatastreams
from .core import Normalizer

logger = logging.getLogger(__name__)


class DraginoLSN50v2_S31Normalizer(Normalizer):
    BatV: int
    TempC_SHT: float
    Hum_SHT: float

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "BatV": CanonicalDatastreams.BATTERY_VOLTAGE,
        "TempC_SHT": CanonicalDatastreams.AIR_TEMPERATURE,
        "Hum_SHT": CanonicalDatastreams.AIR_HUMIDITY,
        }

    TRANSFORM: dict[str, Callable] = {}


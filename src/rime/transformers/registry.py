"""Top-level normalizer registry.

Maps supported sensor models to their observation normalizer implementation.
"""

from typing import Type

from .normalizers.core import VendorObservationNormalizer
from .normalizers import milesight
from .normalizers import netatmo
from .types import SupportedSensors

NORMALIZER_MAP: dict[SupportedSensors, Type[VendorObservationNormalizer]] = {
    SupportedSensors.MILESIGHT_AM103L: milesight.MilesightAm103lNormalizer,
    SupportedSensors.MILESIGHT_AM308L: milesight.MilesightAm308lNormalizer,
    SupportedSensors.NETATMO_NWS03: netatmo.NetatmoNWS03,
}

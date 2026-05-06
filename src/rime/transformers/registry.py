"""Top-level transformer registry.

Maps supported sensor models to their observation transformer implementation.
"""

from typing import Type

from .normalizers.core import VendorObservationTransformer
from .normalizers import milesight
from .normalizers import netatmo
from .types import SupportedSensors

TRANSFORMER_MAP: dict[SupportedSensors, Type[VendorObservationTransformer]] = {
    SupportedSensors.MILESIGHT_AM103L: milesight.MilesightAm103lPayload,
    SupportedSensors.MILESIGHT_AM308L: milesight.MilesightAm308lPayload,
    SupportedSensors.NETATMO_NWS03: netatmo.NetatmoNWS03,
}


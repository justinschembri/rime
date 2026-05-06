"""Per-model ingest component wiring.

Each sensor model resolves a deserializer, decoder, and transformer class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Type

from .decoders import Decoder, NullDecoder
from .deserializers import Deserializer, NullDeserializer
from .normalizers.core import VendorObservationTransformer
from .normalizers.milesight import MilesightAm103lPayload, MilesightAm308lPayload
from .normalizers.netatmo import NetatmoNWS03
from .types import SupportedSensors


@dataclass(frozen=True, slots=True)
class IngestModelComponents:
    deserializer: Type[Deserializer]
    decoder: Type[Decoder]
    transformer: Type[VendorObservationTransformer]


INGEST_COMPONENT_MAP: dict[SupportedSensors, IngestModelComponents] = {
    SupportedSensors.MILESIGHT_AM103L: IngestModelComponents(
        deserializer=NullDeserializer,
        decoder=NullDecoder,
        transformer=MilesightAm103lPayload,
    ),
    SupportedSensors.MILESIGHT_AM308L: IngestModelComponents(
        deserializer=NullDeserializer,
        decoder=NullDecoder,
        transformer=MilesightAm308lPayload,
    ),
    SupportedSensors.NETATMO_NWS03: IngestModelComponents(
        deserializer=NullDeserializer,
        decoder=NullDecoder,
        transformer=NetatmoNWS03,
    ),
}


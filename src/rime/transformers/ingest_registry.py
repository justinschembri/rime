"""Per-model ingest component wiring.

Each sensor model resolves an optional deserializer, an optional decoder,
a parser, and a normalizer class.

``deserializer`` and ``decoder`` default to ``None`` (skip).  Set them only
when the native payload arriving from decapsulation is not yet in a form the
parser can handle:

- ``deserializer``: opaque bytes/str → structured Python object
  (e.g. base64 frm_payload → dict via CBOR or a vendor codec)
- ``decoder``: structured values → semantic observation values
  (e.g. raw ADC register → temperature float, bit-field expansion)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type

from .decoders.core import Decoder
from .deserializers.core import Deserializer
from .normalizers.core import Normalizer
from .normalizers.milesight import (
    MilesightAm103lNormalizer,
    MilesightAm308lNormalizer,
)
from .normalizers.netatmo import NetatmoNWS03
from .parsers import MilesightAm103lParser, MilesightAm308lParser, NetatmoNWS03Parser, Parser
from .types import SupportedSensors


@dataclass(frozen=True, slots=True)
class IngestModelComponents:
    parser: Type[Parser]
    normalizer: Type[Normalizer]
    deserializer: Type[Deserializer] | None = None
    decoder: Type[Decoder] | None = None


INGEST_COMPONENT_MAP: dict[SupportedSensors, IngestModelComponents] = {
    SupportedSensors.MILESIGHT_AM103L: IngestModelComponents(
        parser=MilesightAm103lParser,
        normalizer=MilesightAm103lNormalizer,
    ),
    SupportedSensors.MILESIGHT_AM308L: IngestModelComponents(
        parser=MilesightAm308lParser,
        normalizer=MilesightAm308lNormalizer,
    ),
    SupportedSensors.NETATMO_NWS03: IngestModelComponents(
        parser=NetatmoNWS03Parser,
        normalizer=NetatmoNWS03,
    ),
}

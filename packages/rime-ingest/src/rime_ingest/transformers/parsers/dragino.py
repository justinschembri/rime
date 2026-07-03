"""
Dragino sensor parser: decoded_payload dict -> ObservationRecord.

Shared by all Dragino models.The decoded payload 
"""

from __future__ import annotations

from ...exceptions import MissingPayloadKeysError, UnpackError
from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser

LSN50V2_S31_REQUIRED = {"BatV", "TempC_SHT", "Hum_SHT"}


class DraginoLSN50v2_S31Parser(Parser):
    """Parse a Dragino LSN50v2-S31 decapsulated payload into an `ObservationRecord`.

    The payload shape is provider-independent (it is the LoRaWAN application
    layer decoded output, identical whether arriving via TTN or a future direct
    MQTT broker).  Timestamps must come from the provider envelope since the
    Dragino payload carries no sample time of its own.
    """

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        raw = identified.payload
        if not isinstance(raw, dict):
            raise UnpackError(TypeError("Dragino LSN50v2-S31 payload must be a dict."))

        missing = LSN50V2_S31_REQUIRED - raw.keys()
        if missing:
            raise MissingPayloadKeysError(KeyError(f"Missing required LSN50v2-S31 fields: {missing}"))

        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations=dict(raw),
            provider_timestamp=envelope.provider_timestamp if envelope else None,
            phenomenon_timestamp=envelope.phenomenon_timestamp if envelope else None,
        )


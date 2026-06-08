"""Milesight sensor parser: decoded_payload dict -> ObservationRecord.

Shared by all Milesight models (AM103L, AM308L, ...).  The decoded payload
arriving from TTN (or any future direct provider) is already lowercase and
observation-only — no field renaming or dropping is needed.  The parser's job
here is timestamp resolution and field validation.
"""

from __future__ import annotations

from ...exceptions import MissingPayloadKeysError, UnpackError
from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser

_AM103L_REQUIRED = {"battery", "co2", "humidity", "temperature"}
_AM308L_REQUIRED = {"battery", "co2", "humidity", "light_level", "pir", "pm10", "pm2_5", "pressure", "temperature", "tvoc"}


class MilesightAm103lParser(Parser):
    """Parse a Milesight AM103L decoded payload into an :class:`~rime.transformers.messages.ObservationRecord`.

    The payload shape is provider-independent (it is the LoRaWAN application
    layer decoded output, identical whether arriving via TTN or a future direct
    MQTT broker).  Timestamps come from the provider envelope since the
    Milesight payload carries no sample time of its own.
    """

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        raw = identified.payload
        if not isinstance(raw, dict):
            raise UnpackError(TypeError("Milesight AM103L payload must be a dict."))

        missing = _AM103L_REQUIRED - raw.keys()
        if missing:
            raise MissingPayloadKeysError(KeyError(f"Missing required AM103L fields: {missing}"))

        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations=dict(raw),
            provider_timestamp=envelope.provider_timestamp if envelope else None,
            phenomenon_timestamp=envelope.phenomenon_timestamp if envelope else None,
        )


class MilesightAm308lParser(Parser):
    """Parse a Milesight AM308L decoded payload into an :class:`~rime.transformers.messages.ObservationRecord`.

    Same contract as :class:`MilesightAm103lParser`; validates the larger
    AM308L field set.
    """

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        raw = identified.payload
        if not isinstance(raw, dict):
            raise UnpackError(TypeError("Milesight AM308L payload must be a dict."))

        missing = _AM308L_REQUIRED - raw.keys()
        if missing:
            raise MissingPayloadKeysError(KeyError(f"Missing required AM308L fields: {missing}"))

        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations=dict(raw),
            provider_timestamp=envelope.provider_timestamp if envelope else None,
            phenomenon_timestamp=envelope.phenomenon_timestamp if envelope else None,
        )

"""Eltek datalogger parser: one CSV row dict -> ObservationRecord."""

from __future__ import annotations

from ...exceptions import UnpackError
from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser


class EltekDataloggerParser(Parser):
    """Parse one Eltek CSV row (post fan-out) into an :class:`ObservationRecord`."""

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        raw = identified.payload
        if not isinstance(raw, dict):
            raise UnpackError(
                TypeError(
                    f"Eltek row payload must be a dict, got {type(raw).__name__}."
                )
            )

        observations = {
            key: value
            for key, value in raw.items()
            if value is not None
        }
        if not observations:
            raise UnpackError(ValueError("Eltek row contains no observation values."))

        phenomenon_timestamp = (
            envelope.phenomenon_timestamp if envelope else None
        )
        provider_timestamp = envelope.provider_timestamp if envelope else None

        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations=observations,
            provider_timestamp=provider_timestamp,
            phenomenon_timestamp=phenomenon_timestamp,
        )

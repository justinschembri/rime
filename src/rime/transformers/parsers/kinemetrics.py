"""Kinemetrics ETNA2 parser: point-in-time sample -> ObservationRecord."""

from __future__ import annotations

from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser


class KinemetricsEtna2Parser(Parser):
    """Parse a Kinemetrics ETNA2 sample into an :class:`~rime.transformers.messages.ObservationRecord`."""

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        if not envelope or not envelope.datastream_name:
            raise ValueError("Expected envelope datastream name for Kinemetrics ETNA2 payload.")
        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations={envelope.datastream_name: identified.payload},
            provider_timestamp=envelope.provider_timestamp,
            phenomenon_timestamp=envelope.phenomenon_timestamp,
        )

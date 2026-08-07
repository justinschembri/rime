"""
Parse a payload whose identity / STA datastream is carried exclusively by the 
provider envelope, meaning that the Sensor does not deliver any information 
about itself. 

This is common for simple sensors connected with transmitters and data-loggers.
"""

from __future__ import annotations

from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser

NO_DATA_KEYS = {
        "",
        "open",
        "no_data",
        "no data", 
        }

class NumericChannelEnvelopeParser(Parser):
    """``envelope.datastream_name`` → single observation key (SeedLink / multi-channel)."""

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        if not envelope or not envelope.datastream_name:
            raise ValueError("Expected envelope datastream_name for channel sample.")
        raw = identified.payload
        if isinstance(raw, str) and raw.strip().lower() in NO_DATA_KEYS:
            value = None
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Channel value not numeric: {raw!r}") from e
        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations={envelope.datastream_name: value},
            provider_timestamp=envelope.provider_timestamp,
            phenomenon_timestamp=envelope.phenomenon_timestamp,
        )

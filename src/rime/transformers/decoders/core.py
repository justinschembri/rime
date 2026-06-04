"""Model-level decoder base class: structured form → semantic values."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..messages import EnvelopeMetadata, IdentifiedPayload, IdentifiedTimeSeriesPayload


class Decoder(ABC):
    """ABC for model-specific payload decoders.

    Decoding is the process by which model-specific encoded data is decoded into
    some other representation, e.g., accelerometer data → physical units, bit-field
    expansion.

    Model-specific decoding occurs after a message is decapsulated and should
    modify the `payload` or `payloads` of an `IdentifiedPayload` or 
    `IdentifiedTimeSeriesPayload` respectively.

    Returns a new, IdentifiedPayload | IdentifiedTimeSeriesPayload with decoded
    payloads.
    """

    @staticmethod
    @abstractmethod
    def decode(
        identified_payload: IdentifiedPayload | IdentifiedTimeSeriesPayload,
        envelope_metadata: EnvelopeMetadata | None,
        ) -> IdentifiedPayload | IdentifiedTimeSeriesPayload:
        """Return *identified* with its `payload` decoded."""
        

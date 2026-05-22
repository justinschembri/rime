"""Model-level decoder base class: structured form → semantic values."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..messages import EnvelopeMetadata, IdentifiedPayload


class Decoder(ABC):
    """Optional model-specific payload decoder.

    Use when a sensor payload is already structured (e.g. a dict of raw
    register values) but requires vendor-specific interpretation before
    parsing — e.g. ADC counts → physical units, bit-field expansion,
    decryption, or decompression of a structured container.

    Returns a new :class:`~rime.transformers.messages.IdentifiedPayload`
    with the same ``sensor_uuid`` but a semantically decoded ``payload`` value.

    If the payload arriving from the decapsulator (or a preceding
    :class:`~rime.transformers.deserializers.core.Deserializer`) is already in
    observation-ready form, leave the slot as ``None`` in
    :class:`~rime.transformers.ingest_registry.IngestModelComponents`.
    """

    @staticmethod
    @abstractmethod
    def decode(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> IdentifiedPayload:
        """Return *identified* with its ``payload`` decoded."""
        ...

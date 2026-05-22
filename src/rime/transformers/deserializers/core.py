"""Model-level deserializer base class: opaque bytes/str → structured form."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..decapsulators.types import EnvelopeMetadata, IdentifiedPayload


class Deserializer(ABC):
    """Optional model-specific payload deserializer.

    Use when a sensor payload arrives as opaque bytes or a serialized string
    (e.g. raw LoRaWAN ``frm_payload`` in base64, CBOR, MessagePack) and must
    be converted into a Python structure before the decoder or parser can
    operate on it.

    Returns a new :class:`~rime.transformers.decapsulators.types.IdentifiedPayload`
    with the same ``sensor_uuid`` but a deserialized ``payload`` value.

    Most models whose provider already delivers a decoded dict (TTN
    ``decoded_payload``, Netatmo ``dashboard_data``) do not need a deserializer
    — leave the slot as ``None`` in
    :class:`~rime.transformers.ingest_registry.IngestModelComponents`.
    """

    @staticmethod
    @abstractmethod
    def deserialize(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> IdentifiedPayload:
        """Return *identified* with its ``payload`` deserialized."""
        ...

"""Identity parser — payload needs no model-specific pre-processing."""

from __future__ import annotations

from ..decapsulators.types import EnvelopeMetadata, IdentifiedPayload
from ..messages import ParsedMessage
from .core import Parser


class NullParser(Parser):
    """Pass-through: wraps the identified payload directly into a ParsedMessage.

    Timestamps are sourced from the envelope when present.  Used as the
    default model component in :mod:`rime.transformers.ingest_registry` when
    the native payload requires no structural transformation before the
    transformer stage.
    """

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ParsedMessage:
        return ParsedMessage(
            sensor_uuid=identified.sensor_uuid,
            body=identified.payload,
            provider_timestamp=envelope.provider_timestamp if envelope else None,
            phenomenon_timestamp=envelope.phenomenon_timestamp if envelope else None,
        )

"""Compose ingress steps: deserialize → decapsulate → decode → parse."""

from __future__ import annotations

from typing import Any

from .decoders.null import NullDecoder
from .deserializers.null import NullDeserializer
from .envelopes.types import Decapsulator
from .messages import ParsedMessage


def ingest_to_parsed_messages(
    app_payload: Any,
    *,
    decapsulator: type[Decapsulator],
    deserializer: Any = NullDeserializer,
    decoder: Any = NullDecoder,
) -> list[ParsedMessage]:
    """Run the full chain for one application-level ingest.

    Defaults use :class:`~.deserializers.null.NullDeserializer` and
    :class:`~.decoders.null.NullDecoder` (identity). Replace with vendor
    implementations as they land under ``deserializers/`` and ``decoders/``.
    """
    wire = deserializer.deserialize(app_payload)
    decapped = decapsulator.decapsulate(wire)
    return [ParsedMessage.from_decoded(decoder.decode(m)) for m in decapped]

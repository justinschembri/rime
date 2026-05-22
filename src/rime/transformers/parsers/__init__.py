"""Parsers — identified payload + envelope -> :class:`ParsedMessage`.

A parser is the model-specific bridge between decapsulation and
transformation.  It receives one :class:`~rime.transformers.decapsulators.types.IdentifiedPayload`
(native sensor fragment, already stripped of provider framing) together with
optional :class:`~rime.transformers.decapsulators.types.EnvelopeMetadata` and
produces a :class:`~rime.transformers.messages.ParsedMessage` with
``sensor_uuid``, ``body``, and resolved timestamps.
"""

from __future__ import annotations

from .core import Parser
from .milesight import MilesightAm103lParser, MilesightAm308lParser
from .netatmo import NetatmoNWS03Parser
from .null import NullParser

__all__ = [
    "Parser",
    "MilesightAm103lParser",
    "MilesightAm308lParser",
    "NetatmoNWS03Parser",
    "NullParser",
]

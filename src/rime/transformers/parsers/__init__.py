"""Parsers — identified payload + envelope -> :class:`~rime.transformers.messages.ObservationRecord`.

A parser is the model-specific bridge between decapsulation and normalization.
It receives one :class:`~rime.transformers.messages.IdentifiedPayload` (native
sensor fragment, already stripped of provider framing) together with optional
:class:`~rime.transformers.messages.EnvelopeMetadata` and produces an
:class:`~rime.transformers.messages.ObservationRecord` with ``sensor_uuid``,
``observations``, and resolved timestamps.

Every sensor model must register a concrete :class:`Parser` — there is no
pass-through default.  Observations must be fully validated and timestamped
before the :class:`~rime.transformers.messages.ObservationRecord` is returned.
"""

from __future__ import annotations

from .core import Parser
from .milesight import MilesightAm103lParser, MilesightAm308lParser
from .netatmo import NetatmoNWS03Parser

__all__ = [
    "Parser",
    "MilesightAm103lParser",
    "MilesightAm308lParser",
    "NetatmoNWS03Parser",
]

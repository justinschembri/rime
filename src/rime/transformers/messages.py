"""Ingress pipeline message types (Message family).

:class:`ParsedMessage` is the output of the parser stage and the input to
transformers.  It carries a fully-resolved sensor identity, an opaque ``body``
(the native sensor reading — most commonly a ``dict[str, Any]`` for IoT
sensors), and resolved timestamps.

:class:`DecodedMessage` is retained for optional model-specific decoder
components that perform binary / codec expansion *before* parsing.  It is
not part of the default pipeline (which uses :class:`~rime.transformers.parsers.null.NullParser`
directly), but remains available for future binary protocol support.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .types import SensorUUID


@dataclass(frozen=True, slots=True)
class DecodedMessage:
    """Payload with transport/encoding undone; ``payload`` still ``Any``.

    Used only when a model-specific :class:`~rime.transformers.decoders.core.Decoder`
    is registered.  Not part of the default ``NullParser`` path.
    """

    sensor_uuid: SensorUUID
    payload: Any
    provider_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class ParsedMessage:
    """Fully-resolved per-sensor record ready for the transformer.

    Produced by :class:`~rime.transformers.parsers.core.Parser` subclasses.

    ``body`` is intentionally ``Any`` — transformers are responsible for
    knowing the expected shape.  For standard IoT sensors this will be a
    ``dict[str, Any]``; time-series sources (e.g. SeedLink) may use other
    types.
    """

    sensor_uuid: SensorUUID
    body: Any
    provider_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None

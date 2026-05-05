"""Ingress pipeline message types after decapsulation (Message family).

``DecapsulatedMessage`` (:mod:`rime.transformers.envelopes.types`) feeds
``DecodedMessage`` (transport / encoding undone) then ``ParsedMessage``
(typed ``dict[str, Any]`` body for transformers).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..exceptions import UnpackError

from .envelopes.types import DecapsulatedMessage
from .types import SensorUUID


@dataclass(frozen=True, slots=True)
class DecodedMessage:
    """Payload interpreted for transport/format; ``payload`` still ``Any``."""

    sensor_id: SensorUUID
    payload: Any
    application_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None

    @classmethod
    def from_decapsulated(cls, msg: DecapsulatedMessage) -> DecodedMessage:
        return cls(
            sensor_id=msg.sensor_id,
            payload=msg.payload,
            application_timestamp=msg.application_timestamp,
            phenomenon_timestamp=msg.phenomenon_timestamp,
        )


@dataclass(frozen=True, slots=True)
class ParsedMessage:
    """Structured per-sensor body + routing/timing for STA transformers."""

    sensor_id: SensorUUID
    body: dict[str, Any]
    application_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None

    @classmethod
    def from_decoded(cls, msg: DecodedMessage) -> ParsedMessage:
        body = msg.payload
        if not isinstance(body, dict):
            raise UnpackError(
                TypeError(
                    "DecodedMessage payload must be dict[str, Any] before parse."
                )
            )
        return cls(
            sensor_id=msg.sensor_id,
            body=dict(body),
            application_timestamp=msg.application_timestamp,
            phenomenon_timestamp=msg.phenomenon_timestamp,
        )


def decapsulated_to_parsed_identity_decode(
    messages: list[DecapsulatedMessage],
) -> list[ParsedMessage]:
    """Decode (identity) then parse each decapsulated message to ``ParsedMessage``."""
    out: list[ParsedMessage] = []
    for msg in messages:
        decoded = DecodedMessage.from_decapsulated(msg)
        out.append(ParsedMessage.from_decoded(decoded))
    return out

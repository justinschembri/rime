"""Shared types after decapsulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..types import SensorUUID


@dataclass(frozen=True, slots=True)
class IdentifiedPayload:
    """A native sensor payload fragment paired with its registry identity.

    The ``payload`` is provider-independent: the same sensor model connected
    to a different upstream provider should produce the same ``payload`` shape.
    Identity extraction is provider-dependent and happens inside the
    decapsulator, not in downstream model components.
    """

    sensor_uuid: SensorUUID
    payload: Any


@dataclass(frozen=True, slots=True)
class EnvelopeMetadata:
    """Residual metadata from the provider envelope.

    Carries only information that is *not* embedded in the native sensor
    payload — e.g. gateway receive timestamps, channel/datastream hints from
    the provider envelope.  ``sensor_uuid`` is intentionally absent: identity
    lives on :class:`IdentifiedPayload`.
    """

    app_name: Optional[str] = None
    datastream_name: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    phenomenon_timestamp: Optional[datetime] = None
    other: Optional[Any] = None


@dataclass(frozen=True, slots=True)
class DecapsulatedMessage:
    """One wire payload stripped of provider-specific framing.

    ``sensor_payloads`` is a list of :class:`IdentifiedPayload` — one entry
    per logical sensor present in the original wire message (e.g. multiple
    Netatmo stations, or a single TTN device).  The same sensor model
    connected to a different upstream provider should produce the same
    ``payload`` shapes inside each entry.

    ``envelope_metadata`` carries leftover provider-level context that may be
    needed downstream (timestamps, datastream hints) but is *not* part of the
    sensor-native payload.
    """

    sensor_payloads: list[IdentifiedPayload]
    envelope_metadata: Optional[EnvelopeMetadata] = None


class Decapsulator(ABC):
    """ABC for decapsulators that strip vendor/provider shells."""

    @staticmethod
    @abstractmethod
    def decapsulate(wire_payload: Any) -> DecapsulatedMessage:
        ...

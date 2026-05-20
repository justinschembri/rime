"""Shared types after decapsulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..types import SensorUUID


@dataclass(frozen=True, slots=True)
class EnvelopeMetadata:
    """
    Residual metadata from the payload envelope that may be required downstream
    for observation construction.
    """

    app_name: Optional[str] = None
    sensor_uuid: Optional[SensorUUID] = None
    datastream_name: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    other: Optional[Any] = None

@dataclass(frozen=True, slots=True)
class DecapsulatedMessage:
    """
    An upstream message from a provider stripped of uneccessary information and
    parsed on a payload-by-payload basis.

    Attributes
        sensor_payload (list[Any]): The native decoded, deserialized payload from the 
            sensor. An identical sensor model connected to a different provider should
            have the same shape as this.
        envelope_metadata (EnvelopeMetadata): residual metadata from the envelope
            which may be required downstream.
    """

    sensor_payloads: list[Any]
    envelope_metadata: Optional[EnvelopeMetadata] = None


class Decapsulator(ABC):
    """ABC for decapsulators that strip vendor/provider shells."""

    @staticmethod
    @abstractmethod
    def decapsulate(wire_payload: Any) -> DecapsulatedMessage:
        ...

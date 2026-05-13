"""Shared types after decapsulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..types import SensorUUID


@dataclass(frozen=True, slots=True)
class DecapsulatedMessage:
    """One routed sensor ingest: identity + timestamps + opaque payload body.

    The decapsulation step removes transport/provider scaffolding and keeps:

    - a **sensor key** usable with ``SensorConfig`` / ``sensor_registry``;
    - any **timing** hints needed downstream (provider-received vs phenomenon);
    - a **payload** that still reflects "what came from / about the sensor
      readings" before decoder/normalizer specialization.
    """

    sensor_id: SensorUUID
    payload: Any
    provider_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None


class Decapsulator(ABC):
    """ABC for decapsulators that strip vendor/provider shells."""

    @staticmethod
    @abstractmethod
    def decapsulate(wire_payload: Any) -> list[DecapsulatedMessage]:
        ...

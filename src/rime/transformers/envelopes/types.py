"""Shared types after envelope stripping (decapsulation)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from abc import ABC, abstractmethod
from ..types import SensorUUID


@dataclass(frozen=True, slots=True)
class DecapsulatedMessage:
    """One routed sensor ingest: identity + timestamps + opaque payload body.

    The **envelope** step removes transport/application scaffolding and keeps:

    - a **sensor key** usable with ``SensorConfig`` / ``sensor_registry``;
    - any **timing** hints needed downstream (received vs phenomenon);
    - a **payload** that still reflects “what came from / about the sensor
      readings” before decoder/normalizer specialization.
    """

    sensor_id: SensorUUID
    payload: Any
    application_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None


class Decapsulator(ABC):
    """ABC for decapsulators that strip vendor/application shells."""

    @staticmethod
    @abstractmethod
    def decapsulate(app_payload: Any) -> list[DecapsulatedMessage]:
        ...

"""Deserializer base class for decapsulated messages."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..decapsulators.types import DecapsulatedMessage


class Deserializer(ABC):
    """Base class for model-specific deserializers."""

    @staticmethod
    @abstractmethod
    def deserialize(msg: DecapsulatedMessage) -> DecapsulatedMessage:
        """Return a decapsulated message with payload deserialized as needed."""
        ...


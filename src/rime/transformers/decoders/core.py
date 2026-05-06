"""Decoder base class for post-deserialization decapsulated messages."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..decapsulators.types import DecapsulatedMessage
from ..messages import DecodedMessage


class Decoder(ABC):
    """Base class for model-specific payload decoders."""

    @staticmethod
    @abstractmethod
    def decode(msg: DecapsulatedMessage) -> DecodedMessage:
        """Decode one decapsulated message into a decoded message."""
        ...


"""Identity decoder — decapsulated payload is already the semantic body."""

from __future__ import annotations

from .core import Decoder
from ..decapsulators.types import DecapsulatedMessage
from ..messages import DecodedMessage


class NullDecoder(Decoder):
    """Pass-through: wraps :meth:`DecodedMessage.from_decapsulated`."""

    __slots__ = ()

    @staticmethod
    def decode(msg: DecapsulatedMessage) -> DecodedMessage:
        return DecodedMessage.from_decapsulated(msg)

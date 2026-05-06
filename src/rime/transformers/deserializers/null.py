"""Identity deserializer — decapsulated message payload needs no preprocessing."""

from __future__ import annotations

from .core import Deserializer
from ..envelopes.types import DecapsulatedMessage


class NullDeserializer(Deserializer):
    """Pass-through: ``deserialize(msg)`` returns ``msg`` unchanged.

    Replace with a real :mod:`rime.transformers.deserializers` implementation
    when a decapsulated payload still needs model-specific deserialization.
    """

    __slots__ = ()

    @staticmethod
    def deserialize(msg: DecapsulatedMessage) -> DecapsulatedMessage:
        return msg

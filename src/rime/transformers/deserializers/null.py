"""Identity deserializer — wire object is already structured for decapsulation."""

from __future__ import annotations

from typing import Any


class NullDeserializer:
    """Pass-through: ``deserialize(x)`` returns ``x`` unchanged.

    Replace with a real :mod:`rime.transformers.deserializers` implementation
    when ingest is raw ``bytes`` / ``str`` before decapsulators see a ``dict``.
    """

    __slots__ = ()

    @staticmethod
    def deserialize(payload: Any) -> Any:
        return payload

"""Decapsulator ABC: wire message → DecapsulatedMessage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..messages import DecapsulatedMessage


class Decapsulator(ABC):
    """ABC for decapsulators that strip vendor/provider shells."""

    @staticmethod
    @abstractmethod
    def decapsulate(wire_message: Any) -> DecapsulatedMessage:
        ...

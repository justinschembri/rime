"""Decapsulation — wire/application shells -> :class:`DecapsulatedMessage`.

Submodule imports (e.g. ``from rime.transformers.decapsulators.ttn import ...``) avoid import cycles.
Convenience ``from ...decapsulators import TTNDecapsulator`` uses lazy :func:`__getattr__`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .types import DecapsulatedMessage, Decapsulator, EnvelopeMetadata, IdentifiedPayload

__all__ = [
    "DecapsulatedMessage",
    "Decapsulator",
    "EnvelopeMetadata",
    "IdentifiedPayload",
    "NetatmoDecapsulator",
    "TTNDecapsulator",
]

if TYPE_CHECKING:
    from .netatmo import NetatmoDecapsulator
    from .ttn import TTNDecapsulator


def __getattr__(name: str):
    if name == "NetatmoDecapsulator":
        from .netatmo import NetatmoDecapsulator as _Cls

        return _Cls
    if name == "TTNDecapsulator":
        from .ttn import TTNDecapsulator as _Cls

        return _Cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Decapsulation — wire messages -> :class:`~rime.transformers.messages.DecapsulatedMessage`.

Submodule imports (e.g. ``from rime_ingest.transformers.decapsulators.ttn import ...``) avoid import cycles.
Convenience ``from ...decapsulators import TTNDecapsulator`` uses lazy :func:`__getattr__`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import Decapsulator
from ..messages import DecapsulatedMessage, EnvelopeMetadata, IdentifiedPayload

__all__ = [
    "DecapsulatedMessage",
    "Decapsulator",
    "EnvelopeMetadata",
    "IdentifiedPayload",
    "NetatmoDecapsulator",
    "RimeHttpDecapsulator",
    "TTNDecapsulator",
]

if TYPE_CHECKING:
    from .netatmo import NetatmoDecapsulator
    from .rime_http import RimeHttpDecapsulator
    from .ttn import TTNDecapsulator


def __getattr__(name: str):
    if name == "NetatmoDecapsulator":
        from .netatmo import NetatmoDecapsulator as _Cls
        return _Cls
    if name == "TTNDecapsulator":
        from .ttn import TTNDecapsulator as _Cls
        return _Cls
    if name == "RimeHttpDecapsulator":
        from .rime_http import RimeHttpDecapsulator as _Cls
        return _Cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

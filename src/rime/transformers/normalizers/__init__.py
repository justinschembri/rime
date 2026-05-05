"""Native payload → SensorThings observations (parsed ``dict`` in, STA out).

Sits after :mod:`rime.transformers.envelopes` and :mod:`rime.transformers.messages`;
see :data:`TRANSFORMER_MAP` and :class:`NativePayloadTransformer`.
"""

from .core import NativePayloadTransformer
from .registry import TRANSFORMER_MAP

__all__ = ["NativePayloadTransformer", "TRANSFORMER_MAP"]

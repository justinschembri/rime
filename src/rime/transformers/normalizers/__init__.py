"""Vendor observation dict → SensorThings observations.

Sits after :mod:`rime.transformers.envelopes` and :mod:`rime.transformers.messages`;
see :data:`TRANSFORMER_MAP` and :class:`VendorObservationTransformer`.
"""

from .core import VendorObservationTransformer
from ..registry import TRANSFORMER_MAP

__all__ = ["VendorObservationTransformer", "TRANSFORMER_MAP"]

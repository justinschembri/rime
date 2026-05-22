"""Vendor observation dict -> SensorThings observations.

Sits after :mod:`rime.transformers.parsers`;
see :data:`NORMALIZER_MAP` and :class:`VendorObservationNormalizer`.
"""

from .core import Normalizer
from ..registry import NORMALIZER_MAP

__all__ = ["Normalizer", "NORMALIZER_MAP"]

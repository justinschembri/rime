"""Vendor observation dict -> SensorThings observations.

Sits after :mod:`rime.transformers.parsers`;
see :data:`NORMALIZER_MAP` and :class:`VendorObservationNormalizer`.
"""

from .core import VendorObservationNormalizer
from ..registry import NORMALIZER_MAP

__all__ = ["VendorObservationNormalizer", "NORMALIZER_MAP"]

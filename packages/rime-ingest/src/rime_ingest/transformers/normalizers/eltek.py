"""Eltek datalogger normalizer."""

from __future__ import annotations

from ..types import CanonicalDatastreams
from .core import Normalizer


class EltekDatalogger(Normalizer):
    """Map Eltek channel readings to canonical FROST datastream names."""

    chan_1: float | None = None
    chan_2: float | None = None
    chan_3: float | None = None
    chan_4: float | None = None
    chan_5: float | None = None
    chan_6: float | None = None
    chan_7: float | None = None
    chan_8: float | None = None

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "chan_1": CanonicalDatastreams.ELTEK_CHAN_1_TEMPERATURE,
        "chan_2": CanonicalDatastreams.ELTEK_CHAN_2_TEMPERATURE,
        "chan_3": CanonicalDatastreams.ELTEK_CHAN_3_TEMPERATURE,
        "chan_4": CanonicalDatastreams.ELTEK_CHAN_4_TEMPERATURE,
        "chan_5": CanonicalDatastreams.ELTEK_CHAN_5_VOLTAGE,
        "chan_6": CanonicalDatastreams.ELTEK_CHAN_6_VOLTAGE,
        "chan_7": CanonicalDatastreams.ELTEK_CHAN_7_VOLTAGE,
        "chan_8": CanonicalDatastreams.ELTEK_CHAN_8_VOLTAGE,
    }

    TRANSFORM: dict[str, object] = {}

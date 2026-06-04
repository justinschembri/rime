# standard
import logging
from typing import Callable

# internal
from ..types import CanonicalDatastreams
from .core import Normalizer

logger = logging.getLogger(__name__)


class KinemetricsEtna2(Normalizer):
    HNE: float | None = None
    HNN: float | None = None
    HNZ: float | None = None

    NAME_TRANSFORM: dict[str, CanonicalDatastreams] = {
        "HNE": CanonicalDatastreams.HNE,
        "HNN": CanonicalDatastreams.HNN,
        "HNZ": CanonicalDatastreams.HNZ,
    }

    TRANSFORM: dict[str, Callable] = {}


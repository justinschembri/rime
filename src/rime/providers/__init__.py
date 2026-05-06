"""Concrete sensor application providers."""

from .generic_http import GenericHTTPProvider
from .netatmo import NetatmoProvider
from .registry import PROVIDER_REGISTRY
from .tts import TTSProvider

__all__ = ["GenericHTTPProvider", "NetatmoProvider", "TTSProvider", "PROVIDER_REGISTRY"]

"""Provider registry keyed by config-facing provider ids."""

from .netatmo import NetatmoProvider
from .tts import TTSProvider

PROVIDER_REGISTRY = {
    "netatmo": NetatmoProvider,
    "tts": TTSProvider,
}


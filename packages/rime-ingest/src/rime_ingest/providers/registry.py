"""Provider registry keyed by config-facing provider ids."""

from rime_ingest.providers.gen_seedlink import GenericSeedLinkProvider
from .netatmo import NetatmoProvider
from .rime_http import RimeServerHttpProvider
from .tts import TTSProvider

PROVIDER_REGISTRY = {
    "netatmo": NetatmoProvider,
    "tts": TTSProvider,
    "rime-http": RimeServerHttpProvider,
    "generic-seedlink": GenericSeedLinkProvider,
}


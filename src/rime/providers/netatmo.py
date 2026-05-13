"""Netatmo HTTP provider.

Netatmo authenticates via OAuth tokens stored as a JSON file under
`TOKENS_DIR/<app_name>.json`. The `lnetatmo` client handles the token refresh
flow internally; this provider just hands it the file path.
"""

import logging
from typing import Any, ClassVar, Literal

import lnetatmo

from ..paths import TOKENS_DIR
from ..transformers.decapsulators import NetatmoDecapsulator
from ..transformers.decapsulators.types import DecapsulatedMessage
from ..transport.poll.http import HTTPTransport

debug_logger = logging.getLogger("debug")


class NetatmoProvider(HTTPTransport):
    """Netatmo Weather Station API provider."""

    # CLI hint: which credential helper to invoke when configuring this provider
    auth_method: ClassVar[Literal["tokens", "credentials"]] = "tokens"

    _auth_obj: lnetatmo.ClientAuth
    _authenticated: bool = False

    @property
    def _token_file(self):
        return TOKENS_DIR / f"{self.app_name}.json"

    def _auth(self) -> lnetatmo.ClientAuth:
        if self._authenticated:
            debug_logger.debug(f"{self.app_name} already authenticated.")
            return self._auth_obj

        if not self._token_file.exists():
            raise FileNotFoundError(
                f"Netatmo token file not found: {self._token_file}"
            )

        self._auth_obj = lnetatmo.ClientAuth(credentialFile=self._token_file)
        self._authenticated = True
        return self._auth_obj

    def _decapsulate_provider_payload(
        self, wire_payload: Any
    ) -> list[DecapsulatedMessage]:
        return NetatmoDecapsulator.decapsulate(wire_payload)

    def _pull_data(self) -> list[dict[str, Any]] | None:
        if not self._authenticated:
            self._auth()
        netatmo_connection = lnetatmo.WeatherStationData(self._auth_obj)
        return netatmo_connection.rawData

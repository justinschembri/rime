"""TheThingsStack MQTT provider.

TTS uses an API key stored under `application_credentials.json`, keyed by the
application name. The application name itself is used as the MQTT username.
"""

import json
import logging
from typing import Any, ClassVar, Literal

from ..exceptions import UnpackError
from ..paths import CREDENTIALS_DIR
from ..transformers.decapsulators import TTNDecapsulator
from ..transformers.messages import DecapsulatedMessage
from ..transport.subscription.mqtt import MQTTTransport

event_logger = logging.getLogger("events")


class TTSProvider(MQTTTransport):
    """TheThingsStack provider over MQTT."""

    # TODO: TTS has a default topic: v3/{self.application_name}/devices/+/up
    # user setting up a TTS should not need to define this themselves.
    # CLI hint: which credential helper to invoke when configuring this provider
    auth_method: ClassVar[Literal["tokens", "credentials"]] = "credentials"

    @property
    def _credentials_file(self):
        return CREDENTIALS_DIR / "application_credentials.json"

    def _preflight(self) -> bool:
        if "ttn" not in self.topic:
            event_logger.warning(
                "TheThingsStack topic should include tenant ID '@ttn'. "
                f"Got topic: {self.topic} for {self.app_name}."
            )
            return False
        return True

    def _decapsulate_wire(self, wire_message: dict[str, Any]) -> DecapsulatedMessage:
        decapped = TTNDecapsulator.decapsulate(wire_message)
        if len(decapped.identified_payloads) != 1:
            raise UnpackError(
                RuntimeError(
                    "TTN uplink must decapsulate to exactly one logical device payload."
                )
            )
        return decapped

    def _auth(self) -> None:
        if not self._credentials_file.exists():
            raise FileNotFoundError(
                f"Did not find credential file for {self.app_name}: "
                f"{self._credentials_file}"
            )

        with open(self._credentials_file, "r") as f:
            credentials = json.load(f)
            api_key = credentials.get(self.app_name, {}).get("api_key")
            if not api_key:
                raise KeyError(
                    f"Did not find `api_key` for {self.app_name} in "
                    f"{self._credentials_file}."
                )
        # TTS "usernames" are equivalent to the application names.
        self._mqtt_client.username_pw_set(self.app_name, api_key)
        self._mqtt_client.tls_set()

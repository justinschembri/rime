# `providers`

Concrete integrations with specific upstream sensor applications:
Netatmo, TheThingsStack, Chirpstack, ... A provider answers **where**
data comes from, building on a transport from
[`../transport/`](../transport/README.md) which answers **how** it gets
here.

This is the active growth area of the project. Adding a new provider is
the most common kind of contribution and should be as painless as
possible.

## Current providers

| Provider          | Transport                          | Auth            | Notes                                            |
| ----------------- | ---------------------------------- | --------------- | ------------------------------------------------ |
| `NetatmoProvider` | `HTTPTransport` (poll)             | OAuth tokens    | Polls `WeatherStationData.rawData` via lnetatmo. |
| `TTSProvider`     | `MQTTTransport` (subscription)     | API key         | Subscribes to `v3/<app>/devices/+/up` topics.    |

## What a provider owns

A provider is the smallest piece of code needed to integrate a new
upstream application. It declares:

1. **The transport it uses.** By inheriting from `HTTPTransport` or
   `MQTTTransport` (or any future transport), it picks up the threading
   model, payload pipeline, and exception handling for free.
2. **Application decapsulation.** Implement `_decapsulate_application_payload(self, app_payload)`
   to strip the provider/application envelope and return `list[DecapsulatedMessage]`.
   Model-specific deserialization/decoding/transforming is handled centrally by
   `SensorTransport` using [`../transformers/ingest_registry.py`](../transformers/ingest_registry.py).
3. **Authentication.** Provider-local. Resolve credentials from
   wherever they are stored (token file, credentials JSON, env vars,
   TLS certs) inside `_auth()`.
4. **The data fetch.**
   - For HTTP: implement `_pull_data` to return a single payload.
   - For MQTT: implement `_auth` to configure the broker client; the
     transport's `_connect` handles subscription.
5. **Optional preflight checks.** Override `_preflight()` to return
   `False` and abort startup if the provider config is invalid (e.g. a
   topic missing a tenant ID).
6. **A CLI hint** for credential setup:
   ```python
   auth_method: ClassVar[Literal["tokens", "credentials"]] = "tokens"
   ```
   Used by `rime setup` to invoke the right credential helper. Defaults
   to `"credentials"` if not set.

## Adding a new provider

For something that just speaks an existing transport (Chirpstack,
Helium Console, AWS IoT Core, ...) the steps are:

1. Add `providers/<name>.py` with a class extending the appropriate
   transport ABC.
2. Implement `_decapsulate_application_payload`.
3. Implement `_auth` and (for HTTP) `_pull_data`.
4. Set `auth_method`.
5. Re-export from `providers/__init__.py`.
6. Add an entry to the table above.

Skeleton (MQTT-based provider):

```python
# providers/chirpstack.py
import json
import logging
from typing import Any, ClassVar, Literal

from ..paths import CREDENTIALS_DIR
from ..transformers.envelopes import ChirpstackDecapsulator  # hypothetical
from ..transformers.envelopes.types import DecapsulatedMessage
from ..transport import MQTTTransport

event_logger = logging.getLogger("events")


class ChirpstackProvider(MQTTTransport):
    """Chirpstack provider over MQTT."""

    auth_method: ClassVar[Literal["tokens", "credentials"]] = "credentials"

    def _decapsulate_application_payload(
        self, app_payload: Any
    ) -> list[DecapsulatedMessage]:
        return ChirpstackDecapsulator.decapsulate(app_payload)

    @property
    def _credentials_file(self):
        return CREDENTIALS_DIR / "application_credentials.json"

    def _auth(self) -> None:
        if not self._credentials_file.exists():
            raise FileNotFoundError(...)
        with open(self._credentials_file) as f:
            creds = json.load(f).get(self.app_name, {})
        self._mqtt_client.username_pw_set(creds["username"], creds["password"])
        self._mqtt_client.tls_set()
```

For something that needs a brand-new transport (e.g. SeedLink, an
FTP-drop watcher), build the transport first under
[`../transport/`](../transport/README.md), then build the provider on
top.

## Configuration

Providers are wired up via `deploy/application-configs.yml`:

```yaml
applications:
  multicare-acerra@ttn:
    connection_class: TTSProvider
    host: eu1.cloud.thethings.network
    topic: v3/multicare-acerra@ttn/devices/+/up
  my-netatmo:
    connection_class: NetatmoProvider
    request_interval: 600
```

The `connection_class` value must match the class name in this package
(`getattr` lookup). Any keys whose names match the provider's
constructor parameters are forwarded automatically by `from_config`.

The CLI (`rime setup`) prefers to write this file for you and will
introspect `auth_method` to know which credential setup to invoke.

## See also

- [`../transport/`](../transport/README.md) — abstract transports that
  providers extend.
- [`../transformers/envelopes/`](../transformers/envelopes/) —
  application envelope decapsulators.
- [`../transformers/ingest_registry.py`](../transformers/ingest_registry.py) —
  per-model deserializer/decoder/transformer wiring.
- [`../transformers/messages.py`](../transformers/messages.py) — ingress message
  types from decapsulate → decode → parse.
- [`../paths.py`](../paths.py) — `TOKENS_DIR`, `CREDENTIALS_DIR`, and
  related helpers used to locate provider credentials.

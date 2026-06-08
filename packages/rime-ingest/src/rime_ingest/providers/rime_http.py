"""rime-server-http ingest provider.

Polls a running ``rime-server-http`` instance, processes each drained message
through the shared ingest pipeline, then ACKs the batch. Delivery is
at-least-once: the server retains in-flight messages until acknowledged, so
ingest may process the same server message id more than once if it crashes
between drain and ack.

Configuration (``application-configs.yml``)
-------------------------------------------

.. code-block:: yaml

    applications:
      my-edge-app:                    # must match app_id in server-credentials.yml
        provider: rime-http
        server_url: http://rime-server-http:8080
        batch_limit: 50               # messages per poll (default 50)
        poll_interval: 2.0            # seconds between polls when queue is empty
        max_retries: 10

Credentials (``application_credentials.json``)
-----------------------------------------------

.. code-block:: json

    {
        "my-edge-app": {
            "egress_token": "<secret>"
        }
    }

Sensor identity
---------------
Edge producers must set ``X-Rime-Message-Id`` to the sensor's registry key
(``sensor_uuid``). The decapsulator reads it from that header. No extra config
is needed on the ingest side — identity comes from the wire, not the config,
consistent with all other providers.

To embed identity differently (e.g. in the body), subclass
:class:`~rime_ingest.transformers.decapsulators.rime_http.RimeHttpDecapsulator`
and override ``_resolve_sensor_uuid``, then register the subclass under a
different provider key.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Literal

import requests

from ..paths import CREDENTIALS_DIR
from ..transformers.decapsulators.rime_http import DrainedEnvelope, RimeHttpDecapsulator
from ..transformers.messages import DecapsulatedMessage
from ..transport.poll.buffered_http import BufferedHTTPTransport

event_logger = logging.getLogger("events")
main_logger = logging.getLogger("main")


class RimeServerHttpProvider(BufferedHTTPTransport):
    """Pull wire messages from a ``rime-server-http`` buffer.

    Parameters:
        app_name:      Application identifier — must equal ``app_id`` on the server.
        server_url:    Base URL of the server, e.g. ``http://rime-server-http:8080``.
        batch_limit:   Messages per poll request.
        poll_interval: Seconds to sleep when the server queue is empty.
        max_retries:   Consecutive hard failures before the thread stops.
    """

    auth_method: ClassVar[Literal["credentials"]] = "credentials"

    def __init__(
        self,
        app_name: str,
        *,
        server_url: str,
        batch_limit: int = 50,
        poll_interval: float = 2.0,
        max_retries: int = 10,
    ) -> None:
        super().__init__(
            app_name,
            batch_limit=batch_limit,
            poll_interval=poll_interval,
            max_retries=max_retries,
        )
        self.server_url = server_url.rstrip("/")
        self._decapsulator = RimeHttpDecapsulator()
        self._egress_token: str | None = None
        self._session: requests.Session | None = None

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    @property
    def _credentials_file(self) -> Path:
        return CREDENTIALS_DIR / "application_credentials.json"

    def _auth(self) -> None:
        if self._egress_token is not None:
            return
        if not self._credentials_file.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self._credentials_file}"
            )
        with self._credentials_file.open() as fh:
            creds = json.load(fh)
        token = creds.get(self.app_name, {}).get("egress_token")
        if not token:
            raise KeyError(
                f"No 'egress_token' found for '{self.app_name}' in "
                f"{self._credentials_file}."
            )
        self._egress_token = token
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self._egress_token}"})

    # ------------------------------------------------------------------
    # Buffered-HTTP pull + ack hooks
    # ------------------------------------------------------------------

    def _pull_batch(self, limit: int) -> list[DrainedEnvelope]:
        url = f"{self.server_url}/v1/apps/{self.app_name}/messages"
        resp = self._session.get(url, params={"limit": limit}, timeout=10)
        resp.raise_for_status()
        raw_messages = resp.json().get("messages", [])
        return [self._parse_envelope(m) for m in raw_messages]

    def _ack(self, ids: list[str]) -> None:
        url = f"{self.server_url}/v1/apps/{self.app_name}/messages/ack"
        resp = self._session.post(url, json={"ids": ids}, timeout=10)
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Ingest pipeline hook
    # ------------------------------------------------------------------

    def _decapsulate_wire(self, wire_message: Any) -> DecapsulatedMessage:
        return self._decapsulator.decapsulate_envelope(wire_message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_envelope(raw: dict[str, Any]) -> DrainedEnvelope:
        """Convert one drain-response message dict to a ``DrainedEnvelope``."""
        try:
            body = base64.b64decode(raw["body"])
        except Exception as e:
            raise ValueError(f"Failed to base64-decode message body: {e}") from e

        def _dt(value: str | None) -> datetime | None:
            if not value:
                return None
            s = value.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                return None

        return DrainedEnvelope(
            id=raw["id"],
            body=body,
            content_type=raw.get("content_type", "application/octet-stream"),
            received_at=_dt(raw.get("received_at")) or datetime.now(timezone.utc),
            message_id=raw.get("message_id"),
            emitted_at=_dt(raw.get("emitted_at")),
        )

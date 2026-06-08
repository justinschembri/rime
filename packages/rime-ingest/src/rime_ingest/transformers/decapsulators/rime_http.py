"""Decapsulator for rime-server-http buffered messages.

A ``rime-server-http`` drain message is an opaque byte blob plus server-side
metadata (``id``, ``content_type``, ``received_at``, ``emitted_at``, and
``message_id`` set by the edge producer via ``X-Rime-Message-Id``).  The server
performs **no parsing**: sensor identity must be embedded by the edge producer.

Identity convention
-------------------
Edge producers must set ``X-Rime-Message-Id`` to the ``sensor_uuid`` (the rime
registry key for that sensor).  The decapsulator reads it directly from
``envelope.message_id``, consistent with how TTN embeds identity in
``end_device_ids.dev_eui`` and Netatmo embeds it in ``device._id``.

For payloads where identity is in the body rather than the header, subclass and
override :meth:`_resolve_sensor_uuid`.

Wire envelope (input)
---------------------
The ``wire_message`` received by ``_decapsulate_wire`` is a
:class:`DrainedEnvelope` dataclass produced by :class:`RimeServerHttpProvider`.
This is an intermediate type local to the provider tier — it is *not* the raw
API response JSON but a structured Python object already base64-decoded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ...exceptions import UnpackError
from ..messages import DecapsulatedMessage, EnvelopeMetadata, IdentifiedPayload
from .core import Decapsulator

logger = logging.getLogger("events")


@dataclass(frozen=True, slots=True)
class DrainedEnvelope:
    """Structured representation of one message from the server drain API.

    ``body`` is the decoded byte payload (base64 unwrapped by the provider).
    All other fields come directly from the drain response JSON.
    """

    id: str                          # server-assigned UUID
    body: bytes                      # decoded payload
    content_type: str
    received_at: datetime
    message_id: str | None = None    # X-Rime-Message-Id supplied by edge — should be sensor_uuid
    emitted_at: datetime | None = None


class RimeHttpDecapsulator(Decapsulator):
    """Decapsulate a :class:`DrainedEnvelope` from ``rime-server-http``.

    Identity is read from ``envelope.message_id``, which the edge producer must
    set to the sensor's registry key (``sensor_uuid``).  Override
    :meth:`_resolve_sensor_uuid` if identity is embedded differently (e.g. in
    the body).
    """

    def _resolve_sensor_uuid(self, envelope: DrainedEnvelope) -> str:
        """Return the sensor UUID for *envelope*.

        Default: ``envelope.message_id``, which the edge producer sets to the
        sensor's registry key via ``X-Rime-Message-Id``.

        Override when sensor identity is encoded differently, e.g. as a prefix
        in ``message_id`` (``"<uuid>/<seq>"``) or embedded in the body.
        """
        if not envelope.message_id:
            raise UnpackError(
                ValueError(
                    f"Cannot determine sensor_uuid: DrainedEnvelope.message_id "
                    f"is empty for server message id={envelope.id!r}. "
                    "Edge producers must set X-Rime-Message-Id to the sensor_uuid."
                )
            )
        return envelope.message_id

    def _resolve_payload(self, envelope: DrainedEnvelope) -> Any:
        """Return the sensor-native payload for model-tier processing.

        Default: raw ``bytes``. Override for providers whose parsers expect a
        richer object (e.g. pre-parsed JSON dict when content_type is JSON).
        """
        return envelope.body

    @staticmethod
    def decapsulate(wire_message: Any) -> DecapsulatedMessage:
        """Class-level static entry point required by the ``Decapsulator`` ABC.

        For normal provider usage, ``_decapsulate_wire`` on
        :class:`~rime_ingest.providers.rime_http.RimeServerHttpProvider` calls
        :meth:`decapsulate_envelope` on the configured instance instead.
        """
        return RimeHttpDecapsulator().decapsulate_envelope(wire_message)

    def decapsulate_envelope(self, envelope: DrainedEnvelope) -> DecapsulatedMessage:
        """Produce a :class:`DecapsulatedMessage` from *envelope*.

        This is the primary call path for :class:`RimeServerHttpProvider`.
        """
        if not isinstance(envelope, DrainedEnvelope):
            raise UnpackError(
                TypeError(
                    f"RimeHttpDecapsulator expects a DrainedEnvelope, "
                    f"got {type(envelope).__name__}."
                )
            )
        sensor_uuid = self._resolve_sensor_uuid(envelope)
        payload = self._resolve_payload(envelope)

        envelope_metadata = EnvelopeMetadata(
            app_name=None,
            provider_timestamp=envelope.received_at,
            phenomenon_timestamp=envelope.emitted_at,
        )

        return DecapsulatedMessage(
            identified_payloads=[
                IdentifiedPayload(
                    sensor_uuid=sensor_uuid,
                    payload=payload,
                )
            ],
            envelope_metadata=envelope_metadata,
        )

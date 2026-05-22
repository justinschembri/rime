"""The Things Stack / TTN v3 application uplink JSON -> decapsulated message."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...exceptions import MissingPayloadKeysError, UnpackError
from .types import DecapsulatedMessage, Decapsulator, EnvelopeMetadata, IdentifiedPayload


def _parse_iso_utc(value: str | None) -> datetime | None:
    """Parse RFC3339 / ISO strings including ``Z`` suffix to UTC-aware ``datetime``."""

    if not value or not isinstance(value, str):
        return None
    s = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TTNDecapsulator(Decapsulator):
    """Strip TTS / TTN application uplink webhook or MQTT JSON.

    One top-level object yields one :class:`DecapsulatedMessage` containing
    a single :class:`IdentifiedPayload`.

    - ``sensor_uuid``: ``end_device_ids.dev_eui`` (registry key).
    - ``payload``: shallow copy of ``uplink_message.decoded_payload``.
    - ``envelope_metadata.provider_timestamp``: first ``rx_metadata[].received_at``.
    - ``envelope_metadata.phenomenon_timestamp``: ``uplink_message.time`` when present.
    """

    @staticmethod
    def decapsulate(wire_payload: dict[str, Any]) -> DecapsulatedMessage:
        try:
            sensor_uuid = wire_payload["end_device_ids"]["dev_eui"]
            sensor_payload = wire_payload["uplink_message"]["decoded_payload"]
            provider_timestamp = _parse_iso_utc(
                wire_payload["uplink_message"]["rx_metadata"][0].get("received_at")
            )
            phenomenon_timestamp = _parse_iso_utc(
                wire_payload["uplink_message"].get("time")
            )
            envelope_metadata = EnvelopeMetadata(
                provider_timestamp=provider_timestamp,
                phenomenon_timestamp=phenomenon_timestamp,
            )
        except KeyError as e:
            raise MissingPayloadKeysError(e)
        except MissingPayloadKeysError:
            raise
        except Exception as e:
            raise UnpackError(e)

        return DecapsulatedMessage(
            sensor_payloads=[
                IdentifiedPayload(
                    sensor_uuid=sensor_uuid,
                    payload=dict(sensor_payload),
                )
            ],
            envelope_metadata=envelope_metadata,
        )

"""The Things Stack / TTN v3 application uplink JSON -> decapsulated messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...exceptions import MissingPayloadKeysError, UnpackError
from .types import DecapsulatedMessage, Decapsulator


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

    One top-level object yields one :class:`DecapsulatedMessage`.

    - ``sensor_id``: ``end_device_ids.dev_eui`` (registry key).
    - ``payload``: shallow copy of ``uplink_message.decoded_payload``.
    - ``provider_timestamp``: first ``rx_metadata[].received_at``.
    - ``phenomenon_timestamp``: ``uplink_message.time`` when present.
    """

    @staticmethod
    def decapsulate(wire_payload: dict[str, Any]) -> list[DecapsulatedMessage]:
        try:
            sensor_id = wire_payload["end_device_ids"]["dev_eui"]
            uplink = wire_payload["uplink_message"]
            decoded = uplink["decoded_payload"]
            payload: Any = dict(decoded)

            received_raw = uplink["rx_metadata"][0]["received_at"]
            provider_ts = _parse_iso_utc(
                received_raw if isinstance(received_raw, str) else None
            )

            uplink_time = uplink.get("time")
            phenomenon_ts = _parse_iso_utc(
                uplink_time if isinstance(uplink_time, str) else None
            )
        except KeyError as e:
            raise MissingPayloadKeysError(e)
        except MissingPayloadKeysError:
            raise
        except Exception as e:
            raise UnpackError(e)

        return [
            DecapsulatedMessage(
                sensor_id=sensor_id,
                payload=payload,
                provider_timestamp=provider_ts,
                phenomenon_timestamp=phenomenon_ts,
            )
        ]

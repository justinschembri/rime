"""Netatmo: ``WeatherStationData.rawData`` -> decapsulated per-station messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...exceptions import MissingPayloadKeysError, UnpackError
from .types import DecapsulatedMessage, Decapsulator, EnvelopeMetadata


def _phenomenon_from_dashboard(dashboard_data: dict[str, Any]) -> datetime | None:
    """Observed sample time bundled by Netatmo inside ``dashboard_data`` (unix UTC)."""

    ts = dashboard_data.get("time_utc")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


class NetatmoDecapsulator(Decapsulator):
    """Decapsulator for Netatmo Weather Station ``rawData``.

    Input shape matches ``lnetatmo.WeatherStationData.rawData`` (list of stations).

    Drops station shell noise (wifi, module lists, naming, ...) kept only insofar as
    it is embedded inside ``dashboard_data`` along with readings. Routing uses the
    Netatmo MAC-style ``_id`` as ``sensor_id``.
    """

    @staticmethod
    def decapsulate(wire_payload: list[dict[str, Any]]) -> DecapsulatedMessage:
        sensor_payloads= []
        try:
            for device in wire_payload:
                if not device.get("reachable"):
                    continue
                sensor_payloads.append(dict(device["dashboard_data"]))
        except KeyError as e:
            raise MissingPayloadKeysError(e)
        except MissingPayloadKeysError:
            raise
        except Exception as e:
            raise UnpackError(e)
        return DecapsulatedMessage(sensor_payloads)

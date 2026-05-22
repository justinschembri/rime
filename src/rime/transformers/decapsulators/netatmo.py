"""Netatmo: ``WeatherStationData.rawData`` -> decapsulated per-station messages."""

from __future__ import annotations

import logging
from typing import Any

from ...exceptions import MissingPayloadKeysError, UnpackError
from ..messages import DecapsulatedMessage, IdentifiedPayload
from .core import Decapsulator

logger = logging.getLogger(__name__)


class NetatmoDecapsulator(Decapsulator):
    """Decapsulator for Netatmo Weather Station ``rawData``.

    Input shape matches ``lnetatmo.WeatherStationData.rawData`` (list of stations).

    Drops station shell noise (wifi signal, module lists, naming) and retains
    only the ``dashboard_data`` dict as the sensor-native payload.  Each
    reachable station becomes one :class:`~rime.transformers.messages.IdentifiedPayload`
    keyed by the Netatmo MAC-style ``_id``.

    An empty result (all stations unreachable) is not an error; a warning is
    logged and an empty :class:`~rime.transformers.messages.DecapsulatedMessage`
    is returned.
    """

    @staticmethod
    def decapsulate(wire_message: list[dict[str, Any]]) -> DecapsulatedMessage:
        identified_payloads: list[IdentifiedPayload] = []
        try:
            for device in wire_message:
                if not device.get("reachable"):
                    continue
                identified_payloads.append(
                    IdentifiedPayload(
                        sensor_uuid=device["_id"],
                        payload=dict(device["dashboard_data"]),
                    )
                )
        except KeyError as e:
            raise MissingPayloadKeysError(e)
        except MissingPayloadKeysError:
            raise
        except Exception as e:
            raise UnpackError(e)

        if not identified_payloads:
            logger.warning("NetatmoDecapsulator: no reachable stations in wire message.")

        return DecapsulatedMessage(identified_payloads)

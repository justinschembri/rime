"""Netatmo NWS03 parser: dashboard_data dict -> ObservationRecord."""

from __future__ import annotations

from datetime import datetime, timezone

from ...exceptions import MissingPayloadKeysError, UnpackError
from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser

_REQUIRED_FIELDS = {"temperature", "co2", "humidity", "noise", "pressure", "time_utc"}

_TREND_FIELDS = {"temp_trend", "pressure_trend"}


class NetatmoNWS03Parser(Parser):
    """Parse a Netatmo NWS03 ``dashboard_data`` payload into an :class:`~rime.transformers.messages.ObservationRecord`.

    Responsibilities:
    - Lowercase all field keys (Netatmo uses ``Temperature``, not ``temperature``).
    - Extract ``time_utc`` (unix UTC int) as ``phenomenon_timestamp``; remove it
      from observations so the normalizer receives only observation fields.
    - Drop non-observation metadata fields (``temp_trend``, ``pressure_trend``).
    - Validate that all required observation fields are present.

    Netatmo embeds the sample time inside the payload, so no envelope timestamp
    is needed or used.
    """

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        raw = identified.payload
        if not isinstance(raw, dict):
            raise UnpackError(TypeError("Netatmo NWS03 payload must be a dict."))

        observations: dict = {k.lower(): v for k, v in raw.items() if k.lower() not in _TREND_FIELDS}

        missing = _REQUIRED_FIELDS - observations.keys()
        if missing:
            raise MissingPayloadKeysError(KeyError(f"Missing required Netatmo fields: {missing}"))

        try:
            phenomenon_timestamp = datetime.fromtimestamp(int(observations.pop("time_utc")), tz=timezone.utc)
        except (TypeError, ValueError, OSError) as e:
            raise UnpackError(e)

        return ObservationRecord(
            sensor_uuid=identified.sensor_uuid,
            observations=observations,
            provider_timestamp=None,
            phenomenon_timestamp=phenomenon_timestamp,
        )

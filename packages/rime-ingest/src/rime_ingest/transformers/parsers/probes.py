"""Parsers for single-quantity probe instruments.

A probe payload is a scalar (or a string sentinel for missing data). There is
no vendor field map — the model itself implies the measured quantity. Timestamps
and framing come from the provider envelope when present.
"""

from __future__ import annotations

from typing import Any

from ...exceptions import UnpackError
from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord
from .core import Parser

NO_DATA_KEYS = {
    "",
    "open",
    "no_data",
    "no data",
}


def _coerce_probe_value(raw: Any) -> float | None:
    """Return a float reading, or ``None`` for known no-data sentinels."""
    if isinstance(raw, str) and raw.strip().lower() in NO_DATA_KEYS:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError) as e:
        raise UnpackError(ValueError(f"Probe value not numeric: {raw!r}")) from e


def _parse_scalar(
    identified: IdentifiedPayload,
    envelope: EnvelopeMetadata | None,
    *,
    field: str,
) -> ObservationRecord:
    return ObservationRecord(
        sensor_uuid=identified.sensor_uuid,
        observations={field: _coerce_probe_value(identified.payload)},
        provider_timestamp=envelope.provider_timestamp if envelope else None,
        phenomenon_timestamp=envelope.phenomenon_timestamp if envelope else None,
    )


class HeatFluxPlateParser(Parser):
    """Parse a heat-flux plate sample (single number → ``heat_flux``)."""

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        return _parse_scalar(identified, envelope, field="heat_flux")


class ThermocoupleTParser(Parser):
    """Parse a type-T thermocouple sample (single number → ``temperature``)."""

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        return _parse_scalar(identified, envelope, field="temperature")


class ThermocoupleKParser(Parser):
    """Parse a type-K thermocouple sample (single number → ``temperature``)."""

    @staticmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        return _parse_scalar(identified, envelope, field="temperature")

"""Eltek datalogger CSV export deserializer."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

from ...exceptions import UnpackError
from ..messages import (
    EnvelopeMetadata,
    IdentifiedPayload,
    IdentifiedTimeSeriesPayload,
    IrregularTimeAxis,
)
from .core import Deserializer

_NO_DATA = frozenset({"no data", ""})
_UNITS_ROW = re.compile(r"°C|mV", re.IGNORECASE)
_CHANNEL_KEYS = tuple(f"chan_{i}" for i in range(1, 9))


def _parse_eltek_timestamp(value: str) -> datetime:
    value = value.strip().strip('"')
    try:
        dt = datetime.strptime(value, "%d/%m/%y %H:%M:%S")
    except ValueError as e:
        raise UnpackError(ValueError(f"Invalid Eltek timestamp: {value!r}")) from e
    return dt.replace(tzinfo=timezone.utc)


def _parse_eltek_value(raw: str) -> float | None:
    text = raw.strip().strip('"')
    if text.lower() in _NO_DATA:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError as e:
        raise UnpackError(ValueError(f"Invalid Eltek numeric value: {raw!r}")) from e


def parse_eltek_csv(body: bytes | str) -> tuple[list[dict[str, float | None]], list[datetime]]:
    """Parse an Eltek readings CSV into row dicts and timestamps."""
    text = body.decode("utf-8-sig") if isinstance(body, bytes) else body
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if len(rows) < 2:
        raise UnpackError(ValueError("Eltek CSV must contain a header and at least one data row."))

    header = [cell.strip().strip('"') for cell in rows[0]]
    if not header or header[0].lower() != "date and time":
        raise UnpackError(ValueError("Eltek CSV header must start with 'Date and time'."))

    channel_columns = header[1:]
    if len(channel_columns) != 8:
        raise UnpackError(
            ValueError(f"Expected 8 Eltek channel columns, got {len(channel_columns)}.")
        )

    data_rows = rows[1:]
    if data_rows and _UNITS_ROW.search(";".join(data_rows[0])):
        data_rows = data_rows[1:]

    timestamps: list[datetime] = []
    payloads: list[dict[str, float | None]] = []
    for row in data_rows:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < 9:
            row = row + [""] * (9 - len(row))
        timestamp = _parse_eltek_timestamp(row[0])
        channels = {
            _CHANNEL_KEYS[i]: _parse_eltek_value(row[i + 1])
            for i in range(8)
        }
        if all(value is None for value in channels.values()):
            continue
        timestamps.append(timestamp)
        payloads.append(channels)

    if not payloads:
        raise UnpackError(ValueError("Eltek CSV contains no usable data rows."))

    return payloads, timestamps


class EltekCsvDeserializer(Deserializer):
    """Deserialize Eltek export CSV bytes into an :class:`IdentifiedTimeSeriesPayload`."""

    @staticmethod
    def deserialize(
        identified: IdentifiedPayload | IdentifiedTimeSeriesPayload,
        envelope: EnvelopeMetadata | None,
    ) -> IdentifiedTimeSeriesPayload:
        if not isinstance(identified, IdentifiedPayload):
            raise UnpackError(
                TypeError(
                    "EltekCsvDeserializer expects IdentifiedPayload with CSV bytes."
                )
            )
        if not isinstance(identified.payload, (bytes, str)):
            raise UnpackError(
                TypeError(
                    f"Eltek CSV payload must be bytes or str, got {type(identified.payload).__name__}."
                )
            )

        payloads, timestamps = parse_eltek_csv(identified.payload)
        return IdentifiedTimeSeriesPayload(
            sensor_uuid=identified.sensor_uuid,
            payload=payloads,
            time_axis=IrregularTimeAxis(timestamps=timestamps),
            sensor_model=identified.sensor_model,
            components=identified.components,
        )

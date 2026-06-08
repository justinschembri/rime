"""Tests for Eltek datalogger CSV ingest components."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rime_ingest.exceptions import UnpackError
from rime_ingest.transformers.deserializers.eltek import (
    EltekCsvDeserializer,
    parse_eltek_csv,
)
from rime_ingest.transformers.ingest_registry import INGEST_COMPONENT_MAP
from rime_ingest.transformers.messages import (
    EnvelopeMetadata,
    IdentifiedPayload,
    IdentifiedTimeSeriesPayload,
)
from rime_ingest.transformers.normalizers.eltek import EltekDatalogger
from rime_ingest.transformers.parsers.eltek import EltekDataloggerParser
from rime_ingest.transformers.types import SupportedSensors


_SAMPLE_CSV = b'''"Date and time";"Chan 1";"Chan 2";"Chan 3";"Chan 4";"Chan 5";"Chan 6";"Chan 7";"Chan 8"
"";"\xc2\xb0C    ";"\xc2\xb0C    ";"\xc2\xb0C    ";"\xc2\xb0C    ";"mV    ";"mV    ";"mV    ";"mV    "
"29/05/26 14:34:30";48,2;148,4;146,6;148,5;"No Data";"No Data";"No Data";"No Data"
"29/05/26 14:36:30";47,7;149,3;147,7;149,3;"No Data";"No Data";"No Data";"No Data"
"29/05/26 14:36:30";"No Data";"No Data";"No Data";"No Data";-0,460;-0,460;-0,460;-0,462
'''


class TestParseEltekCsv:
    def test_parses_rows_and_skips_units(self):
        payloads, timestamps = parse_eltek_csv(_SAMPLE_CSV)
        assert len(payloads) == 3
        assert payloads[0]["chan_1"] == 48.2
        assert payloads[0]["chan_5"] is None
        assert payloads[2]["chan_5"] == pytest.approx(-0.460)
        assert timestamps[0] == datetime(2026, 5, 29, 14, 34, 30, tzinfo=timezone.utc)

    def test_rejects_empty_csv(self):
        with pytest.raises(UnpackError):
            parse_eltek_csv(b"Date and time\n")


class TestEltekCsvDeserializer:
    def test_returns_time_series_payload(self):
        identified = IdentifiedPayload(
            sensor_uuid="K02212-12943",
            payload=_SAMPLE_CSV,
        )
        result = EltekCsvDeserializer.deserialize(identified, None)
        assert isinstance(result, IdentifiedTimeSeriesPayload)
        assert result.sensor_uuid == "K02212-12943"
        assert len(result.payload) == 3
        assert len(result.time_axis.timestamps) == 3


class TestEltekDataloggerParser:
    def test_builds_observation_record(self):
        row = {"chan_1": 48.2, "chan_2": None, "chan_5": -0.46}
        ts = datetime(2026, 5, 29, 14, 34, 30, tzinfo=timezone.utc)
        record = EltekDataloggerParser.parse(
            IdentifiedPayload(sensor_uuid="K02212-12943", payload=row),
            EnvelopeMetadata(phenomenon_timestamp=ts),
        )
        assert record.observations == {"chan_1": 48.2, "chan_5": -0.46}
        assert record.phenomenon_timestamp == ts

    def test_rejects_empty_row(self):
        with pytest.raises(UnpackError):
            EltekDataloggerParser.parse(
                IdentifiedPayload(sensor_uuid="x", payload={"chan_1": None}),
                None,
            )


class TestEltekDataloggerNormalizer:
    def test_maps_channels_to_datastreams(self):
        from rime_ingest.transformers.messages import ObservationRecord

        record = ObservationRecord(
            sensor_uuid="K02212-12943",
            observations={"chan_1": 48.2, "chan_5": -0.46},
            phenomenon_timestamp=datetime(2026, 5, 29, 14, 34, 30, tzinfo=timezone.utc),
        )
        normalizer = EltekDatalogger.from_record(record)
        observations = normalizer.to_stObservations()
        names = {name for _, name in observations}
        assert "eltek_chan_1_temperature" in names
        assert "eltek_chan_5_voltage" in names


class TestEltekRegistry:
    def test_registered_in_ingest_map(self):
        components = INGEST_COMPONENT_MAP[SupportedSensors.ELTEK_DATALOGGER]
        assert components.deserializer is EltekCsvDeserializer
        assert components.parser is EltekDataloggerParser
        assert components.normalizer is EltekDatalogger

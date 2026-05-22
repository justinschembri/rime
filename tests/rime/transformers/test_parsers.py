"""Tests for model-specific parsers."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rime.exceptions import MissingPayloadKeysError, UnpackError
from rime.transformers.decapsulators.types import EnvelopeMetadata, IdentifiedPayload
from rime.transformers.messages import ParsedMessage
from rime.transformers.parsers.netatmo import NetatmoNWS03Parser
from rime.transformers.parsers.milesight import MilesightAm103lParser, MilesightAm308lParser


_TS = 1765374089
_TS_DT = datetime.fromtimestamp(_TS, tz=timezone.utc)

_PROVIDER_TS = datetime(2025, 12, 25, 20, 8, 0, 937463, tzinfo=timezone.utc)
_PHENOMENON_TS = datetime(2025, 12, 25, 20, 8, 0, 920247, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _identified(uuid: str, payload: dict) -> IdentifiedPayload:
    return IdentifiedPayload(sensor_uuid=uuid, payload=payload)


def _envelope(provider_ts=None, phenomenon_ts=None) -> EnvelopeMetadata:
    return EnvelopeMetadata(
        provider_timestamp=provider_ts,
        phenomenon_timestamp=phenomenon_ts,
    )


# ---------------------------------------------------------------------------
# NetatmoNWS03Parser
# ---------------------------------------------------------------------------

class TestNetatmoNWS03Parser:
    _FULL = {
        "time_utc": _TS,
        "Temperature": 23.3,
        "CO2": 871,
        "Humidity": 46,
        "Noise": 33,
        "Pressure": 1014.8,
        "temp_trend": "stable",
        "pressure_trend": "up",
    }

    def test_returns_parsed_message(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert isinstance(msg, ParsedMessage)

    def test_sensor_uuid_forwarded(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert msg.sensor_uuid == "70:aa"

    def test_keys_lowercased(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert "temperature" in msg.body
        assert "Temperature" not in msg.body

    def test_time_utc_becomes_phenomenon_timestamp(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert msg.phenomenon_timestamp == _TS_DT

    def test_time_utc_removed_from_body(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert "time_utc" not in msg.body

    def test_trend_fields_dropped(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert "temp_trend" not in msg.body
        assert "pressure_trend" not in msg.body

    def test_provider_timestamp_is_none(self):
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), None)
        assert msg.provider_timestamp is None

    def test_envelope_not_used(self):
        """Envelope timestamps are ignored; Netatmo time comes from the payload."""
        env = _envelope(provider_ts=_PROVIDER_TS, phenomenon_ts=_PHENOMENON_TS)
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", self._FULL), env)
        assert msg.phenomenon_timestamp == _TS_DT
        assert msg.provider_timestamp is None

    def test_missing_required_field_raises(self):
        bad = {k: v for k, v in self._FULL.items() if k != "Temperature"}
        with pytest.raises(MissingPayloadKeysError):
            NetatmoNWS03Parser.parse(_identified("70:aa", bad), None)

    def test_non_dict_payload_raises(self):
        with pytest.raises(UnpackError):
            NetatmoNWS03Parser.parse(_identified("70:aa", "not-a-dict"), None)

    def test_body_is_shallow_copy(self):
        """Modifying body should not mutate the original payload."""
        payload = dict(self._FULL)
        msg = NetatmoNWS03Parser.parse(_identified("70:aa", payload), None)
        msg.body["temperature"] = 99.0
        assert payload["Temperature"] == 23.3


# ---------------------------------------------------------------------------
# MilesightAm103lParser
# ---------------------------------------------------------------------------

class TestMilesightAm103lParser:
    _FULL = {"battery": 53, "co2": 4665.0, "humidity": 75.5, "temperature": 23.1}

    def test_returns_parsed_message(self):
        env = _envelope(provider_ts=_PROVIDER_TS, phenomenon_ts=_PHENOMENON_TS)
        msg = MilesightAm103lParser.parse(_identified("AA:BB", self._FULL), env)
        assert isinstance(msg, ParsedMessage)

    def test_sensor_uuid_forwarded(self):
        msg = MilesightAm103lParser.parse(_identified("AA:BB", self._FULL), None)
        assert msg.sensor_uuid == "AA:BB"

    def test_timestamps_from_envelope(self):
        env = _envelope(provider_ts=_PROVIDER_TS, phenomenon_ts=_PHENOMENON_TS)
        msg = MilesightAm103lParser.parse(_identified("AA:BB", self._FULL), env)
        assert msg.provider_timestamp == _PROVIDER_TS
        assert msg.phenomenon_timestamp == _PHENOMENON_TS

    def test_no_envelope_timestamps_are_none(self):
        msg = MilesightAm103lParser.parse(_identified("AA:BB", self._FULL), None)
        assert msg.provider_timestamp is None
        assert msg.phenomenon_timestamp is None

    def test_body_unchanged(self):
        msg = MilesightAm103lParser.parse(_identified("AA:BB", self._FULL), None)
        assert msg.body == self._FULL

    def test_body_is_shallow_copy(self):
        payload = dict(self._FULL)
        msg = MilesightAm103lParser.parse(_identified("AA:BB", payload), None)
        msg.body["battery"] = 0
        assert payload["battery"] == 53

    def test_missing_required_field_raises(self):
        bad = {k: v for k, v in self._FULL.items() if k != "co2"}
        with pytest.raises(MissingPayloadKeysError):
            MilesightAm103lParser.parse(_identified("AA:BB", bad), None)

    def test_non_dict_payload_raises(self):
        with pytest.raises(UnpackError):
            MilesightAm103lParser.parse(_identified("AA:BB", 42), None)


# ---------------------------------------------------------------------------
# MilesightAm308lParser
# ---------------------------------------------------------------------------

class TestMilesightAm308lParser:
    _FULL = {
        "battery": 53,
        "co2": 4665.0,
        "humidity": 75.5,
        "light_level": 1,
        "pir": "idle",
        "pm10": 107,
        "pm2_5": 101,
        "pressure": 1017.5,
        "temperature": 23.1,
        "tvoc": 1.0,
    }

    def test_returns_parsed_message(self):
        msg = MilesightAm308lParser.parse(_identified("CC:DD", self._FULL), None)
        assert isinstance(msg, ParsedMessage)

    def test_timestamps_from_envelope(self):
        env = _envelope(provider_ts=_PROVIDER_TS, phenomenon_ts=_PHENOMENON_TS)
        msg = MilesightAm308lParser.parse(_identified("CC:DD", self._FULL), env)
        assert msg.provider_timestamp == _PROVIDER_TS
        assert msg.phenomenon_timestamp == _PHENOMENON_TS

    def test_missing_required_field_raises(self):
        bad = {k: v for k, v in self._FULL.items() if k != "pir"}
        with pytest.raises(MissingPayloadKeysError):
            MilesightAm308lParser.parse(_identified("CC:DD", bad), None)

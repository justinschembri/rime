"""Tests for Netatmo envelope decapsulation."""

from __future__ import annotations

import pytest

from rime.exceptions import MissingPayloadKeysError
from rime.transformers.decapsulators.types import DecapsulatedMessage, IdentifiedPayload
from rime.providers.netatmo import NetatmoProvider
from rime.transformers.decapsulators import NetatmoDecapsulator


_TS = 1765374089


def _station(
    sid: str,
    reachable: bool,
    *,
    dash: dict | None = None,
) -> dict:
    return {
        "_id": sid,
        "station_name": "Test",
        "reachable": reachable,
        "wifi_status": 74,
        "dashboard_data": dash
        if dash is not None
        else {"time_utc": _TS, "Temperature": 23.3, "CO2": 871},
        "modules": [],
    }


class TestNetatmoDecapsulator:
    def test_skips_unreachable(self):
        raw = [_station("70:aa", False), _station("70:bb", True)]
        msg = NetatmoDecapsulator.decapsulate(raw)
        assert len(msg.sensor_payloads) == 1
        assert msg.sensor_payloads[0].sensor_uuid == "70:bb"

    def test_payload_is_dashboard_shallow_copy(self):
        dash = {"time_utc": _TS, "Temperature": 12.5}
        raw = [_station("70:cc", True, dash=dash)]
        msg = NetatmoDecapsulator.decapsulate(raw)
        assert msg.sensor_payloads[0].payload["Temperature"] == 12.5
        msg.sensor_payloads[0].payload["Temperature"] = 99.0
        assert dash["Temperature"] == 12.5

    def test_no_envelope_metadata(self):
        raw = [_station("70:dd", True)]
        msg = NetatmoDecapsulator.decapsulate(raw)
        assert msg.envelope_metadata is None

    def test_all_unreachable_returns_empty_payloads(self):
        raw = [_station("70:ee", False)]
        msg = NetatmoDecapsulator.decapsulate(raw)
        assert isinstance(msg, DecapsulatedMessage)
        assert msg.sensor_payloads == []

    def test_missing_dashboard_raises(self):
        raw = [{"_id": "x", "reachable": True}]
        with pytest.raises(MissingPayloadKeysError):
            NetatmoDecapsulator.decapsulate(raw)

    def test_multiple_reachable_stations(self):
        raw = [_station("70:aa", True), _station("70:bb", True)]
        msg = NetatmoDecapsulator.decapsulate(raw)
        assert len(msg.sensor_payloads) == 2
        uuids = {p.sensor_uuid for p in msg.sensor_payloads}
        assert uuids == {"70:aa", "70:bb"}


def test_netatmo_provider_decapsulate_delegates():
    raw = [_station("70:ff", True)]
    decapped = NetatmoProvider("test")._decapsulate_wire(raw)
    assert isinstance(decapped, DecapsulatedMessage)
    assert len(decapped.sensor_payloads) == 1
    identified = decapped.sensor_payloads[0]
    assert isinstance(identified, IdentifiedPayload)
    assert identified.sensor_uuid == "70:ff"
    assert identified.payload["Temperature"] == 23.3
    assert decapped.envelope_metadata is None

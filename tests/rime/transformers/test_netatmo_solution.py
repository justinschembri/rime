"""Tests for Netatmo envelope decapsulation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rime.exceptions import MissingPayloadKeysError
from rime.transformers.decapsulators.types import DecapsulatedMessage
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
        msgs = NetatmoDecapsulator.decapsulate(raw)
        assert len(msgs) == 1
        assert msgs[0].sensor_id == "70:bb"

    def test_payload_is_dashboard_shallow_copy(self):
        dash = {"time_utc": _TS, "Temperature": 12.5}
        raw = [_station("70:cc", True, dash=dash)]
        msgs = NetatmoDecapsulator.decapsulate(raw)
        assert msgs[0].payload["Temperature"] == 12.5
        msgs[0].payload["Temperature"] = 99.0
        assert dash["Temperature"] == 12.5

    def test_phenomenon_timestamp(self):
        raw = [_station("70:dd", True)]
        msgs = NetatmoDecapsulator.decapsulate(raw)
        assert msgs[0].provider_timestamp is None
        assert msgs[0].phenomenon_timestamp == datetime.fromtimestamp(
            _TS, tz=timezone.utc
        )

    def test_missing_dashboard_raises(self):
        raw = [{"_id": "x", "reachable": True}]
        with pytest.raises(MissingPayloadKeysError):
            NetatmoDecapsulator.decapsulate(raw)


def test_netatmo_provider_decapsulate_delegates():
    raw = [_station("70:ee", True)]
    decapped = NetatmoProvider("test")._decapsulate_wire(raw)
    assert len(decapped) == 1
    assert isinstance(decapped[0], DecapsulatedMessage)
    assert decapped[0].sensor_id == "70:ee"
    assert decapped[0].provider_timestamp is None
    assert decapped[0].payload["Temperature"] == 23.3

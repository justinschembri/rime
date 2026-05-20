"""Tests for TTN / TTS v3 envelope decapsulation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rime.exceptions import MissingPayloadKeysError
from rime.transformers.decapsulators import TTNDecapsulator


@pytest.fixture
def minimal_ttn_payload() -> dict:
    """Minimal uplink resembling TTS webhook / MQTT serialization."""

    return {
        "end_device_ids": {"dev_eui": "24E124707D378803"},
        "uplink_message": {
            "time": "2025-12-25T20:08:00.920247Z",
            "decoded_payload": {"temperature": 23.1, "battery": 53},
            "rx_metadata": [
                {
                    "received_at": "2025-12-25T20:08:00.937463873Z",
                }
            ],
        },
    }


def test_ttndecapsulator_timestamps(minimal_ttn_payload):
    msgs = TTNDecapsulator.decapsulate(minimal_ttn_payload)
    assert len(msgs) == 1
    m = msgs[0]
    assert m.sensor_id == "24E124707D378803"
    assert m.sensor_message == {"temperature": 23.1, "battery": 53}
    assert m.provider_timestamp == datetime(
        2025, 12, 25, 20, 8, 0, 937463, tzinfo=timezone.utc
    )
    assert m.phenomenon_timestamp == datetime(
        2025, 12, 25, 20, 8, 0, 920247, tzinfo=timezone.utc
    )


def test_ttndecapsulator_decoded_payload_shallow_copy(minimal_ttn_payload):
    inner = minimal_ttn_payload["uplink_message"]["decoded_payload"]
    msgs = TTNDecapsulator.decapsulate(minimal_ttn_payload)
    msgs[0].sensor_message["temperature"] = 99.0
    assert inner["temperature"] == 23.1


def test_ttndecapsulator_missing_nested():
    with pytest.raises(MissingPayloadKeysError):
        TTNDecapsulator.decapsulate({"end_device_ids": {}, "uplink_message": {}})

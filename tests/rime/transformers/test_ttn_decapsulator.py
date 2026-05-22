"""Tests for TTN / TTS v3 envelope decapsulation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rime.exceptions import MissingPayloadKeysError
from rime.transformers.decapsulators import TTNDecapsulator
from rime.transformers.decapsulators.types import DecapsulatedMessage, IdentifiedPayload


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


def test_ttndecapsulator_structure(minimal_ttn_payload):
    msg = TTNDecapsulator.decapsulate(minimal_ttn_payload)
    assert isinstance(msg, DecapsulatedMessage)
    assert len(msg.sensor_payloads) == 1
    identified = msg.sensor_payloads[0]
    assert isinstance(identified, IdentifiedPayload)
    assert identified.sensor_uuid == "24E124707D378803"
    assert identified.payload == {"temperature": 23.1, "battery": 53}


def test_ttndecapsulator_envelope_timestamps(minimal_ttn_payload):
    msg = TTNDecapsulator.decapsulate(minimal_ttn_payload)
    env = msg.envelope_metadata
    assert env is not None
    assert env.provider_timestamp == datetime(
        2025, 12, 25, 20, 8, 0, 937463, tzinfo=timezone.utc
    )
    assert env.phenomenon_timestamp == datetime(
        2025, 12, 25, 20, 8, 0, 920247, tzinfo=timezone.utc
    )


def test_ttndecapsulator_decoded_payload_shallow_copy(minimal_ttn_payload):
    inner = minimal_ttn_payload["uplink_message"]["decoded_payload"]
    msg = TTNDecapsulator.decapsulate(minimal_ttn_payload)
    msg.sensor_payloads[0].payload["temperature"] = 99.0
    assert inner["temperature"] == 23.1


def test_ttndecapsulator_missing_nested():
    with pytest.raises(MissingPayloadKeysError):
        TTNDecapsulator.decapsulate({"end_device_ids": {}, "uplink_message": {}})


def test_ttndecapsulator_missing_phenomenon_time():
    """uplink_message.time is optional; envelope.phenomenon_timestamp should be None."""
    payload = {
        "end_device_ids": {"dev_eui": "AABBCCDD"},
        "uplink_message": {
            "decoded_payload": {"temperature": 20.0},
            "rx_metadata": [{"received_at": "2025-12-25T20:08:00.937463873Z"}],
        },
    }
    msg = TTNDecapsulator.decapsulate(payload)
    assert msg.envelope_metadata.phenomenon_timestamp is None

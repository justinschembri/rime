"""Unit tests for RimeHttpDecapsulator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rime_ingest.exceptions import UnpackError
from rime_ingest.transformers.decapsulators.rime_http import (
    DrainedEnvelope,
    RimeHttpDecapsulator,
)
from rime_ingest.transformers.messages import DecapsulatedMessage


def _envelope(**kwargs) -> DrainedEnvelope:
    defaults = dict(
        id="srv-001",
        body=b'{"temp": 21.3}',
        content_type="application/json",
        received_at=datetime(2026, 6, 8, 10, 0, 0, tzinfo=timezone.utc),
        message_id="sensor-abc",
        emitted_at=None,
    )
    defaults.update(kwargs)
    return DrainedEnvelope(**defaults)


class TestRimeHttpDecapsulatorDefault:
    """Default: sensor_uuid read from message_id (set by edge via X-Rime-Message-Id)."""

    def test_decapsulate_returns_identified_payload(self):
        d = RimeHttpDecapsulator()
        result = d.decapsulate_envelope(_envelope(message_id="sensor-abc"))
        assert isinstance(result, DecapsulatedMessage)
        assert len(result.identified_payloads) == 1
        assert result.identified_payloads[0].sensor_uuid == "sensor-abc"

    def test_payload_is_raw_bytes_by_default(self):
        body = b"raw payload"
        d = RimeHttpDecapsulator()
        result = d.decapsulate_envelope(_envelope(body=body))
        assert result.identified_payloads[0].payload == body

    def test_received_at_becomes_provider_timestamp(self):
        ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        d = RimeHttpDecapsulator()
        result = d.decapsulate_envelope(_envelope(received_at=ts))
        assert result.envelope_metadata.provider_timestamp == ts

    def test_emitted_at_becomes_phenomenon_timestamp(self):
        ts = datetime(2026, 1, 1, 11, 55, tzinfo=timezone.utc)
        d = RimeHttpDecapsulator()
        result = d.decapsulate_envelope(_envelope(emitted_at=ts))
        assert result.envelope_metadata.phenomenon_timestamp == ts

    def test_missing_message_id_raises_unpack_error(self):
        d = RimeHttpDecapsulator()
        with pytest.raises(UnpackError, match="X-Rime-Message-Id"):
            d.decapsulate_envelope(_envelope(message_id=None))

    def test_empty_message_id_raises_unpack_error(self):
        d = RimeHttpDecapsulator()
        with pytest.raises(UnpackError):
            d.decapsulate_envelope(_envelope(message_id=""))

    def test_wrong_input_type_raises_unpack_error(self):
        d = RimeHttpDecapsulator()
        with pytest.raises(UnpackError):
            d.decapsulate_envelope({"not": "an_envelope"})


class TestRimeHttpDecapsulatorOverride:
    """Override _resolve_sensor_uuid to extract identity differently."""

    class _PrefixDecapsulator(RimeHttpDecapsulator):
        """UUID is the first segment of message_id: '<uuid>/<sequence>'."""
        def _resolve_sensor_uuid(self, envelope: DrainedEnvelope) -> str:
            if not envelope.message_id:
                raise UnpackError(ValueError("message_id missing"))
            return envelope.message_id.split("/")[0]

    def test_uuid_extracted_from_prefix(self):
        d = self._PrefixDecapsulator()
        result = d.decapsulate_envelope(
            _envelope(message_id="sensor-xyz/0042")
        )
        assert result.identified_payloads[0].sensor_uuid == "sensor-xyz"

    def test_missing_message_id_raises_with_override(self):
        d = self._PrefixDecapsulator()
        with pytest.raises(UnpackError):
            d.decapsulate_envelope(_envelope(message_id=None))


class TestDrainedEnvelope:
    def test_defaults(self):
        e = DrainedEnvelope(
            id="x",
            body=b"",
            content_type="text/plain",
            received_at=datetime.now(timezone.utc),
        )
        assert e.message_id is None
        assert e.emitted_at is None

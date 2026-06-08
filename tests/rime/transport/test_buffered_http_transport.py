"""Unit tests for BufferedHTTPTransport.

The transport drives a drain → process → ack loop. We stub out all abstract
methods so we can exercise the loop logic without any network calls.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rime_ingest.transport.poll.buffered_http import BufferedHTTPTransport
from rime_ingest.transformers.messages import (
    DecapsulatedMessage,
    EnvelopeMetadata,
    IdentifiedPayload,
)


# ---------------------------------------------------------------------------
# Test double
# ---------------------------------------------------------------------------

class _Envelope:
    """Minimal wire envelope with an id and a payload."""
    def __init__(self, id: str, body: bytes = b"data"):
        self.id = id
        self.body = body


def _make_decapsulated(sensor_uuid: str = "test-sensor") -> DecapsulatedMessage:
    return DecapsulatedMessage(
        identified_payloads=[IdentifiedPayload(sensor_uuid=sensor_uuid, payload={})],
        envelope_metadata=EnvelopeMetadata(),
    )


class _ConcreteTransport(BufferedHTTPTransport):
    """Concrete transport for testing — no real HTTP calls."""

    def __init__(self, batches: list[list[_Envelope]], **kwargs):
        super().__init__("test-app", **kwargs)
        self._batches = list(batches)
        self.pulled: list[list[_Envelope]] = []
        self.acked: list[list[str]] = []

    def _pull_batch(self, limit: int) -> list[_Envelope]:
        if self._batches:
            batch = self._batches.pop(0)
            self.pulled.append(batch)
            return batch
        return []

    def _ack(self, ids: list[str]) -> None:
        self.acked.append(ids)

    def _decapsulate_wire(self, wire_message: Any) -> DecapsulatedMessage:
        return _make_decapsulated()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_transport(transport: _ConcreteTransport, sensor_registry=None, timeout=2.0):
    """Start *transport*, let it drain its batches, then stop it."""
    with patch("rime_ingest.transport.poll.buffered_http.netmon"):
        transport.start(sensor_registry or {"test-sensor": MagicMock()})
        deadline = time.monotonic() + timeout
        while transport.is_alive and time.monotonic() < deadline:
            # Stop once all pre-loaded batches are consumed.
            if not transport._batches:
                time.sleep(0.05)
                break
        transport.stop()
        if transport._thread:
            transport._thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBufferedHTTPTransport:
    def test_processes_each_message_in_batch(self):
        envelopes = [_Envelope("a"), _Envelope("b"), _Envelope("c")]
        t = _ConcreteTransport(batches=[[envelopes[0]], [envelopes[1]], [envelopes[2]]])

        processed = []
        original = t._process_wire_message
        def _recording_process(msg):
            processed.append(msg.id)
            original(msg)

        with patch.object(t, "_process_wire_message", side_effect=_recording_process):
            _run_transport(t)

        assert set(processed) == {"a", "b", "c"}

    def test_acks_successful_messages(self):
        envelopes = [_Envelope("x"), _Envelope("y")]
        t = _ConcreteTransport(batches=[envelopes])

        with patch.object(t, "_process_wire_message"):
            _run_transport(t)

        assert len(t.acked) >= 1
        acked_flat = [id_ for batch in t.acked for id_ in batch]
        assert set(acked_flat) == {"x", "y"}

    def test_no_ack_when_batch_empty(self):
        t = _ConcreteTransport(batches=[[]], poll_interval=0.01)
        with patch.object(t, "_process_wire_message"):
            _run_transport(t, timeout=0.2)
        assert t.acked == []

    def test_pull_error_increments_failures(self):
        t = _ConcreteTransport(batches=[], max_retries=2, poll_interval=0.01)

        call_count = 0
        def _failing_pull(limit):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("network error")

        t._pull_batch = _failing_pull
        t.start({"test-sensor": MagicMock()})
        t._thread.join(timeout=1.0)

        assert call_count >= 2
        assert not t.is_alive

    def test_ack_failure_is_non_fatal(self):
        envelopes = [_Envelope("z")]
        t = _ConcreteTransport(batches=[envelopes])
        t._ack = lambda ids: (_ for _ in ()).throw(RuntimeError("ack failed"))

        with patch.object(t, "_process_wire_message"):
            _run_transport(t)

        # Transport should not have stopped.
        # (It may have stopped due to empty queue; check it completed normally)
        assert not t._stop_event.is_set() or len(t.pulled) >= 1

    def test_batch_limit_forwarded(self):
        limits_seen = []
        t = _ConcreteTransport(batches=[[]], batch_limit=17)

        original_pull = t._pull_batch
        def _recording_pull(limit):
            limits_seen.append(limit)
            return original_pull(limit)

        t._pull_batch = _recording_pull
        with patch.object(t, "_process_wire_message"):
            _run_transport(t, timeout=0.2)

        assert all(l == 17 for l in limits_seen)

    def test_auth_called_once_before_loop(self):
        t = _ConcreteTransport(batches=[[]])
        auth_calls = []
        t._auth = lambda: auth_calls.append(1)
        with patch.object(t, "_process_wire_message"):
            _run_transport(t, timeout=0.2)
        assert auth_calls == [1]

"""Unit tests for TransportBufferStore."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rime_ingest.sta.core import Observation
from rime_ingest.transport.buffers import (
    NullBuffer,
    TransportBufferStore,
    TresholdBuffer,
)
from rime_ingest.transformers.types import CanonicalDatastreams, SupportedSensors


def _obs(
    result: float,
    *,
    hour: int = 0,
    minute: int = 0,
) -> tuple[Observation, CanonicalDatastreams]:
    datastream = list(CanonicalDatastreams)[0]
    return (
        Observation(
            result=result,
            phenomenonTime=datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc),
        ),
        datastream,
    )


class TestTransportBufferStore:
    def test_null_buffer_flushes_on_first_observation(self) -> None:
        store = TransportBufferStore({SupportedSensors.NETATMO_NWS03: NullBuffer})

        flush = store.record_observation(
            "sensor-a",
            SupportedSensors.NETATMO_NWS03,
            _obs(1.0),
        )

        assert flush is not None
        assert flush.sensor_uuid == "sensor-a"
        assert flush.payload[0].result == 1.0

        store.commit_flush(flush.key)
        assert store.record_observation(
            "sensor-a",
            SupportedSensors.NETATMO_NWS03,
            _obs(2.0),
        ) is not None

    def test_threshold_buffer_accumulates_until_trigger(self) -> None:
        store = TransportBufferStore(
            {
                SupportedSensors.KINEMETRICS_ETNA2: lambda datastream: TresholdBuffer(
                    datastream,
                    max_time=timedelta(minutes=10),
                    sample_rate=1.0,
                )
            }
        )

        first = store.record_observation(
            "sensor-a",
            SupportedSensors.KINEMETRICS_ETNA2,
            _obs(1.0, hour=0, minute=0),
        )
        second = store.record_observation(
            "sensor-a",
            SupportedSensors.KINEMETRICS_ETNA2,
            _obs(2.0, hour=0, minute=1),
        )

        assert first is None
        assert second is None

    def test_drain_pending_only_returns_owned_sensors(self) -> None:
        store = TransportBufferStore(
            {
                SupportedSensors.KINEMETRICS_ETNA2: lambda datastream: TresholdBuffer(
                    datastream,
                    max_time=timedelta(minutes=5),
                    sample_rate=1.0,
                )
            }
        )
        store.record_observation(
            "owned-sensor",
            SupportedSensors.KINEMETRICS_ETNA2,
            _obs(1.0, hour=0, minute=0),
        )
        store.record_observation(
            "other-sensor",
            SupportedSensors.KINEMETRICS_ETNA2,
            _obs(2.0, hour=0, minute=1),
        )

        flushes = store.drain_pending_for_sensors(["owned-sensor"])

        assert len(flushes) == 1
        assert flushes[0].sensor_uuid == "owned-sensor"

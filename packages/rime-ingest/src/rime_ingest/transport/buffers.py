"""Transport buffers."""
# stdlib
from collections import defaultdict
from dataclasses import dataclass
import threading
from datetime import timedelta, datetime
from typing import Any, DefaultDict, Iterable, Tuple
from abc import ABC, abstractmethod
# internal
from rime_ingest.sta.core import Observation
from rime_ingest.transformers.types import (
        CanonicalDatastreams,
        SensorUUID,
        SupportedSensors
        )


class ObservationBuffer(ABC):
    """
    Buffer observations before pushing them to a STA service.

    Handles thread lock, adding observations. Implement _check_trigger() and 
    _dump_locked().
    """

    def __init__(
        self,
        datastream_name: CanonicalDatastreams,
        sample_rate: float = 1.0,
    ):
        self.datastream_name = datastream_name
        self.pending_flush: bool = False
        self.observation_buffer: list[Observation] = []
        self._phenomenon_start: datetime | None = None
        self._phenomenon_end: datetime | None = None
        self._sample_rate = sample_rate
        self._lock = threading.Lock()


    @abstractmethod
    def _check_trigger(self, observation:Observation) -> bool:
        """Check the flush condition of the buffer."""
        pass


    def add_observation(self, observation: Observation) -> None:
        with self._lock:
            if self.pending_flush:
                raise RuntimeError("Cannot add observations while a flush is pending.")

            if not self._phenomenon_start:
                self._phenomenon_start = observation.phenomenonTime_datetime

            self.observation_buffer.append(observation)
            if self._check_trigger(observation):
                self.pending_flush = True
            else:
                self.pending_flush = False

    def sample_results(self) -> list[Any]:
        """Sample result buffer result, return full buffer size if sample_rate==1."""
        results = [obs.result for obs in self.observation_buffer]
        if self._sample_rate == 1:
            return results
        else:
            n = len(self.observation_buffer) 
            target = max(1, round(n*self._sample_rate))
            sample_step = max(1, round(n // target))
            return results[::sample_step]


    def dump(self) -> Tuple[Observation, CanonicalDatastreams]:
        with self._lock:
            return self._dump_locked()

    def flush_pending(self) -> Tuple[Observation, CanonicalDatastreams] | None:
        with self._lock:
            if not self.observation_buffer:
                return None
            return self._dump_locked()

    def commit(self) -> None:
        with self._lock:
            self.observation_buffer.clear()
            self._phenomenon_start = None
            self.pending_flush = False

    @abstractmethod
    def _dump_locked(self) -> Tuple[Observation, CanonicalDatastreams]:
        pass

class NullBuffer(ObservationBuffer):
    """A no-op buffer which immediately flushes any data passed to it."""
    def __init__(
            self,
            datastream_name: CanonicalDatastreams,
            ):
        super().__init__(datastream_name)

    def _check_trigger(self, observation: Observation) -> bool:
        """The buffer is always pending a flush."""
        return True 

    def _dump_locked(self) -> Tuple[Observation, CanonicalDatastreams]:
        """There should only be observation in this buffer."""
        return (self.observation_buffer[0], self.datastream_name)


class TresholdBuffer(ObservationBuffer):
    """Buffer with a size of time-gap treshold."""

    def __init__(
        self,
        datastream_name: CanonicalDatastreams,
        *,
        max_time: timedelta | None = timedelta(minutes=10),
        max_size: int | None = None,
        sample_rate: float = 1.0
    ):
        super().__init__(
                datastream_name,
                sample_rate=sample_rate
                )

        if all([max_size, max_time]):
            raise ValueError("Pass either max_size or max_time, not both.")
        if not (0 < sample_rate <= 1.0):
            raise ValueError("sample_rate must be >0 and <=1")
        if not any([max_size, max_time]):
            raise ValueError("Pass either max_size or max_time.")

        self.max_size = max_size
        self.max_time = max_time


    def _check_trigger(self, observation: Observation) -> bool:

        if self.max_size and len(self.observation_buffer) == self.max_size:
            return True
        elif (
            self.max_time
            and self._phenomenon_start
            and (observation.phenomenonTime_datetime - self._phenomenon_start)
            > self.max_time
        ):
            return True

        return False


    def _dump_locked(self) -> Tuple[Observation, CanonicalDatastreams]:

        observation = Observation(
            result=self.sample_results(),
            phenomenonTime=(
                self._phenomenon_start,
                self.observation_buffer[-1].phenomenonTime_datetime,
            ),
        )

        return (observation, self.datastream_name)


class KinemetricsEtna2Buffer(TresholdBuffer):
    """Default Kinemetrics ETNA2 Buffer with a low sampling rate."""
    def __init__(self, datastream_name: CanonicalDatastreams):
        super().__init__(
                datastream_name, 
                max_time=timedelta(minutes=5), 
                sample_rate=0.01
                )

# Buffers kept in this registry:
def _return_null_buffer() -> type[ObservationBuffer]:
    return NullBuffer

BufferStoreKey = tuple[SensorUUID, SupportedSensors, CanonicalDatastreams]

BUFFER_TYPE_REGISTRY: DefaultDict[
        SupportedSensors,
        type[ObservationBuffer]
        ] = defaultdict(_return_null_buffer)
BUFFER_TYPE_REGISTRY.update(
        {SupportedSensors.KINEMETRICS_ETNA2:KinemetricsEtna2Buffer}
        )


@dataclass(frozen=True)
class BufferedObservationFlush:
    """A buffer snapshot ready for upload to FROST."""

    key: BufferStoreKey
    sensor_uuid: SensorUUID
    payload: Tuple[Observation, CanonicalDatastreams]


class TransportBufferStore:
    """Per-transport cache of in-flight observation buffers.

    Owns buffer lookup, ingestion, and flush coordination under one lock so
    add/check/dump/commit cannot race across worker threads.
    """

    def __init__(
        self,
        buffer_types: DefaultDict[SupportedSensors, type[ObservationBuffer]]
        | dict[SupportedSensors, type[ObservationBuffer]]
        | None = None,
    ):
        self._buffers: dict[BufferStoreKey, ObservationBuffer] = {}
        self._lock = threading.Lock()
        self._buffer_types = buffer_types or BUFFER_TYPE_REGISTRY

    def record_observation(
        self,
        sensor_uuid: SensorUUID,
        sensor_model: SupportedSensors,
        sta_observation: Tuple[Observation, CanonicalDatastreams],
    ) -> BufferedObservationFlush | None:
        """Append an observation and return a flush payload when ready."""
        with self._lock:
            observation, datastream_name = sta_observation
            key = (sensor_uuid, sensor_model, datastream_name)
            buffer = self._buffers.get(key)
            if buffer is None:
                buffer = self._buffer_types[sensor_model](datastream_name)
                self._buffers[key] = buffer
            buffer.add_observation(observation)
            if not buffer.pending_flush:
                return None
            return BufferedObservationFlush(
                key=key,
                sensor_uuid=sensor_uuid,
                payload=buffer.dump(),
            )

    def commit_flush(self, key: BufferStoreKey) -> None:
        """Clear a buffer after its flush payload has uploaded successfully."""
        with self._lock:
            buffer = self._buffers.get(key)
            if buffer is not None:
                buffer.commit()

    def drain_pending_for_sensors(
        self,
        sensor_uuids: Iterable[SensorUUID],
    ) -> list[BufferedObservationFlush]:
        """Return flush payloads for any non-empty buffers owned by *sensor_uuids*."""
        sensor_uuid_set = set(sensor_uuids)
        flushes: list[BufferedObservationFlush] = []
        with self._lock:
            for key, buffer in list(self._buffers.items()):
                sensor_uuid, _, _ = key
                if sensor_uuid not in sensor_uuid_set:
                    continue
                payload = buffer.flush_pending()
                if payload is None:
                    continue
                flushes.append(
                    BufferedObservationFlush(
                        key=key,
                        sensor_uuid=sensor_uuid,
                        payload=payload,
                    )
                )
        return flushes


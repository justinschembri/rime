"""Transport buffers."""
# stdlib
import threading
from datetime import timedelta, datetime
from typing import Tuple
from math import ceil
# internal
from rime_ingest.sta.core import Observation
from rime_ingest.transformers.types import CanonicalDatastreams


class ObservationBuffer:
    """Intermediate buffer for storing Observations before pushing to FROST."""

    def __init__(
        self,
        datastream_name: CanonicalDatastreams,
        *,
        phenomenon_start: datetime | str | None = None,
        max_time: timedelta | None = timedelta(minutes=10),
        max_size: int | None = None,
        sample_rate: float = 1.0
    ):
        if all([max_size, max_time]):
            raise ValueError("Pass either max_size or max_time, not both.")
        if (0 >= sample_rate > 1.0):
            raise ValueError(">0 sample_rate =<1")
        if not any([max_size, max_time]):
            raise ValueError("Pass either max_size or max_time.")

        if isinstance(phenomenon_start, str):
            self.phenomenon_start = datetime.fromisoformat(phenomenon_start)
        else:
            self.phenomenon_start = phenomenon_start
        self.datastream_name = datastream_name
        self.max_size = max_size
        self.max_time = max_time
        self.full: bool = False
        self.pending_flush: bool = False
        self.observation_buffer: list[Observation] = []
        self._sample_rate = sample_rate
        self._lock = threading.Lock()


    def add_observation(self, observation: Observation) -> None:
        with self._lock:
            if self.pending_flush:
                raise RuntimeError("Cannot add observations while a flush is pending.")

            if not self.phenomenon_start:
                self.phenomenon_start = observation.phenomenonTime_datetime

            self.observation_buffer.append(observation)
            if self.max_size and len(self.observation_buffer) == self.max_size:
                self.full = True
            elif (
                self.max_time
                and (observation.phenomenonTime_datetime - self.phenomenon_start)
                > self.max_time
            ):
                self.full = True

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
            self.phenomenon_start = None
            self.full = False
            self.pending_flush = False

    def _dump_locked(self) -> Tuple[Observation, CanonicalDatastreams]:
        self.pending_flush = True
        # buffered observations can be large, so you may want to sample.
        n = len(self.observation_buffer) 
        target = max(1, round(n*self._sample_rate))
        sample_step = max(1, round(n // target))

        results = [obs.result for obs in self.observation_buffer]
        observation = Observation(
            result=results[::sample_step],
            phenomenonTime=(
                self.phenomenon_start,
                self.observation_buffer[-1].phenomenonTime_datetime,
            ),
        )
        return (observation, self.datastream_name)


class KinemetricsEtna2Buffer(ObservationBuffer):
    """Default Kinemetrics ETNA2 Buffer with a low sampling rate."""
    def __init__(self, datastream_name: CanonicalDatastreams):
        super().__init__(
                datastream_name, 
                max_time=timedelta(minutes=5), 
                sample_rate=0.001
                )

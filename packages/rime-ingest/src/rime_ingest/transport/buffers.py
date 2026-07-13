"""Transport buffers."""
# stdlib
from datetime import timedelta, datetime
from typing import Any, Tuple

from rime_ingest.sta.core import Observation
from rime_ingest.transformers.types import CanonicalDatastreams


class ObservationBuffer:
    """
    A intermediate buffer for storing `Observations` before pushing to FROST.
    """
    def __init__(
            self,
            datastream_name: CanonicalDatastreams,
            *,
            phenomenon_start: datetime | str | None= None,
            max_time: timedelta | None = timedelta(minutes=10),
            max_size: int | None = None,
            ):
        if all([max_size, max_time]):
            raise ValueError("Pass either max_size or max_time, not both.")
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
        self.observation_buffer: list[Any] = []


    def add_observation(self, observation: Observation) -> None:

        if not self.phenomenon_start:
            self.phenomenon_start = observation.phenomenonTime_datetime

        if self.full:
            self.observation_buffer.clear()
            self.phenomenon_start = observation.phenomenonTime_datetime

        self.observation_buffer.append(observation.result)
        if self.max_size and len(self.observation_buffer) == self.max_size:
            self.full = True
        elif (self.max_time and (self.phenomenon_start - observation.phenomenonTime_datetime) > self.max_time):
            self.full = True


    def dump(self) -> Tuple[Observation, str]:
         observation = Observation(
                 result = self.observation_buffer, 
                 phenomenonTime = None,
                 phenomenonTime_interval = (
                     self.phenomenon_start, 
                     self.observation_buffer[-1].phenomenonTime)
                 )
         self.full = False
         return (observation, self.datastream_name)

class KinemetricsEtna2Buffer(ObservationBuffer):

    def __init__(self, datastream_name: str): 
        super().__init__(datastream_name, max_time=timedelta(minutes=5))

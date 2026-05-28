# standard
from typing import Any, Callable, Tuple
from datetime import datetime

# external
from pydantic import BaseModel, model_validator

# internal
from ..messages import ObservationRecord
from ..types import CanonicalDatastreams
from ...sta.core import Observation


class Normalizer(BaseModel):
    """Maps vendor observation fields (``ObservationRecord.observations``) to SensorThings observations."""

    provider_phenomenon_time: datetime | None = None
    TRANSFORM: dict[str, Callable] = {}
    NAME_TRANSFORM: dict[str, CanonicalDatastreams]

    @model_validator(mode="after")
    def _validate_transformers(self):
        try:
            if not self.NAME_TRANSFORM:
                raise NotImplementedError(
                    f"{self.__class__} must implement a non-empty " "NAME_TRANSFORMER."
                )
        except AttributeError:
            raise AttributeError(
                f"{self.__class__} must implement a NAME_TRANSFORM dict."
            )

        invalid_names = (
                set(self.NAME_TRANSFORM) - set(member.value for member in CanonicalDatastreams)
                )
        if invalid_names:
            raise AttributeError(
                    f"NameTransformer method has non-canonical datastream names:"
                    f" {invalid_names}"
                    )
        return self

    @classmethod
    def from_record(cls, record: ObservationRecord):
        obj = cls(**record.observations)
        obj.provider_phenomenon_time = record.phenomenon_timestamp or record.provider_timestamp
        return obj

    def _transform(self) -> dict[CanonicalDatastreams, Any]:
        """Apply the transformations to names and values."""
        for observed_property in self.TRANSFORM:
            value = getattr(self, observed_property)
            self.__setattr__(
                observed_property, self.TRANSFORM[observed_property](value)
            )

        transformed_results: dict[CanonicalDatastreams, Any] = {}
        for observed_property, datastream in self.NAME_TRANSFORM.items():
            transformed_results[datastream] = getattr(self, observed_property)
        return transformed_results

    def to_stObservations(self) -> list[Tuple[Observation, str]]:
        """Return a tuple of observations and corresponding datastream."""
        transformed_results = self._transform()
        observations = []
        for datastream, value in transformed_results.items():
            if datastream == CanonicalDatastreams.PHENOMENON_TIME:
                continue
            observation = Observation(
                id=None,
                result=value,
                phenomenonTime=(
                    transformed_results.get(CanonicalDatastreams.PHENOMENON_TIME)
                    or self.provider_phenomenon_time
                ),
            )
            observations.append((observation, datastream.value))
        return observations

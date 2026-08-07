# standard
from typing import Any, Callable, Tuple
from datetime import datetime

# external
from pydantic import BaseModel, model_validator

# internal
from ..messages import ObservationRecord
from ..types import CanonicalDatastreams
from ...sta.maps import class_map_for
from ...sta.schema import SensorThingsEntity


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

        canonical_values = {member.value for member in CanonicalDatastreams}
        invalid_values = {
            datastream.value for datastream in self.NAME_TRANSFORM.values()
        } - canonical_values
        if invalid_values:
            raise AttributeError(
                "NAME_TRANSFORM maps to non-canonical datastream names:"
                f" {invalid_values}"
            )
        return self

    @classmethod
    def from_record(cls, record: ObservationRecord):
        obj = cls(**record.observations)
        obj.provider_phenomenon_time = record.phenomenon_timestamp or record.provider_timestamp
        return obj

    def _transform(self) -> dict[CanonicalDatastreams, Any]:
        """Apply the transformations to names and values."""
        
        for model_datastream_name in self.TRANSFORM:
            value = getattr(self, model_datastream_name)
            self.__setattr__(
                model_datastream_name, self.TRANSFORM[model_datastream_name](value)
            )

        transformed_results: dict[CanonicalDatastreams, Any] = {}
        for model_datastream_name, canonical_datastream_name in self.NAME_TRANSFORM.items():
            transformed_results[canonical_datastream_name] = getattr(self, model_datastream_name)
        return transformed_results

    def to_stObservations(self) -> list[Tuple[Any, CanonicalDatastreams]]:
        """Return a tuple of observations and corresponding datastream."""
        observation_cls = class_map_for()[SensorThingsEntity.OBSERVATION]
        transformed_results = self._transform()
        observations = []
        for datastream, value in transformed_results.items():
            if datastream == CanonicalDatastreams.PHENOMENON_TIME:
                continue
            if value is None:
                continue
            observation = observation_cls(
                id=None,
                result=value,
                phenomenonTime=(
                    transformed_results.get(CanonicalDatastreams.PHENOMENON_TIME)
                    or self.provider_phenomenon_time
                ),
            )
            observations.append((observation, datastream))
        return observations

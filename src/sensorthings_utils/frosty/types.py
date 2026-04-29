"""FROST server types."""
#standard
from typing import Iterator, Any
from enum import Enum
from dataclasses import dataclass
import re

from sensorthings_utils.sensor_things.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
    ENTITY_GROUPS_TO_ENTITIES,
)

FrostUrl = str

class FrostVersions(Enum):
    v1 = "1"
    v1_1 = "1.1"

class FrostEndpoints(Enum):
    """FROST Server entity endpoints. Camelcase for conistency."""
    DATASTREAMS = "/Datastreams"
    FEATURESOFINTEREST = "/FeaturesOfInterest"
    HISTORICALLOCATIONS = "/HistoricalLocations"
    LOCATIONS = "/Locations"
    OBSERVATIONS = "/Observations"
    OBSERVEDPROPERTIES = "/ObservedProperties"
    SENSORS = "/Sensors"
    THINGS = "/Things"

class FrostParams(Enum):
    """FROST Server query params."""
    TOP="$top"
    SKIP="$skip"
    COUNT="$count"
    ORDER="$orderBy"
    EXPAND="$expand"
    SELECT="$select"
    FILTER="$filter"

FrostResultPageIterator = Iterator[list[dict[str, Any]]]


@dataclass(frozen=True)
class FrostEntityRef:
    """Typed reference to a persisted FROST entity."""

    entity: SensorThingsEntity
    iot_id: int
    root_url: str
    version: str

    @classmethod
    def from_frost_url(cls, url: FrostUrl) -> "FrostEntityRef":
        match = re.match(r"^(https?://.+)/v([^/]+)(/[^()]+)\((\d+)\)$", url)
        if not match:
            raise ValueError(f"Unexpected FROST entity URL format: {url}")

        root_url, version, endpoint, iot_id = match.groups()
        endpoint_name = endpoint.lstrip("/")
        try:
            entity_group = SensorThingsEntityGroups(endpoint_name)
        except ValueError as e:
            raise ValueError(f"Unsupported FROST endpoint in URL: {endpoint}") from e
        entity = ENTITY_GROUPS_TO_ENTITIES[entity_group]

        return cls(entity=entity, iot_id=int(iot_id), root_url=root_url, version=version)

    def as_iot_ref(self) -> dict[str, int]:
        return {"@iot.id": self.iot_id}

    def as_frost_url(self, endpoint_path: str) -> FrostUrl:
        return f"{self.root_url}/v{self.version}{endpoint_path}({self.iot_id})"

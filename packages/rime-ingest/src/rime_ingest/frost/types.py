"""FROST server types."""
#standard
from typing import Iterator, Any
from enum import Enum
from dataclasses import dataclass
import re

from rime_ingest.sta.schema import (
    SensorThingsEntity,
    SensorThingsEntityGroups,
    ENTITY_GROUPS_TO_ENTITIES,
)

FrostUrl = str

class FrostVersions(Enum):
    """Supported FROST Server API versions."""

    v1 = "1"
    v1_1 = "1.1"

class FrostEndpoints(Enum):
    """FROST Server entity collection endpoints.

    Values are URL path segments appended directly to the versioned base URL
    (e.g. ``/v1.1/Datastreams``).
    """
    DATASTREAMS = "/Datastreams"
    FEATURESOFINTEREST = "/FeaturesOfInterest"
    HISTORICALLOCATIONS = "/HistoricalLocations"
    LOCATIONS = "/Locations"
    OBSERVATIONS = "/Observations"
    OBSERVEDPROPERTIES = "/ObservedProperties"
    SENSORS = "/Sensors"
    THINGS = "/Things"

FrostResultPageIterator = Iterator[list[dict[str, Any]]]


@dataclass(frozen=True)
class FrostEntityRef:
    """Typed reference to a persisted FROST entity.

    Encapsulates the entity type, numeric ``@iot.id``, server root URL, and
    API version so that callers can reconstruct the full entity URL or produce
    OData ``{"@iot.id": ...}`` link objects without string manipulation.

    Attributes:
        entity: The SensorThings entity type (e.g. ``SENSOR``, ``DATASTREAM``).
        iot_id: The numeric ``@iot.id`` assigned by the server.
        root_url: FROST server root URL, without the version segment.
        version: API version enum value.
    """

    entity: SensorThingsEntity
    iot_id: int
    root_url: str
    version: FrostVersions

    @classmethod
    def from_frost_url(cls, url: FrostUrl) -> "FrostEntityRef":
        """Parse a FROST entity URL into a ``FrostEntityRef``.

        Args:
            url: A fully-qualified FROST entity URL of the form
                ``http(s)://<host>/<base>/v<version>/<Entity>(<id>)``.

        Returns:
            A new ``FrostEntityRef`` instance.

        Raises:
            ValueError: When the URL format is unrecognised or the endpoint
                segment does not map to a known entity group.
        """
        match = re.match(r"^(https?://.+)/v([^/]+)(/[^()]+)\((\d+)\)$", url)
        if not match:
            raise ValueError(f"Unexpected FROST entity URL format: {url}")

        root_url, version, endpoint, iot_id = match.groups()
        version = FrostVersions(version)
        endpoint_name = endpoint.lstrip("/")
        try:
            entity_group = SensorThingsEntityGroups(endpoint_name)
        except ValueError as e:
            raise ValueError(f"Unsupported FROST endpoint in URL: {endpoint}") from e
        entity = ENTITY_GROUPS_TO_ENTITIES[entity_group]

        return cls(entity=entity, iot_id=int(iot_id), root_url=root_url, version=version)

    @property
    def iot_ref(self) -> dict[str, int]:
        """Return an OData ``{"@iot.id": <id>}`` link dict for this entity."""
        return {"@iot.id": self.iot_id}

    @property
    def frost_url(self) -> FrostUrl:
        """Reconstruct the full FROST entity URL from stored components."""
        from rime_ingest.frost.bridges import ENTITY_TO_FROST_ENDPOINT
        endpoint = ENTITY_TO_FROST_ENDPOINT[self.entity]
        return f"{self.root_url}/v{self.version.value}{endpoint.value}({self.iot_id})"

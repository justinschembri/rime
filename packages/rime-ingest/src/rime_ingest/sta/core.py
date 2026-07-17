"""
PyObject representations of the OGC SensorThings API (STA) information model.
"""

# standard
from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, Dict, List, Tuple, Union, Self
from typing_extensions import Annotated
# external
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
    computed_field,
)
# internal
from rime_ingest.frost.bridges import navigation_link_to_entity
from rime_ingest.frost.odata import PhenomenonTime, format_phenomenon_time
from rime_ingest.frost.types import FrostUrl
from rime_ingest.frost.types import FrostEntityRef
from rime_ingest.frost import versions as frost_versions
from rime_ingest.frost.versions import FrostVersions
from .schema import (
    ENTITIES_TO_ENTITY_GROUPS,
    SENSOR_THINGS_ENTITY_FIELDS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)


def _build_from_frost_entity(cls: type, entity: Dict[str, Any]) -> Any:
    """
    Construct a pydantic model from a FROST entity JSON dict.

    This is an abstract function intended for use with any Python STA object 
    defined in the remainder of this module.

    Drops self-link and navigation-link keys, hoists the version-aware id
    field into the model's ``id`` when present, and silently discards any
    payload key that the model does not expose. Using an explicit
    ``model_fields`` filter rather than ``extra="ignore"`` globally means a
    typo in a config-driven constructor still fails loudly.
    """
    model_fields = set(cls.model_fields)
    field_kwargs: dict[str, Any] = {k: v for k, v in entity.items() if k in model_fields}
    if frost_versions.FROST_ID_FIELD in entity:
        field_kwargs["id"] = entity[frost_versions.FROST_ID_FIELD]
    iot_links: dict[
        SensorThingsEntity | SensorThingsEntityGroups, FrostUrl | list[FrostUrl]
    ] = {}
    for key, value in entity.items():
        mapped_entity = navigation_link_to_entity(key)
        if mapped_entity is None:
            continue
        if isinstance(value, list):
            iot_links[mapped_entity] = [str(v) for v in value]
        else:
            iot_links[mapped_entity] = str(value)
    if iot_links:
        field_kwargs["iot_links"] = iot_links
    return cls(**field_kwargs)


def _normalise_dump(d: dict) -> dict:
    """Normalise a model_dump dict for content comparison.

    FROST returns `{}` for null/absent `properties` fields, while YAML configs
    often supply `None`. Treat both as equivalent so existence checks don't
    produce false negatives.
    """
    return {k: (v if v is not None else {}) if k == "properties" else v for k, v in d.items()}


def _partial_equals(a: "BaseModel", b: "BaseModel") -> bool:
    """Compare two SensorThings models on their content fields only.

    "Content fields" are those enumerated in
    `schema.SENSOR_THINGS_ENTITY_FIELDS` for the entity type. This
    deliberately excludes `id`, `links`, `iot_links`, and any server-computed
    fields like a Datastream's `observedArea` / `phenomenonTime`.

    Returns `False` when the two objects resolve to different entity types
    (e.g. `Thing` vs `Sensor`).
    """
    a_entity = a.entity_type  # type: ignore[attr-defined]
    b_entity = b.entity_type  # type: ignore[attr-defined]
    if a_entity != b_entity:
        return False
    fields = set(SENSOR_THINGS_ENTITY_FIELDS[a_entity])
    return (
        _normalise_dump(a.model_dump(include=fields))
        == _normalise_dump(b.model_dump(include=fields))
    )

class SensorThingsObject(BaseModel):
    """
    Parent dataclass for all non-observation OGC Sensor Things Objects.

    Attribute names (and formatting) match those used by the SensorThings Data model,
    thus the use of camelCase.
    """

    id: Optional[int] = None
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    links: Optional[
            Dict[SensorThingsEntity, List["SensorThingsObject"]]
            ] = Field(default_factory=dict)
    iot_links: Optional[
        Dict[
            SensorThingsEntity | SensorThingsEntityGroups,
            List[FrostUrl | FrostEntityRef] | FrostUrl | FrostEntityRef,
        ]
    ] = Field(default_factory=dict)

    @computed_field
    @property
    def entity_type(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__)
        return st_type 

    @classmethod
    def from_frost_entity(cls, entity: dict[str, Any]) -> Self:
        """Build a model from a FROST (OData) entity payload."""
        return _build_from_frost_entity(cls, entity)

    def as_frost_entity(self) -> dict[str, Any]:
        """Dump model fields allowed for a create/update STA JSON body (no iot id/refs)."""
        include = set(SENSOR_THINGS_ENTITY_FIELDS[self.entity_type])
        # version compatibility: STA 1.x uses observationType; 2.x uses resultType
        if self.entity_type == SensorThingsEntity.DATASTREAM:
            if frost_versions.FROST_VERSION == FrostVersions.v2:
                include.discard("observationType")
            else:
                include.discard("resultType")
        return self.model_dump(include=include)

    def partial_eq(self, other: "SensorThingsObject") -> bool:
        """Content-only equality (ignores id, links, iot_links).

        Use when you want to ask "is this the same SensorThings object as
        one the server already has, regardless of identifiers and
        relationships?". Full equality stays on `__eq__`.
        """
        return _partial_equals(self, other)

    def __hash__(self) -> int:
        return hash((self.name, str(self.__class__)))

    def __repr__(self) -> str:
        return self.__repr_name__() + " (name=" + self.name + ")"

    def attach_ref(self, ref: FrostEntityRef) -> None:
        """Slot a persisted FROST ref into the matching `iot_links` bucket.

        Replaces a name placeholder (loaded from a YAML config) with a real
        `FrostEntityRef` keyed by the ref's plural group (e.g. a Sensor ref
        lands at `iot_links[SensorThingsEntityGroups.SENSORS][0]`). When the
        bucket does not exist yet, a single-element list is created so callers
        can stay agnostic of pre-existing state.
        """
        group = ENTITIES_TO_ENTITY_GROUPS[ref.entity]
        if self.iot_links is None:
            self.iot_links = {}
        bucket = self.iot_links.get(group)
        if isinstance(bucket, list) and bucket:
            bucket[0] = ref
        else:
            self.iot_links[group] = [ref]


class Sensor(SensorThingsObject):
    encodingType: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    metadata: Optional[Any] = None


class Thing(SensorThingsObject):
    pass


class Datastream(SensorThingsObject):
    observationType: str | None = None
    resultType: str | None = None
    unitOfMeasurement: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def handle_frost_version(self) -> Self:
        """Map observationType <-> resultType for the active FROST version."""
        if frost_versions.FROST_VERSION == FrostVersions.v2:
            if self.observationType and not self.resultType:
                self.resultType = self.observationType
            self.observationType = None
        else:
            if self.resultType and not self.observationType:
                self.observationType = self.resultType
            self.resultType = None
        return self

    def as_frost_entity(self) -> dict[str, Any]:
        payload = super().as_frost_entity()
        links = self.iot_links or {}
        link_map = {
            SensorThingsEntityGroups.SENSORS: "Sensor",
            SensorThingsEntityGroups.THINGS: "Thing",
            SensorThingsEntityGroups.OBSERVEDPROPERTIES: "ObservedProperty",
        }
        for group, field in link_map.items():
            refs = links.get(group)
            if not refs:
                continue
            ref = refs[0]
            if isinstance(ref, FrostEntityRef):
                payload[field] = ref.iot_ref
        return payload


class Location(SensorThingsObject):
    encodingType: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    location: dict


class ObservedProperty(SensorThingsObject):
    definition: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]


class Observation(BaseModel):
    id: Optional[int] = Field(None, description="Generally assigned by the server.")
    result: Any | list[Any]
    phenomenonTime: PhenomenonTime | None
    iot_links: Dict[
        SensorThingsEntity | SensorThingsEntityGroups, FrostUrl | FrostEntityRef
    ] = Field(default_factory=dict)
    resultTime: datetime | None = None
    validTime: "TimePeriod | None" = None

    
    @computed_field
    @property
    def entity_type(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__)
        return st_type 

    @computed_field
    @property
    def phenomenonTime_datetime(self) -> datetime:
        """Return phenomenonTime as a point-in-time datetime."""
        if not self.phenomenonTime:
            raise ValueError("No phenomenonTime given.")
        if isinstance(self.phenomenonTime, tuple):
            raise ValueError("phenomenonTime is an interval, not an instant.")
        if isinstance(self.phenomenonTime, str):
            return datetime.fromisoformat(self.phenomenonTime)
        return self.phenomenonTime

    @classmethod
    def from_frost_entity(cls, entity: dict[str, Any]) -> "Observation":
        """Build an `Observation` from a FROST entity payload.

        See `SensorThingsObject.from_frost_entity` for the filtering rules.
        """
        return _build_from_frost_entity(cls, entity)

    def as_frost_entity(self) -> dict[str, Any]:
        """Dump observation fields for POST (excludes iot_links and server ids)."""
        include = set(SENSOR_THINGS_ENTITY_FIELDS[self.entity_type])
        entity = self.model_dump(include=include)
        if self.phenomenonTime is not None:
            entity["phenomenonTime"] = format_phenomenon_time(self.phenomenonTime)
        return entity

    def partial_eq(self, other: "Observation") -> bool:
        """Content-only equality for Observations.

        Compares `phenomenonTime`, `resultTime`, `result`, and `validTime`;
        ignores `iot_links`. Normalises ``phenomenonTime`` to the canonical
        FROST string form so datetimes and ISO strings compare equal.
        """
        if not isinstance(other, Observation):
            return False
        fields = set(SENSOR_THINGS_ENTITY_FIELDS[self.entity_type])
        a = _normalise_dump(self.model_dump(include=fields))
        b = _normalise_dump(other.model_dump(include=fields))
        for side in (a, b):
            phenomenon_time = side.get("phenomenonTime")
            if phenomenon_time is not None:
                side["phenomenonTime"] = format_phenomenon_time(phenomenon_time)
        return a == b


class TimePeriod(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def check_valid_time(self) -> Self:
        if self.end < self.start:
            raise ValueError("End period before start period.")
        return self

# all these non-observation STA objects do NOT need an iot link:
UnLinkedSensorThingsObjects = Union[Thing, Location, Sensor, ObservedProperty]
# ... these must, or usually do have a linkage. Technically Observation can be 
# unlinked, but we choose not to enforce this.
LinkedSensorThingsObjects = Union[Datastream, Observation]

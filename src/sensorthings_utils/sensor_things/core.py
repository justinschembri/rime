"""
PyObject representations of the OGC SensorThings API (STA) information model.
"""

# standard
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional, Any, Dict, List, Union, Self
from typing_extensions import Annotated
# external
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
    computed_field,
)

from sensorthings_utils.frost import UrlStr
from sensorthings_utils.frosty.types import NAVIGATION_LINKS_TO_ENTITY
# internal
from .schema import (
    SENSOR_THINGS_ENTITY_FIELDS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)


def _build_from_frost_entity(cls: type, entity: Dict[str, Any]) -> Any:
    """Construct a pydantic model from a FROST entity JSON dict.

    Drops `@iot.selfLink` and `*@iot.navigationLink` keys, hoists `@iot.id`
    into the model's `id` field when declared, and silently discards any
    payload key that the model does not expose. Using an explicit
    `model_fields` filter rather than `extra="ignore"` globally means a
    typo in a config-driven constructor still fails loudly.
    """
    model_fields = set(cls.model_fields)
    field_kwargs: dict[str, Any] = {k: v for k, v in entity.items() if k in model_fields}
    if "@iot.id" in entity:
        field_kwargs["id"] = entity["@iot.id"]
    iot_links: dict[SensorThingsEntity | SensorThingsEntityGroups, str] = {}
    for key, value in entity.items():
        mapped_entity = NAVIGATION_LINKS_TO_ENTITY.get(key)
        if mapped_entity is None:
            continue
        iot_links[mapped_entity] = str(value)
    if iot_links:
        field_kwargs["iot_links"] = iot_links
    return cls(**field_kwargs)


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
    return a.model_dump(include=fields) == b.model_dump(include=fields)


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
            Dict[SensorThingsEntityGroups, List[UrlStr]] | 
            Dict[SensorThingsEntity, UrlStr]
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

    def as_frost_entity(self) -> str:
        """Dump Object model into a FROST shaped JSON entity."""
        return self.model_dump_json()

    def partial_eq(self, other: "SensorThingsObject") -> bool:
        """Content-only equality (ignores id, links, iot_links).

        Use when you want to ask "is this the same SensorThings object as
        one the server already has, regardless of identifiers and
        relationships?". Full equality stays on `__eq__`.
        """
        return _partial_equals(self, other)

    # TODO: #4 The state of iot_links as 'str' should be temporary or stored in another attribute.
    def __hash__(self) -> int:
        return hash((self.name, str(self.__class__)))

    def __repr__(self) -> str:
        return self.__repr_name__() + " (name=" + self.name + ")"

    #TODO: check if this is still neccesary:
    def set_link(
        self,
        entity: SensorThingsEntityGroups,
        instance: str,
        sensor_things_object: "SensorThingsObject",
    ) -> None:
        """Set an `iot_link` dict value."""
        set_index = self.iot_links[entity].index(instance)
        self.iot_links[entity][set_index] = sensor_things_object  # type: ignore


class Sensor(SensorThingsObject):
    encodingType: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    metadata: Optional[Any] = None


class Thing(SensorThingsObject):
    pass


class Datastream(SensorThingsObject):
    observationType: str
    unitOfMeasurement: Optional[Dict[str, Any]] = Field(default_factory=dict)


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
    result: Any
    phenomenonTime: datetime | None
    iot_links: Dict[SensorThingsEntity | SensorThingsEntityGroups, UrlStr] = Field(
        default_factory=dict
    )
    resultTime: datetime | None = None
    validTime: "TimePeriod | None" = None

    @computed_field
    @property
    def entity_type(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__)
        return st_type 

    @classmethod
    def from_frost_entity(cls, entity: dict[str, Any]) -> "Observation":
        """Build an `Observation` from a FROST entity payload.

        See `SensorThingsObject.from_frost_entity` for the filtering rules.
        """
        return _build_from_frost_entity(cls, entity)

    def as_frost_entity(self) -> str:
        """Dump Observation model into a FROST shaped JSON entity."""
        return self.model_dump_json()

    def partial_eq(self, other: "Observation") -> bool:
        """Content-only equality for Observations.

        Compares `phenomenonTime`, `resultTime`, `result`, and `validTime`;
        ignores `iot_links`.
        """
        return _partial_equals(self, other)


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

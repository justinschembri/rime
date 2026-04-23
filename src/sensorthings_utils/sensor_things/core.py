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
    kwargs = {k: v for k, v in entity.items() if k in model_fields}
    if "id" in model_fields and "@iot.id" in entity:
        kwargs["id"] = entity["@iot.id"]
    return cls(**kwargs)


def _partial_equals(a: "BaseModel", b: "BaseModel") -> bool:
    """Compare two SensorThings models on their content fields only.

    "Content fields" are those enumerated in
    `schema.SENSOR_THINGS_ENTITY_FIELDS` for the entity type. This
    deliberately excludes `id`, `links`, `iot_links`, and any server-computed
    fields like a Datastream's `observedArea` / `phenomenonTime`.

    Returns `False` when the two objects resolve to different entity types
    (e.g. `Thing` vs `Sensor`).
    """
    if a.as_entity != b.as_entity:  # type: ignore[attr-defined]
        return False
    fields = set(SENSOR_THINGS_ENTITY_FIELDS[a.as_entity])  # type: ignore[attr-defined]
    return a.model_dump(include=fields) == b.model_dump(include=fields)


class SensorThingsObject(BaseModel):
    """
    Parent dataclass for all non-observation OGC Sensor Things Objects.

    Attribute names (and formatting) match those used by the SensorThings Data model,
    thus the use of camelCase.
    """

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    links: Optional[Dict[SensorThingsEntity, List["SensorThingsObject"]]] = Field(
        default_factory=dict
    )
    iot_links: Optional[
            Dict[SensorThingsEntityGroups, List[int]] | 
            Dict[SensorThingsEntity, int]
            ] = Field(default_factory=dict)

    @computed_field
    @property
    def entity_type(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__)
        return st_type 

    @classmethod
    def from_frost_entity(cls, entity: dict[str, Any]) -> Self:
        """Build a model from a FROST (OData) entity payload.

        Strips `@iot.selfLink` and all `*@iot.navigationLink` keys, hoists
        `@iot.id` into `id` when the subclass declares it, and discards any
        other key the subclass does not declare.
        """
        return _build_from_frost_entity(cls, entity)

    def as_frost_entity(self) -> str:
        """Dump Object model into a FROST shaped JSON entity."""
        ...

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

    def set_iot_link(
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
    id: Optional[int] = None


class Thing(SensorThingsObject):
    id: Optional[int] = Field(
        None, description="Generally assigned by the server."
    )  # TODO: #3 Do you really need an id field?


class Datastream(SensorThingsObject):
    observationType: str
    unitOfMeasurement: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: Optional[int] = Field(None, description="Generally assigned by the server.")


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
    result: Any
    phenomenonTime: datetime | None
    iot_links: Dict[
        SensorThingsEntity, int
       ] = Field(default_factory=dict)
    resultTime: datetime | None = None
    validTime: "TimePeriod | None" = None

    @computed_field
    @property
    def as_entity(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__)
        return st_type 

    @classmethod
    def from_frost_entity(cls, entity: dict[str, Any]) -> "Observation":
        """Build an `Observation` from a FROST entity payload.

        See `SensorThingsObject.from_frost_entity` for the filtering rules.
        """
        return _build_from_frost_entity(cls, entity)

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

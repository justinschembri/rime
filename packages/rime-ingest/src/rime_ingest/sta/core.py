"""
PyObject representations of the OGC SensorThings API (STA) information model.

STA 1.x and 2.0 share identity bases (``Thing``, ``Datastream``, …) for
``isinstance`` checks. Concrete ``*V1`` / ``*V2`` subclasses own the
version-specific attribute sets from OGC 23-019 Table 2. YAML construction and
FROST POST/GET select the concrete class via ``sta.maps.class_map_for``.
"""

# standard
from __future__ import annotations
from datetime import datetime
from typing import ClassVar, Optional, Any, Dict, List, Union, Self
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
from rime_ingest.frost.bridges import datastream_link_bindings, navigation_link_to_entity
from rime_ingest.frost.odata import PhenomenonTime, format_phenomenon_time
from rime_ingest.frost.types import FrostUrl
from rime_ingest.frost.types import FrostEntityRef
from rime_ingest.frost.versions import FrostVersions
from .schema import (
    ENTITIES_TO_ENTITY_GROUPS,
    SensorThingsEntity,
    SensorThingsEntityGroups,
)

_Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
_RequiredDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
_OptionalUri = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)
]


def _build_from_frost_entity(cls: type, entity: Dict[str, Any]) -> Any:
    """
    Construct a pydantic model from a FROST entity JSON dict.

    Drops self-link and navigation-link keys, hoists the version-aware id
    field into the model's ``id`` when present, and silently discards any
    payload key that the model does not expose. Using an explicit
    ``model_fields`` filter rather than ``extra="ignore"`` globally means a
    typo in a config-driven constructor still fails loudly.
    """
    from rime_ingest.frost import versions as frost_versions

    model_fields = set(cls.model_fields)
    field_kwargs: dict[str, Any] = {k: v for k, v in entity.items() if k in model_fields}
    for id_key in (frost_versions.FROST_ID_FIELD, "id", "@iot.id"):
        if id_key in entity:
            field_kwargs["id"] = entity[id_key]
            break
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
    return {
        k: (v if v is not None else {}) if k == "properties" else v for k, v in d.items()
    }


def _partial_equals(a: "BaseModel", b: "BaseModel") -> bool:
    """Compare two SensorThings models on their content fields only.

    Uses each concrete class's ``_content_fields``. Objects of different entity
    types never compare equal.
    """
    a_entity = a.entity_type  # type: ignore[attr-defined]
    b_entity = b.entity_type  # type: ignore[attr-defined]
    if a_entity != b_entity:
        return False
    a_fields = getattr(type(a), "_content_fields", None)
    b_fields = getattr(type(b), "_content_fields", None)
    if not a_fields or a_fields != b_fields:
        return False
    return (
        _normalise_dump(a.model_dump(include=set(a_fields)))
        == _normalise_dump(b.model_dump(include=set(b_fields)))
    )


class SensorThingsObject(BaseModel):
    """
    Parent for all non-observation OGC SensorThings entities.

    Concrete ``*V1`` / ``*V2`` subclasses set ``_entity_type``,
    ``_content_fields``, and version-specific attributes. Attribute names match
    the SensorThings JSON model (camelCase).
    """

    _entity_type: ClassVar[SensorThingsEntity]
    _content_fields: ClassVar[frozenset[str]]
    _sta_version: ClassVar[FrostVersions]

    id: Optional[int] = None
    name: _Name
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    links: Optional[Dict[SensorThingsEntity, List["SensorThingsObject"]]] = Field(
        default_factory=dict
    )
    iot_links: Optional[
        Dict[
            SensorThingsEntity | SensorThingsEntityGroups,
            List[FrostUrl | FrostEntityRef] | FrostUrl | FrostEntityRef,
        ]
    ] = Field(default_factory=dict)

    @computed_field
    @property
    def entity_type(self) -> SensorThingsEntity:
        return type(self)._entity_type

    @classmethod
    def from_frost_entity(cls, entity: dict[str, Any]) -> Self:
        """Build a model from a FROST (OData) entity payload."""
        return _build_from_frost_entity(cls, entity)

    def as_frost_entity(self) -> dict[str, Any]:
        """Dump model fields allowed for a create/update STA JSON body.

        Omits keys whose value is ``None`` so optional STA 2.0 attributes
        (``definition``, ``resultEncoding``, …) are not posted as JSON null.
        """
        payload = self.model_dump(include=set(type(self)._content_fields))
        return {k: v for k, v in payload.items() if v is not None}

    def partial_eq(self, other: "SensorThingsObject") -> bool:
        """Content-only equality (ignores id, links, iot_links)."""
        return _partial_equals(self, other)

    def __hash__(self) -> int:
        return hash((self.name, str(self.__class__)))

    def __repr__(self) -> str:
        return self.__repr_name__() + " (name=" + self.name + ")"

    def attach_ref(self, ref: FrostEntityRef) -> None:
        """Slot a persisted FROST ref into the matching `iot_links` bucket."""
        group = ENTITIES_TO_ENTITY_GROUPS[ref.entity]
        if self.iot_links is None:
            self.iot_links = {}
        bucket = self.iot_links.get(group)
        if isinstance(bucket, list) and bucket:
            bucket[0] = ref
        else:
            self.iot_links[group] = [ref]


class Thing(SensorThingsObject):
    """Shared Thing identity (STA 1.x and 2.0)."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.THING


class ThingV1(Thing):
    """STA 1.x Thing — description mandatory; no definition."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "properties"}
    )
    description: _RequiredDescription


class ThingV2(Thing):
    """STA 2.0 Thing — description optional; definition added (OGC 23-019)."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "definition", "properties"}
    )
    definition: Optional[_OptionalUri] = None


class Sensor(SensorThingsObject):
    """Shared Sensor identity."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.SENSOR
    encodingType: _Name
    metadata: Optional[Any] = None


class SensorV1(Sensor):
    """STA 1.x Sensor — description mandatory."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "encodingType", "metadata", "properties"}
    )
    description: _RequiredDescription


class SensorV2(Sensor):
    """STA 2.0 Sensor — description optional; definition added."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "description",
            "definition",
            "encodingType",
            "metadata",
            "properties",
        }
    )
    definition: Optional[_OptionalUri] = None


class Location(SensorThingsObject):
    """Shared Location identity."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.LOCATION
    encodingType: _Name
    location: dict


class LocationV1(Location):
    """STA 1.x Location — description mandatory."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "encodingType", "location", "properties"}
    )
    description: _RequiredDescription


class LocationV2(Location):
    """STA 2.0 Location — description optional; definition added."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "description",
            "definition",
            "encodingType",
            "location",
            "properties",
        }
    )
    definition: Optional[_OptionalUri] = None


class Datastream(SensorThingsObject):
    """Shared Datastream identity; wire shape lives on V1 / V2 subclasses."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.DATASTREAM

    def as_frost_entity(self) -> dict[str, Any]:
        payload = super().as_frost_entity()
        links = self.iot_links or {}
        version = getattr(type(self), "_sta_version", None)
        for group, binding in datastream_link_bindings(version).items():
            refs = links.get(group)
            if not refs:
                continue
            if not isinstance(refs, list):
                refs = [refs]
            resolved = [r for r in refs if isinstance(r, FrostEntityRef)]
            if not resolved:
                continue
            if binding.as_collection:
                payload[binding.field] = [r.iot_ref for r in resolved]
            else:
                payload[binding.field] = resolved[0].iot_ref
        return payload


class DatastreamV1(Datastream):
    """STA 1.x Datastream — observationType + unitOfMeasurement."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "description",
            "observationType",
            "unitOfMeasurement",
            "properties",
        }
    )
    description: _RequiredDescription
    observationType: _Name
    unitOfMeasurement: Dict[str, Any] = Field(default_factory=dict)


class DatastreamV2(Datastream):
    """STA 2.0 Datastream — resultType (SWE-Common) embeds units; no observationType."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "description",
            "definition",
            "resultType",
            "resultEncoding",
            "properties",
        }
    )
    definition: Optional[_OptionalUri] = None
    resultType: Dict[str, Any]
    resultEncoding: Optional[Dict[str, Any]] = None


class ObservedProperty(SensorThingsObject):
    """Shared ObservedProperty identity."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.OBSERVEDPROPERTY
    definition: _Name


class ObservedPropertyV1(ObservedProperty):
    """STA 1.x ObservedProperty — description mandatory."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "definition", "properties"}
    )
    description: _RequiredDescription


class ObservedPropertyV2(ObservedProperty):
    """STA 2.0 ObservedProperty — description optional."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "definition", "properties"}
    )


class FeatureOfInterest(SensorThingsObject):
    """STA 1.x FeatureOfInterest."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.FEATUREOFINTEREST
    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "encodingType", "feature", "properties"}
    )
    description: _RequiredDescription
    encodingType: _Name
    feature: dict


class Feature(SensorThingsObject):
    """STA 2.0 Feature (replaces FeatureOfInterest; OGC 23-019)."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.FEATURE
    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "name",
            "description",
            "definition",
            "encodingType",
            "feature",
            "properties",
        }
    )
    definition: Optional[_OptionalUri] = None
    encodingType: _Name
    feature: dict

class FeatureType(SensorThingsObject):
    """STA 2.0 FeatureType — type metadata for Features."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.FEATURE_TYPE
    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "description", "definition", "properties"}
    )
    definition: Optional[_OptionalUri] = None


class Observation(BaseModel):
    """Shared Observation identity; V1/V2 differ on properties vs parameters."""

    _entity_type: ClassVar[SensorThingsEntity] = SensorThingsEntity.OBSERVATION
    _content_fields: ClassVar[frozenset[str]]
    _sta_version: ClassVar[FrostVersions]

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
        return type(self)._entity_type

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
    def from_frost_entity(cls, entity: dict[str, Any]) -> Self:
        return _build_from_frost_entity(cls, entity)

    def as_frost_entity(self) -> dict[str, Any]:
        entity = self.model_dump(include=set(type(self)._content_fields))
        if self.phenomenonTime is not None:
            entity["phenomenonTime"] = self._format_phenomenon_time(self.phenomenonTime)
        if self.validTime is not None:
            entity["validTime"] = self._format_valid_time(self.validTime)
        return entity

    def _format_phenomenon_time(self, value: PhenomenonTime) -> Any:
        return format_phenomenon_time(value)

    def _format_valid_time(self, value: "TimePeriod") -> Any:
        return f"{value.start.isoformat()}/{value.end.isoformat()}"

    def partial_eq(self, other: "Observation") -> bool:
        if not isinstance(other, Observation):
            return False
        if type(self)._content_fields != type(other)._content_fields:
            return False
        fields = set(type(self)._content_fields)
        a = _normalise_dump(self.model_dump(include=fields))
        b = _normalise_dump(other.model_dump(include=fields))
        for side in (a, b):
            phenomenon_time = side.get("phenomenonTime")
            if phenomenon_time is not None:
                side["phenomenonTime"] = format_phenomenon_time(phenomenon_time)
        return a == b


class ObservationV1(Observation):
    """STA 1.x Observation — optional parameters; FoI was mandatory on the server."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v1_1
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"phenomenonTime", "resultTime", "result", "validTime", "parameters"}
    )
    parameters: Optional[Dict[str, Any]] = None


class ObservationV2(Observation):
    """STA 2.0 Observation — properties replaces parameters; interval times as objects."""

    _sta_version: ClassVar[FrostVersions] = FrostVersions.v2
    _content_fields: ClassVar[frozenset[str]] = frozenset(
        {"phenomenonTime", "resultTime", "result", "validTime", "properties"}
    )
    properties: Optional[Dict[str, Any]] = None

    def _format_phenomenon_time(self, value: PhenomenonTime) -> Any:
        # STA 2.0: interval times are complex objects, not ``start/end`` strings.
        if isinstance(value, tuple):
            start, end = value
            return {
                "start": format_phenomenon_time(start),
                "end": format_phenomenon_time(end),
            }
        return format_phenomenon_time(value)

    def _format_valid_time(self, value: "TimePeriod") -> Any:
        return {
            "start": value.start.isoformat(),
            "end": value.end.isoformat(),
        }


class TimePeriod(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def check_valid_time(self) -> Self:
        if self.end < self.start:
            raise ValueError("End period before start period.")
        return self

UnLinkedSensorThingsObjects = Union[
    Thing,
    Location,
    Sensor,
    ObservedProperty,
    FeatureOfInterest,
    Feature,
    FeatureType,
]
LinkedSensorThingsObjects = Union[Datastream, Observation]

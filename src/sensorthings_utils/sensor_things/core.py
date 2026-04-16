"""
Pure OGC SensorThings dataclasses.
"""

# standard
from typing import Optional, Any, Dict, List, Literal, Tuple, Union
from typing_extensions import Annotated, Self
from datetime import datetime
from enum import Enum
# external
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
    computed_field,
)

# internal
SENSOR_THINGS_OBJECTS = [
    "sensors",
    "things",
    "locations",
    "datastreams",
    "observedProperties",
]

#TODO: split these into SensorThingSingleEntity and groups:
class SensorThingsEntity(Enum):
    """Single entities from the SensorThings information model."""
    SENSOR="Sensor"
    THING="Thing"
    LOCATION="Location"
    HISTORICALLOCATIONS="HistoricalLocation"
    DATASTREAM="Datastream"
    OBSERVATION="Observation"
    OBSERVEDPROPERTY="ObservedProperty"
    FEATUREOFINTEREST="FeatureOfInterest"

class SensorThingsEntityGroups(Enum):
    """Entity groups from the SensorThings information model."""
    SENSORS = "Sensors"
    THINGS = "Things"
    LOCATIONS = "Locations"
    HISTORICALLOCATIONS = "HistoricalLocations"
    DATASTREAMS = "Datastreams"
    OBSERVATIONS = "Observations"
    OBSERVEDPROPERTIES = "ObservedProperties"
    FEATURESOFINTEREST = "FeaturesOfInterest"

ENTITY_GROUPS_TO_ENTITIES: Dict[SensorThingsEntityGroups, SensorThingsEntity] = {
    SensorThingsEntityGroups.SENSORS: SensorThingsEntity.SENSOR,
    SensorThingsEntityGroups.THINGS: SensorThingsEntity.THING,
    SensorThingsEntityGroups.LOCATIONS: SensorThingsEntity.LOCATION,
    SensorThingsEntityGroups.HISTORICALLOCATIONS: SensorThingsEntity.HISTORICALLOCATIONS,
    SensorThingsEntityGroups.DATASTREAMS: SensorThingsEntity.DATASTREAM,
    SensorThingsEntityGroups.OBSERVATIONS: SensorThingsEntity.OBSERVATION,
    SensorThingsEntityGroups.OBSERVEDPROPERTIES: SensorThingsEntity.OBSERVEDPROPERTY,
    SensorThingsEntityGroups.FEATURESOFINTEREST: SensorThingsEntity.FEATUREOFINTEREST,
}

# all entities which require can exist WITHOUT an IOT link:

SENSOR_THINGS_ENTITY_FIELDS: Dict[
    SensorThingsEntity, Tuple[str, ...]
] = {
    SensorThingsEntity.THING: (
        "name",
        "description",
        "properties",
    ),
    SensorThingsEntity.LOCATION: (
        "name",
        "description",
        "encodingType",
        "location",
        "properties",
    ),
    SensorThingsEntity.SENSOR: (
        "name",
        "description",
        "encodingType",
        "metadata",
        "properties",
    ),
    SensorThingsEntity.FEATUREOFINTEREST: (
        "name",
        "description",
        "encodingType",
        "feature",
        "properties",
    ),
    SensorThingsEntity.OBSERVEDPROPERTY: (
        "name",
        "description",
        "definition",
        "properties",
    ),
}

# these are the multiciplity relations between SensorThings entities. For example
# a Thing can have HistoricalLocations, Locations and Datastreams:
SENSOR_THINGS_MULTIPLICITIES = {
        SensorThingsEntity.SENSOR:[
            SensorThingsEntityGroups.DATASTREAMS
            ],
        SensorThingsEntity.THING:[
            SensorThingsEntityGroups.HISTORICALLOCATIONS,
            SensorThingsEntityGroups.LOCATIONS,
            SensorThingsEntityGroups.DATASTREAMS
            ],
        SensorThingsEntity.LOCATION:[
            SensorThingsEntityGroups.HISTORICALLOCATIONS,
            SensorThingsEntityGroups.THINGS,
            ],
        SensorThingsEntity.HISTORICALLOCATIONS:[
            SensorThingsEntity.THING,
            SensorThingsEntityGroups.LOCATIONS
            ],
        SensorThingsEntity.DATASTREAM:[
            SensorThingsEntity.OBSERVEDPROPERTY,
            SensorThingsEntity.SENSOR,
            SensorThingsEntity.THING,
            SensorThingsEntityGroups.OBSERVATIONS
            ],
        SensorThingsEntity.OBSERVATION:[
            SensorThingsEntity.DATASTREAM,
            SensorThingsEntity.FEATUREOFINTEREST
            ],
        SensorThingsEntity.OBSERVEDPROPERTY:[
            SensorThingsEntityGroups.DATASTREAMS
            ],
        SensorThingsEntity.FEATUREOFINTEREST:[
            SensorThingsEntityGroups.OBSERVATIONS
            ]
        }


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
    iot_links: Dict[
        Literal["sensors", "things", "locations", "datastreams", "observedProperties"],
        List[str],
    ] = {}

    @computed_field
    @property
    def as_entity(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__).value
        return st_type 

    # TODO: #4 The state of iot_links as 'str' should be temporary or stored in another attribute.
    def __hash__(self) -> int:
        return hash((self.name, str(self.__class__)))

    def __repr__(self) -> str:
        return self.__repr_name__() + " (name=" + self.name + ")"

    def set_iot_link(
        self,
        entity: Literal[
            "sensors", "things", "locations", "datastreams", "observedProperties"
        ],
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
    iot_links: int | None = None
    resultTime: datetime | None = None
    validTime: "TimePeriod | None" = None

    @computed_field
    @property
    def as_entity(self) -> SensorThingsEntity:
        st_type = SensorThingsEntity(self.__class__.__name__).value
        return st_type 


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

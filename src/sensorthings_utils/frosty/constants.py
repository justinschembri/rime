"""Shared constants for FROST response/model mappings."""

from typing import Literal

from sensorthings_utils.sensor_things.core import (
    Datastream,
    Location,
    Observation,
    ObservedProperty,
    Sensor,
    Thing,
)

EntityName = Literal[
    "Datastreams",
    "Sensors",
    "Things",
    "Locations",
    "ObservedProperties",
    "Observations",
]

MODEL_FIELDS_MAP: dict[EntityName, list[str]] = {
    "Datastreams": list(Datastream.model_fields.keys()),
    "Sensors": list(Sensor.model_fields.keys()),
    "Things": list(Thing.model_fields.keys()),
    "Locations": list(Location.model_fields.keys()),
    "ObservedProperties": list(ObservedProperty.model_fields.keys()),
    "Observations": list(Observation.model_fields.keys()),
}

# Fields that are part of SensorThings response payloads but are not currently
# represented in local pydantic models.
EXTRA_STANDARD_FIELDS_MAP: dict[EntityName, list[str]] = {
    "Datastreams": ["observedArea", "phenomenonTime", "resultTime"],
    "Sensors": [],
    "Things": [],
    "Locations": [],
    "ObservedProperties": [],
    "Observations": [],
}

COMMON_IOT_FIELDS = ["@iot.selfLink", "@iot.id"]

NAVIGATION_HEADERS_MAP: dict[EntityName, list[str]] = {
    "Datastreams": [
        "ObservedProperty@iot.navigationLink",
        "Sensor@iot.navigationLink",
        "Thing@iot.navigationLink",
        "Observations@iot.navigationLink",
    ],
    "Sensors": ["Datastreams@iot.navigationLink"],
    "Things": [
        "HistoricalLocations@iot.navigationLink",
        "Locations@iot.navigationLink",
        "Datastreams@iot.navigationLink",
    ],
    "Locations": [
        "HistoricalLocations@iot.navigationLink",
        "Things@iot.navigationLink",
    ],
    "ObservedProperties": ["Datastreams@iot.navigationLink"],
    "Observations": [
        "Datastream@iot.navigationLink",
        "FeatureOfInterest@iot.navigationLink",
    ],
}

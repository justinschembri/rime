"""FROST server types."""
#standard
from typing import Iterator, Any
from enum import Enum

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


"""FROST server types."""
#standard
from enum import Enum
#internal
#external

class FrostVersions(Enum):
    v1 = "1"
    v1_1 = "1.1"

class FrostEndpoints(Enum):
    """FROST Server entity endpoints. Camelcase for conistency."""
    Datastreams = "/Datastreams"
    FeaturesOfInterest = "/FeaturesOfInterest"
    HistoricalLocations = "/HistoricalLocations"
    Locations = "/Locations"
    Observations = "/Observations"
    ObservedProperties = "/ObservedProperties"
    Sensors = "/Sensors"
    Things = "/Things"

class FrostParams(Enum):
    """FROST Server query params."""
    TOP="$top"
    SKIP="$skip"
    COUNT="$count"
    ORDER="$orderBy"
    EXPAND="$expand"
    SELECT="$select"
    FILTER="$filter"
    


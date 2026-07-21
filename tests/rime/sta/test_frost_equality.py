"""Unit tests for `from_frost_entity` + `partial_eq` on SensorThings models.

These are fully offline: they hand-craft the kind of JSON payloads a FROST
server emits (with `@iot.id`, `@iot.selfLink`, `*@iot.navigationLink`, and
server-computed fields) and check that the model constructors and the
content-only equality operator behave correctly.
"""
# standard
# external
import pytest

# internal
from rime_ingest.sta.core import (
    DatastreamV1,
    LocationV1,
    ObservationV1,
    ObservationV2,
    ObservedPropertyV1,
    SensorV1,
    ThingV1,
)


# --- from_frost_entity ----------------------------------------------------


class TestFromFrostEntity:
    def test_drops_iot_metadata_on_thing(self):
        payload = {
            "@iot.selfLink": "http://example/Things(7)",
            "@iot.id": 7,
            "name": "NWS03",
            "description": "Netatmo weather station",
            "properties": {"site": "test"},
            "Datastreams@iot.navigationLink": "http://example/Things(7)/Datastreams",
            "Locations@iot.navigationLink": "http://example/Things(7)/Locations",
            "HistoricalLocations@iot.navigationLink": "http://example/Things(7)/HistoricalLocations",
        }

        thing = ThingV1.from_frost_entity(payload)

        assert isinstance(thing, ThingV1)
        assert thing.id == 7
        assert thing.name == "NWS03"
        assert thing.description == "Netatmo weather station"
        assert thing.properties == {"site": "test"}

    def test_drops_iot_metadata_on_observation(self):
        payload = {
            "@iot.selfLink": "http://example/Observations(13)",
            "@iot.id": 13,
            "phenomenonTime": "2025-03-23T12:14:39Z",
            "resultTime": None,
            "result": 22.9,
            "Datastream@iot.navigationLink": "http://example/Observations(13)/Datastream",
            "FeatureOfInterest@iot.navigationLink": "http://example/Observations(13)/FeatureOfInterest",
        }

        obs = ObservationV1.from_frost_entity(payload)

        assert isinstance(obs, ObservationV1)
        assert obs.result == 22.9
        assert obs.phenomenonTime is not None
        assert obs.resultTime is None

    def test_ignores_server_computed_fields_on_datastream(self):
        # A real FROST Datastream payload carries `observedArea`,
        # `phenomenonTime` and `resultTime` that our Pydantic `Datastream`
        # does not declare. Those must be dropped silently, not raise.
        payload = {
            "@iot.selfLink": "http://example/Datastreams(1)",
            "@iot.id": 1,
            "name": "temperature",
            "description": "Ambient temperature",
            "observationType": "http://.../OM_Measurement",
            "unitOfMeasurement": {
                "name": "Celsius",
                "symbol": "C",
                "definition": "http://unitsofmeasure.org/ucum.html#para-30",
            },
            "properties": {},
            "observedArea": {"type": "Point", "coordinates": [4.37, 52.0]},
            "phenomenonTime": "2025-03-23T00:00:00Z/2025-03-23T23:59:00Z",
            "resultTime": "2025-03-23T00:00:00Z/2025-03-23T23:59:00Z",
            "Thing@iot.navigationLink": "http://example/Datastreams(1)/Thing",
            "Sensor@iot.navigationLink": "http://example/Datastreams(1)/Sensor",
            "ObservedProperty@iot.navigationLink": "http://example/Datastreams(1)/ObservedProperty",
            "Observations@iot.navigationLink": "http://example/Datastreams(1)/Observations",
        }

        ds = DatastreamV1.from_frost_entity(payload)

        assert isinstance(ds, DatastreamV1)
        assert ds.id == 1
        assert ds.name == "temperature"
        assert ds.observationType == "http://.../OM_Measurement"


# --- partial_eq -----------------------------------------------------------


class TestPartialEq:
    def test_ignores_links_and_id(self):
        a = ThingV1(
            name="NWS03",
            description="Netatmo weather station",
            properties={"site": "test"},
            id=1,
        )
        b = ThingV1(
            name="NWS03",
            description="Netatmo weather station",
            properties={"site": "test"},
            id=999,
        )
        # Different id; different (empty) links populated differently.
        assert a.partial_eq(b) is True
        # Full equality still differs because id differs.
        assert (a == b) is False

    def test_detects_content_change(self):
        a = ThingV1(name="NWS03", description="A")
        b = ThingV1(name="NWS04", description="A")
        assert a.partial_eq(b) is False

    def test_rejects_cross_type(self):
        thing = ThingV1(name="x", description="y")
        sensor = SensorV1(name="x", description="y", encodingType="text/html")
        assert thing.partial_eq(sensor) is False

    def test_handles_float_int_coords(self):
        # FROST serializes `52.0` as `52`. Local model carries floats.
        # Python dict equality treats `4.0 == 4` and `52.0 == 52` as True,
        # so these Locations must compare equal under partial_eq.
        declared = LocationV1(
            name="L",
            description="L",
            encodingType="application/geo+json",
            location={"type": "Point", "coordinates": [4.0, 52.0]},
        )
        from_server = LocationV1.from_frost_entity(
            {
                "@iot.id": 42,
                "@iot.selfLink": "http://example/Locations(42)",
                "name": "L",
                "description": "L",
                "encodingType": "application/geo+json",
                "location": {"type": "Point", "coordinates": [4, 52]},
            }
        )
        assert declared.partial_eq(from_server) is True

    def test_handles_missing_properties(self):
        # If the server omits `properties`, pydantic fills in the default
        # `{}`. A locally-declared Thing with `properties={}` must compare
        # equal to it under partial_eq.
        declared = ThingV1(name="T", description="d", properties={})
        from_server = ThingV1.from_frost_entity(
            {
                "@iot.id": 1,
                "@iot.selfLink": "http://example/Things(1)",
                "name": "T",
                "description": "d",
            }
        )
        assert declared.partial_eq(from_server) is True

    def test_observation_partial_eq(self):
        a = ObservationV1(phenomenonTime="2025-03-23T12:14:39Z", result=22.9)
        b = ObservationV1.from_frost_entity(
            {
                "@iot.id": 99,
                "@iot.selfLink": "http://example/Observations(99)",
                "phenomenonTime": "2025-03-23T12:14:39Z",
                "resultTime": None,
                "result": 22.9,
                "Datastream@iot.navigationLink": "http://example/Observations(99)/Datastream",
            }
        )
        assert a.partial_eq(b) is True

    def test_observation_partial_eq_detects_result_change(self):
        a = ObservationV1(phenomenonTime="2025-03-23T12:14:39Z", result=22.9)
        b = ObservationV1(phenomenonTime="2025-03-23T12:14:39Z", result=99.0)
        assert a.partial_eq(b) is False

    def test_v2_observation_from_frost_entity_instant_dict(self):
        """FROST v2 returns instants as ``{"start": "<iso>"}``."""
        payload = {
            "@id": "http://example/Observations(1)",
            "id": 1,
            "phenomenonTime": {"start": "2025-06-01T12:00:00Z"},
            "resultTime": None,
            "result": 42.0,
            "properties": None,
            "Datastream@navigationLink": "http://example/Observations(1)/Datastream",
        }
        obs = ObservationV2.from_frost_entity(payload)
        assert isinstance(obs, ObservationV2)
        assert obs.result == 42.0
        assert obs.phenomenonTime == "2025-06-01T12:00:00Z"

    def test_v2_observation_from_frost_entity_interval_dict(self):
        """FROST v2 returns intervals as ``{"start": ..., "end": ...}``."""
        payload = {
            "@id": "http://example/Observations(2)",
            "id": 2,
            "phenomenonTime": {
                "start": "2025-06-01T12:00:00Z",
                "end": "2025-06-01T12:05:00Z",
            },
            "resultTime": None,
            "result": [1, 2, 3],
            "properties": None,
        }
        obs = ObservationV2.from_frost_entity(payload)
        assert isinstance(obs, ObservationV2)
        assert isinstance(obs.phenomenonTime, tuple)
        assert len(obs.phenomenonTime) == 2

    def test_v2_observation_partial_eq_with_server_instant(self):
        """Local instant observation matches v2 server ``{"start": ...}`` form."""
        local = ObservationV2(
            result=22.9,
            phenomenonTime="2025-06-01T12:00:00Z",
        )
        from_server = ObservationV2.from_frost_entity(
            {
                "id": 1,
                "@id": "http://example/Observations(1)",
                "phenomenonTime": {"start": "2025-06-01T12:00:00Z"},
                "resultTime": None,
                "result": 22.9,
                "properties": None,
            }
        )
        assert local.partial_eq(from_server) is True

    def test_v2_observation_partial_eq_different_result(self):
        """Different results at the same time must not match."""
        local = ObservationV2(result=22.9, phenomenonTime="2025-06-01T12:00:00Z")
        from_server = ObservationV2.from_frost_entity(
            {
                "id": 1,
                "@id": "http://example/Observations(1)",
                "phenomenonTime": {"start": "2025-06-01T12:00:00Z"},
                "resultTime": None,
                "result": 99.0,
                "properties": None,
            }
        )
        assert local.partial_eq(from_server) is False

    def test_observation_partial_eq_normalises_datetime_phenomenon_time(self):
        from datetime import datetime, timezone

        local = ObservationV1(
            result=1.0,
            phenomenonTime=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        from_server = ObservationV1.from_frost_entity(
            {
                "@iot.id": 1,
                "@iot.selfLink": "http://example/Observations(1)",
                "phenomenonTime": "2025-01-01T00:00:00Z",
                "result": 1.0,
                "resultTime": None,
            }
        )
        assert local.partial_eq(from_server) is True


# --- ObservedProperty quick round-trip sanity check -----------------------


def test_observed_property_round_trip():
    payload = {
        "@iot.selfLink": "http://example/ObservedProperties(3)",
        "@iot.id": 3,
        "name": "Temperature",
        "description": "Ambient temperature",
        "definition": "http://dbpedia.org/page/Temperature",
        "properties": {},
        "Datastreams@iot.navigationLink": "http://example/ObservedProperties(3)/Datastreams",
    }
    op = ObservedPropertyV1.from_frost_entity(payload)
    local = ObservedPropertyV1(
        name="Temperature",
        description="Ambient temperature",
        definition="http://dbpedia.org/page/Temperature",
        properties={},
    )
    assert op.partial_eq(local) is True

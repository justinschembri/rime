"""Integration tests for `frost.get` against an ephemeral FROST stack.

The stack is spun up via `docker compose` from a session-scoped fixture in
`conftest.py` and seeded with a deterministic set of entities:

- 1 Thing (name="TEST-THING")
- 1 Location (name="TEST-LOCATION")
- 1 Sensor (name="TEST-SENSOR")
- 1 ObservedProperty (name="TEST-OBSPROP")
- 1 Datastream (name="TEST-DS")
- 10 Observations with `result = 1..10` at `2025-01-01..2025-01-10`

Because the dataset is small and fully controlled, these tests assert on
exact counts and values where possible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from datetime import datetime, timezone

from rime_ingest.frost.get import (
    frost_entity_lookup,
    frost_entity_lookup_pages,
    frost_object_lookup,
    general_frost_get,
    get_frost_datastream_observations,
)
from rime_ingest.frost.helpers import check_object_existence
from rime_ingest.frost.odata import ODataParams
from rime_ingest.sta.core import (
    DatastreamV1,
    LocationV1,
    ObservationV1,
    ObservedPropertyV1,
    SensorV1,
    ThingV1,
)
from rime_ingest.sta.schema import (
    SensorThingsEntityGroups,
)

if TYPE_CHECKING:
    # imported only for typing; tests are not a package so runtime import
    # of a sibling conftest would fail.
    from conftest import DockerFrost


pytestmark = [pytest.mark.docker, pytest.mark.slow]


def _datastream_id(frost: DockerFrost) -> int:
    """Return the `@iot.id` of the seeded TEST-DS datastream."""
    data = frost_entity_lookup(
        SensorThingsEntityGroups.DATASTREAMS,
        root_url=frost.root_url,
        version=frost.version,
        params={ODataParams.FILTER: "name eq 'TEST-DS'"},
    )
    assert data, "Seed datastream not found"
    return int(data[0]["@iot.id"])


class TestGeneralGet:
    def test_returns_dict_with_value(self, docker_frost: DockerFrost) -> None:
        url = f"{docker_frost.root_url}/{docker_frost.version}/Things"
        response = general_frost_get(url)

        assert isinstance(response, dict)
        assert isinstance(response.get("value"), list)


class TestFrostEntityLookupPages:
    def test_yields_list_of_dicts(self, docker_frost: DockerFrost) -> None:
        pages = list(
            frost_entity_lookup_pages(
                SensorThingsEntityGroups.THINGS,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
        )

        assert pages, "Expected at least one page of Things"
        assert all(isinstance(page, list) for page in pages)
        rows = [row for page in pages for row in page]
        names = {row["name"] for row in rows}
        # seed plants three top-level Things (primary, datastream-existence,
        # and no-properties) via deep insert; see SEED_* in conftest.py
        assert {
            "TEST-THING",
            "TEST-THING-DS2",
            "TEST-THING-NOPROPS",
        } <= names

    def test_pagination_observations(self, docker_frost: DockerFrost) -> None:
        """With 10 observations and `$top=3` we expect 4 pages (3+3+3+1)."""
        datastream_id = _datastream_id(docker_frost)

        pages = list(
            frost_entity_lookup_pages(
                SensorThingsEntityGroups.DATASTREAMS,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
                first_entity_id=datastream_id,
                second_entity=SensorThingsEntityGroups.OBSERVATIONS,
                params={ODataParams.TOP: 3},
            )
        )

        assert len(pages) >= 2, (
            "Expected FROST to paginate when $top < total rows"
        )
        total = sum(len(page) for page in pages)
        assert total == 10
        assert all(isinstance(page, list) for page in pages)
        assert all(isinstance(row, dict) for page in pages for row in page)

    def test_empty_filter_yields_no_pages(
        self, docker_frost: DockerFrost
    ) -> None:
        pages = frost_entity_lookup_pages(
            SensorThingsEntityGroups.THINGS,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            params={ODataParams.FILTER: "name eq '__nope__'"},
        )

        assert list(pages) == []


class TestFrostEntityLookup:
    def test_merges_pages(self, docker_frost: DockerFrost) -> None:
        datastream_id = _datastream_id(docker_frost)

        data = frost_entity_lookup(
            SensorThingsEntityGroups.DATASTREAMS,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            first_entity_id=datastream_id,
            second_entity=SensorThingsEntityGroups.OBSERVATIONS,
            params={ODataParams.TOP: 3},
        )

        assert data is not None
        assert len(data) == 10
        assert {row["result"] for row in data} == {float(n) for n in range(1, 11)}

    def test_no_match_returns_none(self, docker_frost: DockerFrost) -> None:
        data = frost_entity_lookup(
            SensorThingsEntityGroups.THINGS,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            params={ODataParams.FILTER: "name eq '__nope__'"},
        )

        assert data is None


class TestFrostObjectLookup:
    def test_lookup_thing_by_name(self, docker_frost: DockerFrost) -> None:
        thing = ThingV1(name="TEST-THING", description="ignored")

        data = frost_object_lookup(
            thing,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )

        assert data is not None
        assert len(data) == 1
        assert data[0]["name"] == "TEST-THING"

    def test_missing_thing(self, docker_frost: DockerFrost) -> None:
        thing = ThingV1(name="__nope__", description="x")

        data = frost_object_lookup(
            thing,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )

        assert data is None


class TestGetDatastreamObservations:
    def test_all_observations(self, docker_frost: DockerFrost) -> None:
        datastream_id = _datastream_id(docker_frost)

        observations = get_frost_datastream_observations(
            datastream_id=datastream_id,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )

        assert len(observations) == 10
        assert {row["result"] for row in observations} == {
            float(n) for n in range(1, 11)
        }

    def test_default_ordering_is_descending(
        self, docker_frost: DockerFrost
    ) -> None:
        """Default `descending=True` should reverse-sort by phenomenonTime."""
        datastream_id = _datastream_id(docker_frost)

        observations = get_frost_datastream_observations(
            datastream_id=datastream_id,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )

        phenomenon_times = [row["phenomenonTime"] for row in observations]
        assert phenomenon_times == sorted(phenomenon_times, reverse=True)

    def test_ascending_ordering(self, docker_frost: DockerFrost) -> None:
        datastream_id = _datastream_id(docker_frost)

        observations = get_frost_datastream_observations(
            datastream_id=datastream_id,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            descending=False,
        )

        phenomenon_times = [row["phenomenonTime"] for row in observations]
        assert phenomenon_times == sorted(phenomenon_times)

    def test_time_window(self, docker_frost: DockerFrost) -> None:
        datastream_id = _datastream_id(docker_frost)

        observations = get_frost_datastream_observations(
            datastream_id=datastream_id,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            time_start="2025-01-03T00:00:00Z",
            time_end="2025-01-05T00:00:00Z",
        )

        results = sorted(row["result"] for row in observations)
        assert results == [3.0, 4.0, 5.0]

    def test_result_range(self, docker_frost: DockerFrost) -> None:
        datastream_id = _datastream_id(docker_frost)

        observations = get_frost_datastream_observations(
            datastream_id=datastream_id,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            result_min=7,
            result_max=9,
        )

        results = sorted(row["result"] for row in observations)
        assert results == [7.0, 8.0, 9.0]

    def test_empty_window(self, docker_frost: DockerFrost) -> None:
        datastream_id = _datastream_id(docker_frost)

        observations = get_frost_datastream_observations(
            datastream_id=datastream_id,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            time_start="1900-01-01T00:00:00Z",
            time_end="1900-01-02T00:00:00Z",
        )

        assert observations == []


class TestCheckObjectExistence:
    def test_existing_thing_matches(self, docker_frost: DockerFrost) -> None:
        thing = ThingV1(
            name="TEST-THING",
            description="Ephemeral thing used by frost tests.",
            properties={"site": "test"},
        )

        assert (
            check_object_existence(
                thing,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_existing_location_matches(self, docker_frost: DockerFrost) -> None:
        location = LocationV1(
            name="TEST-LOCATION",
            description="Ephemeral location.",
            encodingType="application/geo+json",
            location={"type": "Point", "coordinates": [4.37, 52.37]},
        )

        assert (
            check_object_existence(
                location,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_existing_sensor_matches(self, docker_frost: DockerFrost) -> None:
        sensor = SensorV1(
            name="TEST-SENSOR",
            description="Ephemeral sensor.",
            encodingType="text/plain",
            metadata="none",
        )

        assert (
            check_object_existence(
                sensor,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_existing_observed_property_matches(
        self, docker_frost: DockerFrost
    ) -> None:
        observed_property = ObservedPropertyV1(
            name="TEST-OBSPROP",
            description="Ephemeral observed property.",
            definition="https://example.com/testprop",
        )

        assert (
            check_object_existence(
                observed_property,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_missing_thing_returns_false(
        self, docker_frost: DockerFrost
    ) -> None:
        thing = ThingV1(name="__nope__", description="x")

        assert (
            check_object_existence(
                thing,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is None
        )


class TestCheckDatastreamExistence:
    """Covers the `_check_datastream_object_exists` branch of
    `check_object_existence`, which dispatches on `isinstance(Datastream)`.
    """

    def _make_datastream(
        self, *, sensor_name: str, name: str = "TEST-DS"
    ) -> Datastream:
        sensor = SensorV1(
            name=sensor_name,
            description="linked sensor",
            encodingType="text/plain",
            metadata="none",
        )
        datastream = DatastreamV1(
            name=name,
            description="Ephemeral datastream.",
            observationType=(
                "http://www.opengis.net/def/observationType/"
                "OGC-OM/2.0/OM_Measurement"
            ),
            unitOfMeasurement={
                "name": "percent",
                "symbol": "%",
                "definition": "https://unitsofmeasure.org/ucum#para-29",
            },
        )
        datastream.iot_links = {SensorThingsEntityGroups.SENSORS: [sensor.name]}
        return datastream

    def test_matches_when_sensor_name_matches(
        self, docker_frost: DockerFrost
    ) -> None:
        datastream = self._make_datastream(sensor_name="TEST-SENSOR")

        assert (
            check_object_existence(
                datastream,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_no_match_when_sensor_name_differs(
        self, docker_frost: DockerFrost
    ) -> None:
        """Same datastream name, different linked sensor -> no match."""
        datastream = self._make_datastream(sensor_name="NOT-A-REAL-SENSOR")

        assert (
            check_object_existence(
                datastream,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is None
        )

    def test_missing_datastream_returns_false(
        self, docker_frost: DockerFrost
    ) -> None:
        datastream = self._make_datastream(
            sensor_name="TEST-SENSOR", name="__nope__"
        )

        assert (
            check_object_existence(
                datastream,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is None
        )


class TestCheckObservationExistence:
    """Covers the `_check_observation_object_exists` branch."""

    def test_matches_existing_phenomenon_time(
        self, docker_frost: DockerFrost
    ) -> None:
        observation = ObservationV1(
            result=1.0,
            phenomenonTime=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        assert (
            check_object_existence(
                observation,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_missing_phenomenon_time_returns_false(
        self, docker_frost: DockerFrost
    ) -> None:
        observation = ObservationV1(
            result=0,
            phenomenonTime=datetime(1900, 1, 1, tzinfo=timezone.utc),
        )

        assert (
            check_object_existence(
                observation,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is None
        )


class TestCheckObjectExistencePayloadQuirks:
    """Regression pins for FROST serialization quirks on unlinked objects.

    Exercises payload shapes that used to trip the old byte-for-byte JSON
    dump comparison in `_check_unlinked_object_exists` (missing
    `properties`, float/int coordinate mismatch). The current
    implementation compares via `partial_eq` on Pydantic models, so these
    must pass.
    """

    def test_thing_without_server_properties(
        self, docker_frost: DockerFrost
    ) -> None:
        thing = ThingV1(
            name="TEST-THING-NOPROPS",
            description="Thing seeded without properties.",
        )

        assert (
            check_object_existence(
                thing,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

    def test_location_with_integer_valued_coordinates(
        self, docker_frost: DockerFrost
    ) -> None:
        location = LocationV1(
            name="TEST-LOCATION-INTCOORD",
            description="Ephemeral location with .0 coords.",
            encodingType="application/geo+json",
            location={"type": "Point", "coordinates": [4.0, 52.0]},
        )

        assert (
            check_object_existence(
                location,
                root_url=docker_frost.root_url,
                version=docker_frost.version,
            )
            is not None
        )

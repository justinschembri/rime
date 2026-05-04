"""Read-only integration tests for `frost.get` against a live FROST server.

These tests target the TU Delft Multicare FROST instance. They are marked as
`real` and `online` and are automatically skipped if the server is
unreachable (see `conftest.multicare_root_url`).

The tests deliberately make **no assumptions about specific @iot.ids or
result values** beyond the known entity names (e.g. "TU Delft GDMC"), since
the underlying data evolves over time.
"""

from __future__ import annotations

import pytest

from rime.frost.get import (
    frost_entity_lookup,
    frost_entity_lookup_pages,
    frost_object_lookup,
    frost_object_lookup_pages,
    general_frost_get,
    get_frost_datastream_observations,
)
from rime.frost.helpers import check_object_existence
from rime.frost.types import FrostParams
from rime.sta.core import Thing
from rime.sta.schema import SensorThingsEntityGroups


pytestmark = [pytest.mark.real, pytest.mark.online]


# a stable Thing on the Multicare server used for lookup-by-name assertions
KNOWN_THING_NAME = "TU Delft GDMC"


class TestGeneralGet:
    def test_returns_dict_with_value(self, multicare_root_url: str) -> None:
        url = f"{multicare_root_url}/v1.1/Things"
        response = general_frost_get(url, {"$top": 1})

        assert isinstance(response, dict)
        assert "value" in response
        assert isinstance(response["value"], list)


class TestFrostEntityLookupPages:
    def test_first_page_is_list_of_dicts(self, multicare_root_url: str) -> None:
        """Regression guard: each yielded page must be a `list[dict]`.

        The `FrostResultPageIterator` alias was mis-typed as `Iterator[dict]`,
        causing downstream `extend(...)` calls to iterate dict keys instead
        of rows.
        """
        pages = frost_entity_lookup_pages(
            SensorThingsEntityGroups.THINGS,
            root_url=multicare_root_url,
            params={FrostParams.TOP: 1},
        )

        first = next(pages)

        assert isinstance(first, list)
        assert first, "Expected at least one Thing on Multicare FROST"
        assert isinstance(first[0], dict)
        assert "@iot.id" in first[0]

    def test_empty_result_yields_no_pages(self, multicare_root_url: str) -> None:
        pages = frost_entity_lookup_pages(
            SensorThingsEntityGroups.THINGS,
            root_url=multicare_root_url,
            params={FrostParams.FILTER: "name eq '__does_not_exist__'"},
        )

        assert list(pages) == []

    def test_pagination_yields_multiple_pages(
        self, multicare_root_url: str
    ) -> None:
        """Observations count is in the millions; `$top=2` forces paging."""
        pages = frost_entity_lookup_pages(
            SensorThingsEntityGroups.OBSERVATIONS,
            root_url=multicare_root_url,
            params={
                FrostParams.TOP: 2,
                FrostParams.SELECT: "@iot.id",
            },
        )

        collected: list[list[dict]] = []
        for page in pages:
            assert isinstance(page, list)
            assert all(isinstance(row, dict) for row in page)
            collected.append(page)
            if len(collected) >= 3:
                break

        assert len(collected) >= 2, (
            "Expected multiple pages when $top=2 against a huge table"
        )


class TestFrostEntityLookup:
    def test_returns_merged_list(self, multicare_root_url: str) -> None:
        data = frost_entity_lookup(
            SensorThingsEntityGroups.THINGS,
            root_url=multicare_root_url,
            params={FrostParams.TOP: 2},
        )

        assert isinstance(data, list)
        assert data
        assert all(isinstance(row, dict) for row in data)
        assert all("@iot.id" in row for row in data)
        assert len(data) >= 3, "Expected pagination to merge at least 3 Things"

    def test_nested_entity(self, multicare_root_url: str) -> None:
        """`Things(1)/Datastreams` should be reachable and non-empty."""
        data = frost_entity_lookup(
            SensorThingsEntityGroups.THINGS,
            root_url=multicare_root_url,
            first_entity_id=1,
            second_entity=SensorThingsEntityGroups.DATASTREAMS,
        )

        assert isinstance(data, list)
        assert data
        assert all("@iot.id" in row for row in data)

    def test_no_match_returns_none(self, multicare_root_url: str) -> None:
        data = frost_entity_lookup(
            SensorThingsEntityGroups.THINGS,
            root_url=multicare_root_url,
            params={FrostParams.FILTER: "name eq '__does_not_exist__'"},
        )

        assert data is None


class TestFrostObjectLookup:
    def test_matches_existing_thing_by_name(
        self, multicare_root_url: str
    ) -> None:
        thing = Thing(name=KNOWN_THING_NAME, description="ignored by lookup")

        pages = list(
            frost_object_lookup_pages(thing, root_url=multicare_root_url)
        )
        merged = frost_object_lookup(thing, root_url=multicare_root_url)

        assert pages, "Expected at least one page"
        assert all(isinstance(page, list) for page in pages)

        assert merged is not None
        assert len(merged) == 1
        assert merged[0]["name"] == KNOWN_THING_NAME

    def test_missing_thing_returns_none(self, multicare_root_url: str) -> None:
        thing = Thing(name="__does_not_exist__", description="x")

        merged = frost_object_lookup(thing, root_url=multicare_root_url)

        assert merged is None


class TestGetDatastreamObservations:
    def test_time_window_yields_rows(self, multicare_root_url: str) -> None:
        """A tight time window should return a bounded, non-empty result.

        Datastream(1) on Multicare has been receiving data since
        2025-03-23T12:14:39Z, so this window is expected to match a few
        observations without pulling the full ~96k-row dataset.
        """
        observations = get_frost_datastream_observations(
            datastream_id=1,
            root_url=multicare_root_url,
            time_start="2025-03-23T12:14:00Z",
            time_end="2025-03-23T13:00:00Z",
        )

        assert isinstance(observations, list)
        assert observations
        assert all(isinstance(row, dict) for row in observations)
        # default $select includes these fields:
        expected_fields = {"@iot.id", "phenomenonTime", "result"}
        assert expected_fields.issubset(observations[0].keys())

    def test_impossible_filter_returns_empty(
        self, multicare_root_url: str
    ) -> None:
        observations = get_frost_datastream_observations(
            datastream_id=1,
            root_url=multicare_root_url,
            time_start="1900-01-01T00:00:00Z",
            time_end="1900-01-02T00:00:00Z",
        )

        assert observations == []


class TestCheckObjectExistence:
    def test_missing_thing_returns_false(
        self, multicare_root_url: str
    ) -> None:
        thing = Thing(name="__does_not_exist__", description="x")

        assert (
            check_object_existence(thing, root_url=multicare_root_url)
            is None
        )

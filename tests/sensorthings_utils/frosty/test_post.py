"""Integration tests for `frosty.post` against an ephemeral FROST stack.

These tests mirror the manual sanity checks we used during refactor work:
posting equivalent Thing payloads as (1) JSON string, (2) dict, and
(3) SensorThingsObject should all succeed and return a `Location` URL.
"""
from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import pytest
import requests

from sensorthings_utils.frosty.post import general_post, make_frost_entity
from sensorthings_utils.sensor_things.core import Thing

if TYPE_CHECKING:
    from conftest import DockerFrost

pytestmark = [pytest.mark.docker, pytest.mark.slow]


def _assert_created_thing(location: str, expected_name: str) -> None:
    assert "/Things(" in location
    response = requests.get(location, timeout=10)
    response.raise_for_status()
    assert response.json()["name"] == expected_name


class TestPostViaDockerFrost:
    def test_general_post_accepts_str_dict_and_object_payloads(
        self, docker_frost: DockerFrost
    ) -> None:
        url = f"{docker_frost.root_url}/{docker_frost.version}/Things"
        name_str = f"TEST-POST-STR-{uuid.uuid4().hex[:12]}"
        name_dict = f"TEST-POST-DICT-{uuid.uuid4().hex[:12]}"
        name_object = f"TEST-POST-OBJECT-{uuid.uuid4().hex[:12]}"

        payload_str = json.dumps(
            {
                "name": name_str,
                "description": "Created by general_post with str payload.",
                "properties": {"oven": True, "heatingPlates": 4},
            }
        )
        payload_dict = {
            "name": name_dict,
            "description": "Created by general_post with dict payload.",
            "properties": {"oven": True, "heatingPlates": 4},
        }
        payload_object = Thing(
            name=name_object,
            description="Created by general_post with object payload.",
            properties={"oven": True, "heatingPlates": 4},
        )

        payloads = [
            ("str", payload_str, name_str),
            ("dict", payload_dict, name_dict),
            ("object", payload_object, name_object),
        ]

        for label, payload, expected_name in payloads:
            location = general_post(url, payload)
            assert isinstance(location, str), f"{label} payload should return Location str"
            _assert_created_thing(location, expected_name)

    def test_make_frost_entity_creates_then_skips_same_thing(
        self, docker_frost: DockerFrost
    ) -> None:
        name = f"TEST-POST-IDEM-{uuid.uuid4().hex[:12]}"
        thing = Thing(
            name=name,
            description="Idempotence check for make_frost_entity.",
        )
        first = make_frost_entity(
            thing,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )
        assert first is not None

        second = make_frost_entity(
            thing,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )
        assert second is None

"""Integration tests for `sensorthings_utils.frosty.post` against the ephemeral FROST stack.

Uses the same `docker_frost` session fixture as `test_get_docker.py` (see conftest).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import requests

from sensorthings_utils.frosty.get import frost_entity_lookup
from sensorthings_utils.frosty.post import general_post, make_frost_entity
from sensorthings_utils.frosty.types import FrostParams
from sensorthings_utils.sensor_things.core import Thing
from sensorthings_utils.sensor_things.schema import SensorThingsEntityGroups

if TYPE_CHECKING:
    from conftest import DockerFrost

pytestmark = [pytest.mark.docker, pytest.mark.slow]


class TestPostViaDockerFrost:
    def test_make_frost_entity_creates_thing_and_returns_location(
        self, docker_frost: DockerFrost
    ) -> None:
        name = f"TEST-POST-THING-{uuid.uuid4().hex[:12]}"
        thing = Thing(
            name=name,
            description="Ephemeral create via make_frost_entity in docker test.",
        )
        loc = make_frost_entity(
            thing,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
        )
        assert loc is not None
        assert f"/Things(" in loc

        data = frost_entity_lookup(
            SensorThingsEntityGroups.THINGS,
            root_url=docker_frost.root_url,
            version=docker_frost.version,
            params={FrostParams.FILTER: f"name eq '{name}'"},
        )
        assert data is not None
        assert len(data) == 1
        assert data[0]["name"] == name

    def test_make_frost_entity_idempotent_skips_second_create(
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

    def test_general_post_raw_json_creates_thing(
        self, docker_frost: DockerFrost
    ) -> None:
        name = f"TEST-POST-RAW-{uuid.uuid4().hex[:12]}"
        url = f"{docker_frost.root_url}/{docker_frost.version}/Things"
        payload: dict = {
            "name": name,
            "description": "Created by general_post raw JSON in docker test.",
        }
        response = general_post(
            url,
            payload,
        )
        assert response.status_code in (200, 201)
        loc = response.headers.get("Location")
        assert loc
        r2 = requests.get(loc, timeout=10)
        r2.raise_for_status()
        assert r2.json()["name"] == name

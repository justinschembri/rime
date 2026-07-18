"""Unit tests for FROST URL composition contracts.

These tests protect the boundary between:
- `get.find_datastream_observations_url` (returns Datastream parent URL)
- `post.make_frost_entity` (appends entity collection segment)

Together they prevent regressions where Observation POST URLs become
`.../Observations/Observations`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from rime_ingest.frost.get import find_datastream_observations_url
from rime_ingest.frost.post import make_frost_entity
from rime_ingest.frost.types import FrostEntityRef
from rime_ingest.sta.core import ObservationV1 as Observation


def test_find_datastream_observations_url_returns_datastream_parent(monkeypatch):
    """Lookup returns Datastream URL, not Observations navigation URL."""

    def fake_lookup(*, first_entity, first_entity_id=None, **kwargs):
        # First call: sensor lookup by name.
        if first_entity_id is None:
            return [{"@iot.id": 42}]
        # Second call: datastream lookup under sensor.
        return [
            {
                "@iot.id": 7,
                "@iot.selfLink": (
                    "http://localhost:8080/FROST-Server/v1.1/Datastreams(7)"
                ),
                "Observations@iot.navigationLink": (
                    "http://localhost:8080/FROST-Server/v1.1/"
                    "Datastreams(7)/Observations"
                ),
            }
        ]

    monkeypatch.setattr("rime_ingest.frost.get.frost_entity_lookup", fake_lookup)

    out = find_datastream_observations_url(
        sensor_name="sensor-1",
        datastream_name="temperature_indoor",
        root_url="http://web:8080/FROST-Server",
        version="1.1",
    )
    assert out == "http://web:8080/FROST-Server/v1.1/Datastreams(7)"


def test_make_frost_entity_observation_endpoint_appends_once(monkeypatch):
    """Observation POST target is `<Datastream>/Observations` exactly once."""
    captured: dict[str, str] = {}

    def fake_exists(*args, **kwargs):
        return None

    def fake_post(url, payload, **kwargs):
        captured["url"] = url
        return FrostEntityRef.from_frost_url(
            "http://web:8080/FROST-Server/v1.1/Observations(123)"
        )

    monkeypatch.setattr("rime_ingest.frost.post.check_object_existence", fake_exists)
    monkeypatch.setattr("rime_ingest.frost.post.general_post", fake_post)

    obs = Observation(result=21.3, phenomenonTime=datetime.now(UTC))
    ref = make_frost_entity(
        obs,
        root_url="http://web:8080/FROST-Server",
        version="1.1",
        endpoint="http://web:8080/FROST-Server/v1.1/Datastreams(7)",
    )

    assert isinstance(ref, FrostEntityRef)
    assert (
        captured["url"]
        == "http://web:8080/FROST-Server/v1.1/Datastreams(7)/Observations"
    )

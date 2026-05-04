"""Observation upload flows against ``rime.frost.post``."""
# stdlib
from datetime import datetime
# external
import pytest

from rime.frost.post import general_post, make_frost_entity

from rime.sta.core import Observation


@pytest.fixture
def valid_observation() -> Observation:
    return Observation(
        result=100,
        phenomenonTime=datetime(year=2025, month=1, day=1),
    )


def test_frost_post_entrypoints_importable() -> None:
    assert callable(make_frost_entity)
    assert callable(general_post)


def test_double_observation(valid_observation: Observation) -> None:
    """Placeholder: two identical observation POSTs — needs FROST base URL + seed."""
    pytest.skip(
        "Implement with docker_frost (or POST fixture): "
        "call make_frost_entity / general_post twice and assert behaviour."
    )

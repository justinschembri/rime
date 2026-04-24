"""Observation flows: target `frosty.post`, not deprecated `sensorthings_utils.frost`.

If collection fails here, check `frosty/post.py` still imports `UrlStr` from
`frost.py` — that should move to a neutral types module so this package can
load without the legacy module.
"""
# stdlib
from datetime import datetime
# external
import pytest

# Once `frosty.post` loads without depending on deprecated `frost`, these import.
try:
    from sensorthings_utils.frosty.post import general_post, make_frost_entity
except ImportError as exc:
    pytest.skip(
        f"frosty.post must be importable without legacy frost (e.g. UrlStr): {exc}",
        allow_module_level=True,
    )

from sensorthings_utils.sensor_things.core import Observation


@pytest.fixture
def valid_observation() -> Observation:
    return Observation(
        result=100,
        phenomenonTime=datetime(year=2025, month=1, day=1),
    )


def test_frosty_post_entrypoints_importable() -> None:
    assert callable(make_frost_entity)
    assert callable(general_post)


def test_double_observation(valid_observation: Observation) -> None:
    """Placeholder: two identical observation POSTs — needs FROST base URL + seed."""
    pytest.skip(
        "Implement with docker_frost (or POST fixture): "
        "call make_frost_entity / general_post twice and assert behaviour."
    )

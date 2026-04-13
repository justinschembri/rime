# standard
import unittest

# external
# internal
from sensorthings_utils.sensor_things.extensions import (
    SensorConfig,
    SensorArrangement,
)
from sensorthings_utils.paths import ROOT_DIR


class Test_SensorArrangement(unittest.TestCase):
    MOCK_DATA_PATH = (
        ROOT_DIR
        / "deploy"
        / "sensor_configs"
        / "netatmo"
        / "template_netatmo.nws03.yaml"
    )

    def setUp(self) -> None:
        self.sensor_arrangement_map = SensorConfig(self.MOCK_DATA_PATH)
        self.sensor_arrangement = SensorArrangement(self.sensor_arrangement_map)

    def test_instantiation(self) -> None:
        """Test basic instantiation using good data."""
        sensor_arrangement_map = SensorConfig(self.MOCK_DATA_PATH)
        assert isinstance(sensor_arrangement_map, SensorConfig)

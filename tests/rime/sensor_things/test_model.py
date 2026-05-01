# standard
import unittest

# internal
from rime.sensor_things.extensions import SensorConfig
from rime.paths import ROOT_DIR


class TestSensorConfig(unittest.TestCase):
    MOCK_DATA_PATH = (
        ROOT_DIR
        / "deploy"
        / "sensor_configs"
        / "netatmo"
        / "template_netatmo.nws03.yaml"
    )

    def test_instantiation(self) -> None:
        """SensorConfig loads and parses a valid YAML config without raising."""
        sensor_config = SensorConfig(self.MOCK_DATA_PATH)
        assert isinstance(sensor_config, SensorConfig)

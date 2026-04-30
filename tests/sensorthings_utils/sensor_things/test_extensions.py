"""Test sensor_things/extensions.py"""

# standard
from pathlib import Path

# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig

TEST_DATA_DIR = Path(__file__).parent / "data"
GOOD_CONFIG_FILE = TEST_DATA_DIR / "valid_sensor_config.yaml"
EMPTY_IOT_LINK_CONFIG_FILE = TEST_DATA_DIR / "empty_iot_link_sensor_config.yaml"


class TestSensorConfig:
    """Test the SensorConfig class."""

    def test_good_config_validates(self):
        good_config = SensorConfig(GOOD_CONFIG_FILE)
        assert good_config.check_validity()[0] is True
        assert good_config.is_valid is True

    def test_empty_iot_link_invalid(self):
        bad_config = SensorConfig(EMPTY_IOT_LINK_CONFIG_FILE)
        assert bad_config.is_valid is False

    def test_ingestion_sets_model_and_name_metadata(self):
        good_config = SensorConfig(GOOD_CONFIG_FILE)
        assert good_config.model.value == "netatmo.nws03"
        assert good_config.name == "sensor-001"

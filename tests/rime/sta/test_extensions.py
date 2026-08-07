"""Test sta/extensions.py"""

# standard
from pathlib import Path

# internal
from rime_ingest.sta.extensions import SensorConfig
from rime_ingest.transformers.types import CanonicalDatastreams, SupportedSensors

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

    def test_ingestion_sets_sensors_registry_metadata(self):
        good_config = SensorConfig(GOOD_CONFIG_FILE)
        assert set(good_config.sensors) == {"sensor-001"}
        entry = good_config.sensors["sensor-001"]
        assert entry.model == SupportedSensors.NETATMO_NWS03
        assert entry.datastreams == (CanonicalDatastreams.TEMP_IN,)
        assert good_config.thing_name == "room-120"

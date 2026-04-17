"""Test sensor_things/extensions.py"""

# standard
from pathlib import Path
from copy import deepcopy

# external
import yaml
import pytest
# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig, SensorArrangement

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

    def test_ingestion_resolves_links_to_object_refs(self):
        arrangement = SensorArrangement(SensorConfig(GOOD_CONFIG_FILE))

        sensor = arrangement.get("Sensor", instance="sensor-001")
        datastream = arrangement.get("Datastream", instance="temperature_indoor")
        thing = arrangement.get("Thing", instance="room-120")
        location = arrangement.get("Location", instance="loc-120")
        observed_property = arrangement.get("ObservedProperty", instance="indoor_temperature")

        assert sensor.iot_links["datastreams"][0] is datastream
        assert datastream.iot_links["sensors"][0] is sensor
        assert datastream.iot_links["things"][0] is thing
        assert datastream.iot_links["observedProperties"][0] is observed_property
        assert thing.iot_links["locations"][0] is location
        assert location.iot_links["things"][0] is thing

    def test_guardrail_missing_link_target_raises_keyerror(self, tmp_path):
        with open(GOOD_CONFIG_FILE, "r") as f:
            config_data = yaml.safe_load(f)

        bad_data = deepcopy(config_data)
        bad_data["sensors"]["netatmo.nws03"]["iot_links"]["datastreams"] = [
            "does_not_exist"
        ]

        bad_config_path = tmp_path / "bad_missing_link_target.yaml"
        with open(bad_config_path, "w") as f:
            yaml.safe_dump(bad_data, f, sort_keys=False)

        with pytest.raises(KeyError):
            SensorArrangement(SensorConfig(bad_config_path))

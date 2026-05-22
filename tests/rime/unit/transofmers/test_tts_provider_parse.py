"""Test TTS provider payload decapsulation (TTN envelope → DecapsulatedMessage)."""
from datetime import datetime, timezone
from typing import Any

import pytest

from rime.providers.tts import TTSProvider
from rime.transformers.decapsulators.types import DecapsulatedMessage, IdentifiedPayload


class TestTTSProviderPayload:
    """Test TTN ingest via TTSProvider._decapsulate_wire."""

    @pytest.fixture
    def valid_payload(self) -> dict[str, Any]:
        """Fixture providing a valid TTS payload."""
        return {
            "end_device_ids": {
                "device_id": "ieq-thcpvl-001",
                "application_ids": {"application_id": "multicare-acerra"},
                "dev_eui": "24E124707D378803",
                "join_eui": "24E124C0002A0001",
                "dev_addr": "260B7A49",
            },
            "correlation_ids": ["gs:uplink:01KDBJ076FC6J8N818Z0GTG7VH"],
            "received_at": "2025-12-25T20:08:01.180377996Z",
            "uplink_message": {
                "session_key_id": "AZrtIhr44TiNGAgGyNKXbw==",
                "f_port": 85,
                "f_cnt": 4016,
                "frm_payload": "A2fnAARolwUAAAbLAQd9ORIIfWQACXO/Jwt9ZQAMfWsAAXU1",
                "decoded_payload": {
                    "battery": 53,
                    "co2": 4665,
                    "humidity": 75.5,
                    "light_level": 1,
                    "pir": "idle",
                    "pm10": 107,
                    "pm2_5": 101,
                    "pressure": 1017.5,
                    "temperature": 23.1,
                    "tvoc": 1,
                },
                "time": "2025-12-25T20:08:00.920247Z",
                "rx_metadata": [
                    {
                        "gateway_ids": {
                            "gateway_id": "multicare-gateway-03",
                            "eui": "A84041FFFF2A9A12",
                        },
                        "time": "2025-12-25T20:08:00.920247Z",
                        "timestamp": 2193199502,
                        "rssi": -72,
                        "channel_rssi": -72,
                        "snr": 11,
                        "frequency_offset": "-22",
                        "uplink_token": "CiIKIAoUbXVsdGljYXJlLWdhdGV3YXktMDMSCKhAQf//KpoSEI6j5pUIGgwIoLO2ygYQ5IuB0AMgsKWCp+q2Aw==",
                        "channel_index": 5,
                        "received_at": "2025-12-25T20:08:00.937463873Z",
                    }
                ],
                "settings": {
                    "data_rate": {
                        "lora": {
                            "bandwidth": 125000,
                            "spreading_factor": 7,
                            "coding_rate": "4/5",
                        }
                    },
                    "frequency": "867500000",
                    "timestamp": 2193199502,
                    "time": "2025-12-25T20:08:00.920247Z",
                },
                "received_at": "2025-12-25T20:08:00.975695414Z",
                "consumed_airtime": "0.097536s",
                "version_ids": {
                    "brand_id": "milesight-iot",
                    "model_id": "am308l",
                    "hardware_version": "1.x",
                    "firmware_version": "1.x",
                    "band_id": "EU_863_870",
                },
                "network_ids": {
                    "net_id": "000013",
                    "ns_id": "EC656E0000000181",
                    "tenant_id": "ttn",
                    "cluster_id": "eu1",
                    "cluster_address": "eu1.cloud.thethings.network",
                },
                "last_battery_percentage": {
                    "f_cnt": 3908,
                    "value": 52.569168,
                    "received_at": "2025-12-25T07:09:14.353301178Z",
                },
            },
        }

    def test_decapsulate_returns_single_message(self, valid_payload):
        provider = TTSProvider(
            "test-app",
            host="eu1.cloud.thethings.network",
            topic="v3/test-app@ttn/devices/+/up",
        )
        decapped = provider._decapsulate_wire(valid_payload)

        assert isinstance(decapped, DecapsulatedMessage)
        assert len(decapped.sensor_payloads) == 1

    def test_identified_payload_sensor_uuid(self, valid_payload):
        provider = TTSProvider(
            "test-app",
            host="eu1.cloud.thethings.network",
            topic="v3/test-app@ttn/devices/+/up",
        )
        decapped = provider._decapsulate_wire(valid_payload)
        identified = decapped.sensor_payloads[0]

        assert isinstance(identified, IdentifiedPayload)
        assert identified.sensor_uuid == "24E124707D378803"

    def test_sensor_payload_contents(self, valid_payload):
        provider = TTSProvider(
            "test-app",
            host="eu1.cloud.thethings.network",
            topic="v3/test-app@ttn/devices/+/up",
        )
        decapped = provider._decapsulate_wire(valid_payload)
        sensor_data = decapped.sensor_payloads[0].payload

        assert sensor_data["battery"] == 53
        assert sensor_data["co2"] == 4665
        assert sensor_data["humidity"] == 75.5
        assert sensor_data["light_level"] == 1
        assert sensor_data["pir"] == "idle"
        assert sensor_data["pm10"] == 107
        assert sensor_data["pm2_5"] == 101
        assert sensor_data["pressure"] == 1017.5
        assert sensor_data["temperature"] == 23.1
        assert sensor_data["tvoc"] == 1

    def test_envelope_timestamps(self, valid_payload):
        provider = TTSProvider(
            "test-app",
            host="eu1.cloud.thethings.network",
            topic="v3/test-app@ttn/devices/+/up",
        )
        decapped = provider._decapsulate_wire(valid_payload)
        env = decapped.envelope_metadata

        assert env is not None
        assert env.provider_timestamp == datetime(
            2025, 12, 25, 20, 8, 0, 937463, tzinfo=timezone.utc
        )
        assert env.phenomenon_timestamp == datetime(
            2025, 12, 25, 20, 8, 0, 920247, tzinfo=timezone.utc
        )

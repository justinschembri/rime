"""Test concrete implementations in connections package."""

# standard
import json
from pathlib import Path
import time
import logging
import threading
# external
import pytest
# internal
from rime_ingest.providers import TTSProvider

debug_logger = logging.getLogger(__name__)
debug_logger.setLevel(logging.DEBUG)


@pytest.fixture
def bad_tts_credentials(tmp_path: Path) -> Path:
    path = tmp_path / "./bad_tts_credentials"
    bad_tokens = {"tts-mock-application": {"api_key": "foo"}}
    path.write_text(json.dumps(bad_tokens))
    return path


@pytest.fixture
def valid_tts_connection() -> TTSProvider:
    """A valid TTS provider with real credentials."""
    application_name = "multicare-acerra@ttn"
    return TTSProvider(
            application_name,
            "eu1.cloud.thethings.network",
            f"v3/{application_name}/devices/+/up",
            )


class TestTTSProviderAuthentication:
    """
    Tests the TTSProvider's basic auth process.

    Testing Strategy:
        - *Authentication* as implemented in `_auth()`:
            - good tokens,
            - bad tokens,
            - no tokens,
    """
    @pytest.mark.online
    def test_auth_good_tokens(self, valid_tts_connection: TTSProvider):
        """Happy path testing: good tokens should connect successfully."""
        connection_succeeded = threading.Event()

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                connection_succeeded.set()

        valid_tts_connection._auth()
        valid_tts_connection._mqtt_client.on_connect = on_connect
        valid_tts_connection._mqtt_client.connect(
            valid_tts_connection.host,
            valid_tts_connection.port
        )
        valid_tts_connection._mqtt_client.loop_start()

        assert connection_succeeded.wait(timeout=5), "Failed to connect within 5 seconds"
        assert valid_tts_connection._mqtt_client.is_connected()

        valid_tts_connection._mqtt_client.loop_stop()
        valid_tts_connection._mqtt_client.disconnect()

    @pytest.mark.online
    def test_bad_creds(self, bad_tts_credentials, valid_tts_connection, monkeypatch):
        """Passing bad creds should fail to connect."""
        connection_failed = threading.Event()
        connection_succeeded = threading.Event()

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                connection_succeeded.set()
            else:
                connection_failed.set()

        invalid_connection = TTSProvider(
            "tts-mock-application",
            host=valid_tts_connection.host,
            topic=valid_tts_connection.topic,
            port=valid_tts_connection.port,
        )
        # override credential file resolution for the test
        monkeypatch.setattr(
            type(invalid_connection),
            "_credentials_file",
            property(lambda self: bad_tts_credentials),
        )

        invalid_connection._auth()
        invalid_connection._mqtt_client.on_connect = on_connect
        invalid_connection._mqtt_client.connect(
            valid_tts_connection.host,
            valid_tts_connection.port
        )
        invalid_connection._mqtt_client.loop_start()

        time.sleep(3)

        assert connection_failed.is_set(), "Expected connection to fail with bad credentials"
        assert not connection_succeeded.is_set()
        assert not invalid_connection._mqtt_client.is_connected()

        invalid_connection._mqtt_client.loop_stop()
        invalid_connection._mqtt_client.disconnect()

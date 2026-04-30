"""Test concrete implementations in connections package."""

# standard
import json
from pathlib import Path
# external
import lnetatmo
import pytest
# internal
from sensorthings_utils.providers import NetatmoProvider


@pytest.fixture
def bad_netatmo_tokens(tmp_path: Path) -> Path:
    path = tmp_path / "./bad_netatmo_tokens"
    bad_tokens = {
            "client_id": "foo",
            "client_secret":"bar",
            "refresh_token":"foobar"
        }
    path.write_text(json.dumps(bad_tokens))
    return path


@pytest.fixture
def valid_netatmo_connection() -> NetatmoProvider:
    """A valid Netatmo provider with good tokens."""
    return NetatmoProvider("netatmo-test-application")


class TestNetatmoProviderAuthentication:
    """
    Tests the NetatmoProvider's basic auth process.

    Testing Strategy:
        - *Authentication* as implemented in `_auth()`:
            - good tokens,
            - bad tokens,
            - no tokens,
    """
    @pytest.mark.real
    @pytest.mark.online
    def test_auth_good_tokens(self, valid_netatmo_connection: NetatmoProvider):
        """Happy path testing: good tokens should return a ClientAuth object."""
        assert isinstance(valid_netatmo_connection._auth(), lnetatmo.ClientAuth)

    def test_bad_tokens(self, bad_netatmo_tokens, monkeypatch):
        """Passing bad tokens via patched token file path."""
        netatmo_provider = NetatmoProvider("netatmo-test-application")
        # override the resolved token file path for the test
        monkeypatch.setattr(
            type(netatmo_provider),
            "_token_file",
            property(lambda self: bad_netatmo_tokens),
        )
        assert isinstance(netatmo_provider._auth(), lnetatmo.ClientAuth)

    def test_missing_app_name(self):
        """Constructor requires an app_name."""
        with pytest.raises(TypeError):
            NetatmoProvider()  # type: ignore


class TestNetatmoPulling:
    """
    Tests the actual data pulling. Requires valid tokens!

    Valid netatmo tokens needed at:
        `/deployment/secrets/tokens/netatmo-test-application.json`

    Testing Strategy:
        - *Pulling* as implemented in `_pull_data()`:
            - basic data arrival, type and structure
    """
    @pytest.mark.real
    def test_basic_pulling(self, valid_netatmo_connection: NetatmoProvider):
        """Happy path testing: data should arrive, check structure too."""
        application_payload = valid_netatmo_connection._pull_data()
        assert application_payload is not None
        assert isinstance(application_payload, list)

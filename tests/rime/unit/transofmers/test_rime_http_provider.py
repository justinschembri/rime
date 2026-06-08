"""Unit tests for RimeServerHttpProvider.

All HTTP calls are intercepted with unittest.mock so no server is needed.
"""

from __future__ import annotations

import base64
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rime_ingest.providers.rime_http import RimeServerHttpProvider
from rime_ingest.transformers.decapsulators.rime_http import DrainedEnvelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    tmp_path: Path,
    server_url: str = "http://localhost:8080",
) -> RimeServerHttpProvider:
    """Return a provider backed by a temp credentials file."""
    creds = {
        "test-app": {"egress_token": "secret-token"}
    }
    creds_file = tmp_path / "application_credentials.json"
    creds_file.write_text(json.dumps(creds))

    p = RimeServerHttpProvider("test-app", server_url=server_url)
    # Patch CREDENTIALS_DIR to the temp path
    with patch.object(type(p), "_credentials_file", new_callable=lambda: property(lambda self: creds_file)):
        p._auth()
    return p


def _drain_message(
    id: str = "msg-1",
    body: bytes = b"hello",
    content_type: str = "application/octet-stream",
    received_at: str = "2026-06-08T10:00:00Z",
    message_id: str | None = None,
    emitted_at: str | None = None,
) -> dict:
    return {
        "id": id,
        "body": base64.b64encode(body).decode(),
        "content_type": content_type,
        "received_at": received_at,
        "message_id": message_id,
        "emitted_at": emitted_at,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRimeServerHttpProviderAuth:
    def test_auth_sets_token(self, tmp_path):
        p = _make_provider(tmp_path)
        assert p._egress_token == "secret-token"

    def test_auth_raises_on_missing_file(self):
        p = RimeServerHttpProvider("test-app", server_url="http://x")
        with patch.object(
            type(p), "_credentials_file",
            new_callable=lambda: property(lambda self: Path("/nonexistent/creds.json"))
        ):
            with pytest.raises(FileNotFoundError):
                p._auth()

    def test_auth_raises_on_missing_token(self, tmp_path):
        creds_file = tmp_path / "application_credentials.json"
        creds_file.write_text(json.dumps({"test-app": {}}))
        p = RimeServerHttpProvider("test-app", server_url="http://x")
        with patch.object(type(p), "_credentials_file", new_callable=lambda: property(lambda self: creds_file)):
            with pytest.raises(KeyError):
                p._auth()


class TestParseEnvelope:
    def test_decodes_body(self):
        raw = _drain_message(body=b"raw bytes")
        env = RimeServerHttpProvider._parse_envelope(raw)
        assert env.body == b"raw bytes"

    def test_parses_received_at(self):
        raw = _drain_message(received_at="2026-01-01T12:00:00Z")
        env = RimeServerHttpProvider._parse_envelope(raw)
        assert env.received_at == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    def test_parses_emitted_at(self):
        raw = _drain_message(emitted_at="2026-01-01T11:55:00Z")
        env = RimeServerHttpProvider._parse_envelope(raw)
        assert env.emitted_at == datetime(2026, 1, 1, 11, 55, tzinfo=timezone.utc)

    def test_none_emitted_at(self):
        raw = _drain_message(emitted_at=None)
        env = RimeServerHttpProvider._parse_envelope(raw)
        assert env.emitted_at is None

    def test_invalid_base64_raises(self):
        raw = _drain_message()
        raw["body"] = "not valid base64!!!"
        with pytest.raises(ValueError):
            RimeServerHttpProvider._parse_envelope(raw)

    def test_returns_drained_envelope(self):
        raw = _drain_message(id="srv-42", message_id="edge-id")
        env = RimeServerHttpProvider._parse_envelope(raw)
        assert isinstance(env, DrainedEnvelope)
        assert env.id == "srv-42"
        assert env.message_id == "edge-id"


class TestPullBatchAndAck:
    def test_pull_batch_returns_envelopes(self, tmp_path):
        p = _make_provider(tmp_path)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "messages": [_drain_message("m1"), _drain_message("m2")]
        }
        p._session.get = MagicMock(return_value=mock_resp)

        batch = p._pull_batch(limit=10)
        assert len(batch) == 2
        assert batch[0].id == "m1"
        assert batch[1].id == "m2"

    def test_pull_batch_passes_limit(self, tmp_path):
        p = _make_provider(tmp_path)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"messages": []}
        p._session.get = MagicMock(return_value=mock_resp)

        p._pull_batch(limit=25)
        p._session.get.assert_called_once_with(
            "http://localhost:8080/v1/apps/test-app/messages",
            params={"limit": 25},
            timeout=10,
        )

    def test_ack_posts_ids(self, tmp_path):
        p = _make_provider(tmp_path)
        mock_resp = MagicMock()
        p._session.post = MagicMock(return_value=mock_resp)

        p._ack(["id-1", "id-2"])
        p._session.post.assert_called_once_with(
            "http://localhost:8080/v1/apps/test-app/messages/ack",
            json={"ids": ["id-1", "id-2"]},
            timeout=10,
        )


class TestRegistry:
    def test_rime_http_in_registry(self):
        from rime_ingest.providers.registry import PROVIDER_REGISTRY
        assert "rime-http" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["rime-http"] is RimeServerHttpProvider

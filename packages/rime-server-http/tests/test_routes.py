"""Smoke tests for the FastAPI routes using httpx.AsyncClient."""

from __future__ import annotations

import base64
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from rime_server_http.app import create_app
from rime_server_http.buffer import MessageBuffer
from rime_server_http.config import AppCredentials, Limits, ServerConfig


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_config() -> ServerConfig:
    return ServerConfig(
        limits=Limits(max_body_bytes=1024, max_queue_depth_per_app=5),
        apps={
            "test-app": AppCredentials(
                ingress_token="edge-secret",
                egress_token="ingest-secret",
            )
        },
    )


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    config = _make_config()
    buffer = MessageBuffer(max_depth_per_app=config.limits.max_queue_depth_per_app)
    app = create_app(config, buffer)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def client_with_buffer() -> AsyncIterator[tuple[AsyncClient, MessageBuffer]]:
    config = _make_config()
    buffer = MessageBuffer(max_depth_per_app=config.limits.max_queue_depth_per_app)
    app = create_app(config, buffer)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, buffer


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /v1/apps/{app_id}/messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_message_accepted(client):
    resp = await client.post(
        "/v1/apps/test-app/messages",
        content=b"hello",
        headers={
            "Authorization": "Bearer edge-secret",
            "Content-Type": "text/plain",
        },
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_post_message_wrong_token(client):
    resp = await client.post(
        "/v1/apps/test-app/messages",
        content=b"hello",
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_message_no_token(client):
    resp = await client.post("/v1/apps/test-app/messages", content=b"hello")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_message_unknown_app(client):
    resp = await client.post(
        "/v1/apps/unknown-app/messages",
        content=b"hello",
        headers={"Authorization": "Bearer edge-secret"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_message_empty_body(client):
    resp = await client.post(
        "/v1/apps/test-app/messages",
        content=b"",
        headers={"Authorization": "Bearer edge-secret"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_message_too_large(client):
    resp = await client.post(
        "/v1/apps/test-app/messages",
        content=b"x" * 2000,
        headers={"Authorization": "Bearer edge-secret"},
    )
    assert resp.status_code == 413  # FastAPI maps 413_CONTENT_TOO_LARGE


@pytest.mark.asyncio
async def test_post_message_queue_full(client):
    for _ in range(5):
        resp = await client.post(
            "/v1/apps/test-app/messages",
            content=b"data",
            headers={"Authorization": "Bearer edge-secret"},
        )
        assert resp.status_code == 202

    resp = await client.post(
        "/v1/apps/test-app/messages",
        content=b"overflow",
        headers={"Authorization": "Bearer edge-secret"},
    )
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET /v1/apps/{app_id}/messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_messages_empty(client):
    resp = await client.get(
        "/v1/apps/test-app/messages",
        headers={"Authorization": "Bearer ingest-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


@pytest.mark.asyncio
async def test_get_messages_returns_posted(client_with_buffer):
    ac, buf = client_with_buffer
    await ac.post(
        "/v1/apps/test-app/messages",
        content=b"payload-bytes",
        headers={
            "Authorization": "Bearer edge-secret",
            "Content-Type": "application/octet-stream",
        },
    )

    resp = await ac.get(
        "/v1/apps/test-app/messages",
        headers={"Authorization": "Bearer ingest-secret"},
    )
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 1
    assert base64.b64decode(messages[0]["body"]) == b"payload-bytes"
    assert messages[0]["content_type"] == "application/octet-stream"


@pytest.mark.asyncio
async def test_get_messages_respects_limit(client_with_buffer):
    ac, _ = client_with_buffer
    for i in range(3):
        await ac.post(
            "/v1/apps/test-app/messages",
            content=f"msg{i}".encode(),
            headers={"Authorization": "Bearer edge-secret"},
        )

    resp = await ac.get(
        "/v1/apps/test-app/messages?limit=2",
        headers={"Authorization": "Bearer ingest-secret"},
    )
    assert len(resp.json()["messages"]) == 2


@pytest.mark.asyncio
async def test_get_messages_wrong_token(client):
    resp = await client.get(
        "/v1/apps/test-app/messages",
        headers={"Authorization": "Bearer edge-secret"},  # ingress token, not egress
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /v1/apps/{app_id}/messages/ack
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ack_messages(client_with_buffer):
    ac, _ = client_with_buffer
    await ac.post(
        "/v1/apps/test-app/messages",
        content=b"data",
        headers={"Authorization": "Bearer edge-secret"},
    )

    drain = await ac.get(
        "/v1/apps/test-app/messages",
        headers={"Authorization": "Bearer ingest-secret"},
    )
    msg_id = drain.json()["messages"][0]["id"]

    ack = await ac.post(
        "/v1/apps/test-app/messages/ack",
        json={"ids": [msg_id]},
        headers={"Authorization": "Bearer ingest-secret"},
    )
    assert ack.status_code == 204


@pytest.mark.asyncio
async def test_ack_unknown_ids_still_204(client):
    resp = await client.post(
        "/v1/apps/test-app/messages/ack",
        json={"ids": ["not-a-real-id"]},
        headers={"Authorization": "Bearer ingest-secret"},
    )
    assert resp.status_code == 204

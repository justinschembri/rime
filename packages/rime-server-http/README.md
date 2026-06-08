# rime-server-http

Dumb HTTP ingress buffer that sits between **rime-edge** producers and **rime-ingest**.

```
edge device                    rime-server-http              rime-ingest
──────────                     ────────────────              ───────────
POST /v1/apps/{id}/messages ──▶ validate + enqueue
                                                  ◀── GET /v1/apps/{id}/messages
                                                  ◀── POST /v1/apps/{id}/messages/ack
```

No parsing, no pipeline logic — it accepts raw bytes, buffers them per `app_id`,
and hands them to ingest on demand.  Delivery is **at-least-once**: if ingest
crashes after GET but before ACK, the in-flight batch is lost on server restart
(requeue-stale is a post-MVP concern).

---

## Configuration

Mount a YAML credentials file and point the server at it:

```yaml
# server-credentials.yml

limits:
  max_body_bytes: 1048576          # 1 MiB
  max_queue_depth_per_app: 1000

apps:
  seismic-edge-01:
    ingress_token: "edge-secret"   # used by edge producers (POST)
    egress_token:  "ingest-secret" # used by rime-ingest (GET + ACK)
```

| Environment variable              | Default                                  |
|-----------------------------------|------------------------------------------|
| `RIME_SERVER_CREDENTIALS_FILE`    | `/app/runtime/server-credentials.yml`   |
| `RIME_SERVER_HOST`                | `0.0.0.0`                               |
| `RIME_SERVER_PORT`                | `8080`                                  |
| `RIME_SERVER_LOG_LEVEL`           | `info`                                  |

---

## API

### `POST /v1/apps/{app_id}/messages`
Accept a wire payload from an edge producer.

- Auth: `Authorization: Bearer <ingress_token>`
- Body: opaque bytes (`Content-Type` forwarded to ingest)
- Optional headers: `X-Rime-Message-Id`, `X-Rime-Emitted-At` (ISO-8601)
- Returns `202 Accepted`
- Returns `413` if body exceeds `max_body_bytes`
- Returns `429` if the queue for `app_id` is full

### `GET /v1/apps/{app_id}/messages?limit=N`
Drain up to N pending messages (default 50, max 500).

- Auth: `Authorization: Bearer <egress_token>`
- Returns JSON `{"messages": [{id, message_id, received_at, emitted_at, content_type, body}, ...]}`
- `body` is base64-encoded
- Drained messages move to in-flight until acknowledged

### `POST /v1/apps/{app_id}/messages/ack`
Commit processed messages.

- Auth: `Authorization: Bearer <egress_token>`
- Body: `{"ids": ["server-uuid", ...]}`
- Returns `204 No Content`

### `GET /health`
Liveness probe. Returns `{"status": "ok"}`. No auth.

### `GET /v1/stats`
Per-app queue depths. No auth. Intended for ops/debugging only.

---

## Running locally

```bash
# Install (creates .venv in this directory)
uv sync

# Provide a credentials file
export RIME_SERVER_CREDENTIALS_FILE=/path/to/server-credentials.yml

# Start the server
uv run rime-server-http
```

## Docker

```bash
docker build -t rime-server-http .
docker run -p 8080:8080 \
  -v /path/to/runtime:/app/runtime:ro \
  rime-server-http
```

The `/app/runtime/` directory must contain `server-credentials.yml` (or override
`RIME_SERVER_CREDENTIALS_FILE`).

---

## Tests

```bash
uv run pytest tests/ -v
```

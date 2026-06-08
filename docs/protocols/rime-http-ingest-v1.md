# Rime HTTP ingest protocol (v1)

Normative contract between **edge producers** (`rime-edge`) and
**`rime-server-http`**. Draft — implementations should track this document until
an OpenAPI spec replaces it.

## Roles

| Party | Responsibility |
|-------|----------------|
| Edge producer | `POST` wire payloads |
| `rime-server-http` | Authenticate, buffer, expose for ingest pull |
| `rime-ingest` | Poll drain API, decapsulate, upload to FROST |

The server does not parse sensor payloads. Ingest does not accept direct pushes
from edge nodes.

## Ingress: edge → server

### Request

```
POST /v1/apps/{app_id}/messages HTTP/1.1
Host: <rime-server-http>
Authorization: Bearer <api_key>
Content-Type: <opaque; e.g. application/octet-stream, text/csv, application/json>
X-Rime-Message-Id: <uuid; optional but recommended for idempotency>
X-Rime-Emitted-At: <ISO-8601 UTC; optional; edge clock>
```

**Body:** opaque octets — the `wire_message`. No rime-specific JSON envelope is
required for v1; headers carry routing metadata.

### Responses

| Status | Meaning |
|--------|---------|
| `202 Accepted` | Buffered successfully |
| `400 Bad Request` | Missing/invalid headers or empty body |
| `401 Unauthorized` | Invalid or missing credential |
| `403 Forbidden` | Credential valid but not allowed for `app_id` |
| `409 Conflict` | Duplicate `X-Rime-Message-Id` (optional server behaviour) |
| `413 Payload Too Large` | Body exceeds server limit |
| `429 Too Many Requests` | Buffer full; edge should retry with backoff |
| `5xx` | Transient server error; edge should retry with backoff |

## Egress: ingest → server

Defined when `rime-server-http` is implemented. Expected shape:

- `GET /v1/apps/{app_id}/messages` — fetch pending batch
- `POST /v1/apps/{app_id}/messages/ack` — commit after processing

Delivery semantics: **at-least-once**. Edge and ingest must tolerate duplicates.

## `app_id`

Must match an application entry in central `application-configs.yml` so ingest
knows which decapsulator and sensor registry entries apply.

## Alternative envelope (optional)

For debugging or small JSON payloads, producers may use:

```
Content-Type: application/vnd.rime.message+json
```

```json
{
  "message_id": "uuid",
  "emitted_at": "2026-06-08T12:00:00Z",
  "content_type": "text/csv",
  "body": "<base64>"
}
```

Binary-heavy producers should use raw body + headers instead.

## Versioning

- URL prefix `/v1/` is frozen per major version.
- Breaking changes require `/v2/` and a migration period.
- Edge release tarballs should record supported protocol version in a
  `PROTOCOL_VERSION` file or binary `--version` output.

## See also

- [`packages/rime-edge/README.md`](../../packages/rime-edge/README.md)
- [`docs/roadmap.md`](../roadmap.md)

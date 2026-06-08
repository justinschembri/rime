# `rime-servers`

Dumb protocol forwarders at the center of the rime deployment. Devices and edge
producers connect here; **ingest** consumes buffered payloads via the same
pull/subscribe patterns used for external providers.

## Planned components

| Server | Status | Notes |
|--------|--------|-------|
| `rime-server-http` | Planned | `POST` ingress from edge; drain API for ingest |
| `rime-server-mqtt` | Planned | Managed broker replacement for Mosquitto stub |
| `rime-server-seedlink` | Would-have | Seismic instruments |

See [architecture roadmap](../../docs/roadmap.md).

## `rime-server-http`

Responsibilities only:

1. Authenticate ingress (`Authorization`, per-`app_id` credentials).
2. Buffer wire messages (memory + optional disk spool).
3. Serve a pull/drain API for `rime-ingest` (no inline calls into ingest).

Wire contract: [rime-http-ingest-v1](../../docs/protocols/rime-http-ingest-v1.md).

Implementation will live in this package when work begins. Until then, this
directory holds the architectural slot and links to the protocol spec.

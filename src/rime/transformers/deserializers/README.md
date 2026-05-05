# `deserializers` (stub)

**Planned role:** convert **serialized wire forms** into **Python values** (`Any`) without yet assigning sensor identity or stripping vendor envelopes.

Typical jobs:

- `str` / `bytes` → `dict` / `list` via **JSON**, **CBOR**, **msgpack**, etc.
- Optional schema validation at the “syntax” level only (not STA semantics)

## Current status

**Not wired.** Many paths deserialize inside the transport (e.g. `json.loads` on MQTT payload) or receive already-parsed `dict`s from HTTP clients.

## Relationship to other stages

- **After** [`frames`](../frames/README.md) if the input is still raw bytes.
- **Before** [`envelopes`](../envelopes/README.md) when the decapsulator expects a **parsed tree**, not a string.
- Distinct from **[`decoders`](../decoders/README.md)** — deserializers recover **structure**; decoders apply **vendor / crypto / compression semantics** to the payload body.

## Suggested contract (future)

Pure functions: `deserialize(payload: bytes | str, content_type: str) -> Any` or small strategy registry keyed by integration.

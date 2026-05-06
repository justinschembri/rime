# `deserializers`

## Shipped

- [`NullDeserializer`](null.py) — **identity** `deserialize(msg) -> msg`, used as the
  default model component in [`../ingest_registry.py`](../ingest_registry.py).

## Planned

Convert **serialized wire forms** into **Python values** (`Any`) without yet assigning sensor identity or applying decapsulation.

Typical jobs:

- `str` / `bytes` → `dict` / `list` via **JSON**, **CBOR**, **msgpack**, etc.
- Optional schema validation at the “syntax” level only (not STA semantics)

Many paths still deserialize inside the transport (e.g. `json.loads` on MQTT payload) or receive already-parsed `dict`s from HTTP clients; move that here when formats multiply.

## Relationship to other stages

- **After** [`frames`](../frames/README.md) if the input is still raw bytes.
- **Before** [`decapsulators`](../decapsulators/README.md) when the decapsulator expects a **parsed tree**, not a string.
- Distinct from **[`decoders`](../decoders/README.md)** — deserializers recover **structure**; decoders apply **vendor / crypto / compression semantics** to the payload body.

## Suggested contract (future)

Pure functions: `deserialize(payload: bytes | str, content_type: str) -> Any` or small strategy registry keyed by integration.

Register a custom deserializer in [`../ingest_registry.py`](../ingest_registry.py)
for the relevant `SupportedSensors` entry.

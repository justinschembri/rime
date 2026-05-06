# `decoders`

## Shipped

- [`NullDecoder`](null.py) — **identity** `decode(msg: DecapsulatedMessage) -> DecodedMessage` via [`DecodedMessage.from_decapsulated`](../messages.py), used as the default model component in [`../ingest_registry.py`](../ingest_registry.py).

## Planned

Interpret the **decapsulated payload body** when it is not yet a plain observation `dict` — decryption, decompression, protobuf / custom binary layouts, vendor “frm_payload” expansion, etc.

This aligns with [`DecodedMessage`](../messages.py): same `sensor_id` and timestamps, `payload` still `Any` but **meaningfully decoded** for the next step.

[`decapsulated_to_parsed_identity_decode`](../messages.py) also delegates to **`NullDecoder`** when you already hold a list of **`DecapsulatedMessage`**.

## Relationship to other stages

- **After** [`envelopes`](../envelopes/README.md) — you already know **which device** the bytes belong to.
- **Before** strict **parse to `dict[str, Any]`** — decoders may emit nested structures that a later normalizer or a dedicated “flatten” step consumes.
- Distinct from **[`deserializers`](../deserializers/README.md)** — e.g. base64 **string** → **bytes** might be deserialization; **bytes** → **application fields** is decoding.

## Suggested contract (future)

`Decoder` protocol: `decode(msg: DecapsulatedMessage) -> DecodedMessage`, or per-vendor callables. Register in [`../ingest_registry.py`](../ingest_registry.py).

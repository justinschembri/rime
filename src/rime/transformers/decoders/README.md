# `decoders` (stub)

**Planned role:** interpret the **decapsulated payload body** when it is not yet a plain observation `dict` — decryption, decompression, protobuf / custom binary layouts, vendor “frm_payload” expansion, etc.

This aligns with [`DecodedMessage`](../messages.py): same `sensor_id` and timestamps, `payload` still `Any` but **meaningfully decoded** for the next step.

## Current status

**Not wired.** [`decapsulated_to_parsed_identity_decode`](../messages.py) implements an **identity** decode: `DecodedMessage.from_decapsulated` copies `payload` unchanged, then `ParsedMessage.from_decoded` requires a `dict`.

## Relationship to other stages

- **After** [`envelopes`](../envelopes/README.md) — you already know **which device** the bytes belong to.
- **Before** strict **parse to `dict[str, Any]`** — decoders may emit nested structures that a later normalizer or a dedicated “flatten” step consumes.
- Distinct from **[`deserializers`](../deserializers/README.md)** — e.g. base64 **string** → **bytes** might be deserialization; **bytes** → **application fields** is decoding.

## Suggested contract (future)

`Decoder` protocol: `decode(msg: DecapsulatedMessage) -> DecodedMessage`, or per-vendor callables registered beside decapsulators in providers.

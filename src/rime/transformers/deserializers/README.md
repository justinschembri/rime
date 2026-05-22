# `deserializers`

Optional model-level step that converts an **opaque payload** (bytes, base64 string, CBOR blob) into a **structured Python object** the decoder or parser can work with.

## When to use

Register a deserializer when the `IdentifiedPayload.payload` arriving after decapsulation is not yet a structured form.  Typical cases:

- Raw LoRaWAN `frm_payload` (base64 string → bytes → dict via a vendor codec)
- CBOR or MessagePack-encoded readings
- zlib-compressed JSON

Leave `deserializer=None` in `IngestModelComponents` (the default) when the provider already delivers a decoded dict — e.g. TTN `decoded_payload`, Netatmo `dashboard_data`.

## Contract

```python
Deserializer.deserialize(
    identified: IdentifiedPayload,
    envelope: EnvelopeMetadata | None,
) -> IdentifiedPayload
```

Returns a new `IdentifiedPayload` with the same `sensor_uuid` but a deserialized `payload` value.

## Wire-level utility (not a model-level deserializer)

- [`JsonWireDeserializer`](json_wire.py) — `bytes | str → Any` via `json.loads`.  Used by `MQTTTransport._deserialize_wire` *before* decapsulation; not registered in `INGEST_COMPONENT_MAP`.

## Relationship to other stages

- Runs **after** [`decapsulators`](../decapsulators/README.md): identity is already known.
- Runs **before** [`decoders`](../decoders/README.md): payload is still opaque.
- Distinct from **[`decoders`](../decoders/README.md)**: deserializers recover **structure**; decoders apply **vendor/semantic interpretation** to an already-structured payload.

## Adding a deserializer

1. Subclass [`Deserializer`](core.py).
2. Implement `deserialize(identified, envelope) -> IdentifiedPayload`.
3. Register under `deserializer=` in [`../ingest_registry.py`](../ingest_registry.py).

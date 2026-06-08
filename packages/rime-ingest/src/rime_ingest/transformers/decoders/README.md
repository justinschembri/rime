# `decoders`

Optional model-level step that interprets a **structured but raw payload** and converts it into **observation-ready values**.

## When to use

Register a decoder when `IdentifiedPayload.payload` is already a dict or list but its values are not yet physical observations.  Typical cases:

- Raw ADC register values → temperature / pressure floats
- Bit-field expansion (e.g. status byte → individual boolean fields)
- Decryption of a structured container
- Decompression of a nested payload that is itself structured

Leave `decoder=None` in `IngestModelComponents` (the default) when the payload values are already observation-ready — e.g. Milesight `decoded_payload` and Netatmo `dashboard_data` both arrive with physical values intact.

## Contract

```python
Decoder.decode(
    identified: IdentifiedPayload,
    envelope: EnvelopeMetadata | None,
) -> IdentifiedPayload
```

Returns a new `IdentifiedPayload` with the same `sensor_uuid` but a semantically decoded `payload` value.

## Pipeline position

```text
[optional Deserializer]  →  [optional Decoder]  →  Parser  →  Normalizer
```

The decoder sees a structured payload (dict/list) produced either directly by decapsulation or by a preceding deserializer.

## Relationship to other stages

- Runs **after** [`deserializers`](../deserializers/README.md): payload is already structured.
- Runs **before** [`parsers`](../parsers/README.md): parser expects observation-ready values.
- Distinct from **[`deserializers`](../deserializers/README.md)**: decoders apply **vendor/semantic interpretation**; deserializers recover **structure** from opaque bytes.

## Adding a decoder

1. Subclass [`Decoder`](core.py).
2. Implement `decode(identified, envelope) -> IdentifiedPayload`.
3. Register under `decoder=` in [`../ingest_registry.py`](../ingest_registry.py).

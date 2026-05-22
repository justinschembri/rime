# `parsers`

Parsers are the model-specific bridge between decapsulation and transformation.

## Role

A parser receives:

1. One [`IdentifiedPayload`](../decapsulators/types.py) — the native sensor fragment, already stripped of provider framing.
2. Optional [`EnvelopeMetadata`](../decapsulators/types.py) — leftover provider-level context such as timestamps the sensor payload does not carry itself.

It returns a [`ParsedMessage`](../messages.py) carrying:

- `sensor_uuid` — the registry key (copied from `IdentifiedPayload`)
- `body` — the normalised sensor reading, ready for the transformer
- `provider_timestamp` / `phenomenon_timestamp` — resolved timestamps

## Key principle

A parser is **model-specific, not provider-specific**.  The same parser handles
the same sensor model regardless of whether the payload arrived via TTN, a
direct MQTT broker, or an HTTP endpoint.  Provider identity has already been
removed by decapsulation; the envelope supplies only what the payload itself
cannot carry (e.g. the TTN gateway receive time).

## Implementations

| Class | Purpose |
|-------|---------|
| [`NullParser`](null.py) | Identity pass-through — payload needs no restructuring before the transformer. Default for most registered models. |

## Where it sits in the pipeline

```text
DecapsulatedMessage.sensor_payloads[]
  → Parser.parse(identified, envelope)
     → ParsedMessage
        → VendorObservationNormalizer
```

## Adding a parser

1. Subclass [`Parser`](core.py) with a static `parse(identified, envelope) -> ParsedMessage`.
2. Raise `UnpackError` on malformed payloads.
3. Register in [`../ingest_registry.py`](../ingest_registry.py) under the relevant `SupportedSensors` key.

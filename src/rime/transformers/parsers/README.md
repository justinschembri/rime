# `parsers`

Parsers are the model-specific bridge between decapsulation and normalization.

## Role

A parser receives:

1. One [`IdentifiedPayload`](../../transformers/messages.py) — the native sensor fragment, already stripped of provider framing.
2. Optional [`EnvelopeMetadata`](../../transformers/messages.py) — leftover provider-level context such as timestamps the sensor payload does not carry itself.

It returns an [`ObservationRecord`](../../transformers/messages.py) carrying:

- `sensor_uuid` — the registry key (copied from `IdentifiedPayload`)
- `observations` — only observation-ready key/value pairs; timestamps and non-observation metadata have been extracted or dropped
- `provider_timestamp` / `phenomenon_timestamp` — resolved timestamps

## Contract

Every sensor model must register a concrete `Parser`.  The `observations` field
on the returned `ObservationRecord` must contain **only** observation fields — the
normalizer expects a clean dict of physical quantities with no metadata mixed in.

Each parser must define `_REQUIRED_FIELDS` and validate them before returning.

## Key principle

A parser is **model-specific, not provider-specific**.  The same parser handles
the same sensor model regardless of whether the payload arrived via TTN, a
direct MQTT broker, or an HTTP endpoint.  Provider identity has already been
removed by decapsulation; the envelope supplies only what the payload itself
cannot carry (e.g. the TTN gateway receive time).

## Implementations

| Class | Purpose |
|-------|---------|
| [`MilesightAm103lParser`](milesight.py) | Validates AM103L fields; timestamps from envelope. |
| [`MilesightAm308lParser`](milesight.py) | Validates AM308L fields; timestamps from envelope. |
| [`NetatmoNWS03Parser`](netatmo.py) | Lowercases keys, extracts `time_utc`, drops trend fields. |

## Where it sits in the pipeline

```text
DecapsulatedMessage.identified_payloads[]
  → Parser.parse(identified, envelope)
     → ObservationRecord
        → VendorObservationNormalizer
```

## Adding a parser

1. Subclass [`Parser`](core.py) with a static `parse(identified, envelope) -> ObservationRecord`.
2. Define `_REQUIRED_FIELDS` and validate them; raise `MissingPayloadKeysError` on missing keys.
3. Raise `UnpackError` on malformed payloads.
4. Ensure `observations` contains only observation-ready fields (no timestamps, no metadata).
5. Register in [`../ingest_registry.py`](../ingest_registry.py) under the relevant `SupportedSensors` key.

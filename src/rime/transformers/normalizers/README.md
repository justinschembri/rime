# `normalizers`

**Parsed → STA** — turns a **parsed per-sensor body** (`dict[str, Any]`) into **SensorThings `Observation`** instances (and datastream names) for FROST upload.

## Entry points

- [`VendorObservationNormalizer`](core.py) — Pydantic base: field validation, `TRANSFORM` lambdas, `NAME_TRANSFORM` → `ObservedProperties`, `to_stObservations()`.
- [`from_parsed(msg: ParsedMessage)`](core.py) — builds the model from `msg.body` and sets `provider_phenomenon_time` from `msg.phenomenon_timestamp`.
- [`NORMALIZER_MAP`](../registry.py) — maps [`SupportedSensors`](../types.py) to concrete normalizer classes.

## Implementations

| Sensor kind | Class |
|-------------|--------|
| Milesight AM103L | [`MilesightAm103lNormalizer`](milesight.py) |
| Milesight AM308L | [`MilesightAm308lNormalizer`](milesight.py) |
| Netatmo NWS03 | [`NetatmoNWS03`](netatmo.py) |

## Where it sits in the pipeline

```text
ParsedMessage  →  model-selected normalizer (VendorObservationNormalizer)  →  list[(Observation, datastream)]
```

Selection uses `sensor_registry[sensor_uuid]` → `SupportedSensors` in [`SensorTransport._process_payload`](../../transport/base.py), then `INGEST_COMPONENT_MAP` picks the normalizer.

## Adding a normalizer

1. Subclass `VendorObservationNormalizer` with fields matching the keys in `ParsedMessage.body` (the parser is responsible for normalization to lowercase before this stage).
2. Set `NAME_TRANSFORM` (required) and optional `TRANSFORM` lambdas.
3. Register in [`../ingest_registry.py`](../ingest_registry.py) under the `normalizer` key.
4. Ensure config / STA templates use the matching `SupportedSensors` value.

This layer is **not** responsible for wire shapes, provider envelopes, or key normalization — that belongs to **decapsulators**, **parsers**, and **providers**.

# `normalizers`

**Native → STA** — turns a **parsed per-sensor body** (`dict[str, Any]`) into **SensorThings `Observation`** instances (and datastream names) for FROST upload.

## Entry points

- [`VendorObservationTransformer`](core.py) — Pydantic base: field validation, `TRANSFORM` lambdas, `NAME_TRANSFORM` → `ObservedProperties`, `to_stObservations()`.
- [`from_parsed(msg: ParsedMessage)`](core.py) — builds the model from `msg.body` and sets `provider_phenomenon_time` from `msg.provider_timestamp`.
- [`TRANSFORMER_MAP`](../registry.py) — maps [`SupportedSensors`](../types.py) to concrete normalizer classes.

## Implementations

| Sensor kind | Class |
|-------------|--------|
| Milesight AM103L | [`MilesightAm103lObservationTransformer`](milesight.py) |
| Milesight AM308L | [`MilesightAm308lObservationTransformer`](milesight.py) |
| Netatmo NWS03 | [`NetatmoNWS03`](netatmo.py) |

## Where it sits in the pipeline

```text
ParsedMessage  →  model-selected normalizer  →  VendorObservationTransformer  →  list[Observation, datastream]
```

Selection uses `sensor_registry[sensor_id]` -> `SupportedSensors` in [`SensorTransport._process_payload`](../../transport/base.py), then `INGEST_COMPONENT_MAP` chooses the normalizer as the `transformer` component.

## Adding a normalizer

1. Subclass `VendorObservationTransformer` with fields matching **lowercased** keys in `ParsedMessage.body` (see `from_parsed`).
2. Set `NAME_TRANSFORM` (and optional `TRANSFORM`) like existing devices.
3. Register in [`../registry.py`](../registry.py).
4. Ensure config / STA templates use the matching `SupportedSensors` value.

This layer is **not** responsible for MQTT topics, HTTP shapes, or TTN JSON — that belongs to **decapsulators** and **providers**.

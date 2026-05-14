# `transformers`

Maps **upstream application payloads** into **SensorThings-shaped observations** and FROST uploads. The package is split by **pipeline stage** so each concern stays small and testable.

## Layout

| Path | Role |
|------|------|
| [`types.py`](types.py) | Shared enums and aliases: `SensorUUID`, `SupportedSensors`, `ObservedProperties`. |
| [`messages.py`](messages.py) | **Message** types: `DecodedMessage`, `ParsedMessage`, and list helpers. |
| [`ingest_registry.py`](ingest_registry.py) | **Per-model ingest components**: deserializer, decoder, and `VendorObservationTransformer`. |
| [`decapsulators/`](decapsulators/README.md) | **Decapsulation** — wire / vendor shells -> `list[DecapsulatedMessage]`. |
| [`normalizers/`](normalizers/README.md) | **STA projection** — `ParsedMessage.body` → `Observation` via `VendorObservationTransformer` implementations. |
| [`deserializers/`](deserializers/README.md) | Post-decapsulation payload deserializers; includes **identity** [`NullDeserializer`](deserializers/null.py). |
| [`decoders/`](decoders/README.md) | Post-decapsulation semantic decoders; includes **identity** [`NullDecoder`](decoders/null.py). |

Providers only decapsulate (`_decapsulate_wire`). `SensorTransport` resolves per-model ingest components from [`ingest_registry.py`](ingest_registry.py), then runs deserializer → decoder → parse → transformer.

## Wire payload lifecycle (transport -> FROST)

| Stage | Owner | Input | Output | Responsibility |
|------|------|------|------|------|
| 1 | Transport (`SensorTransport._run`) | Wire payload from poll/subscription transport | `wire_payload` | Acquire one upstream payload and forward it to shared processing. |
| 2 | Transport (`SensorTransport._process_payload`) | `wire_payload` | `list[DecapsulatedMessage]` | Call provider decode/deserialize/decapsulate hooks. |
| 3 | Provider (`_decapsulate_wire`) + `decapsulators/*` | Provider envelope | `DecapsulatedMessage` entries | Decapsulate envelope, route by `sensor_id`, preserve timing hints. |
| 4 | Ingest registry (`INGEST_COMPONENT_MAP`) | `sensor_model` from `sensor_registry[sensor_id]` | Deserializer/decoder/transformer classes | Select per-model ingest components. |
| 5 | Deserializer + Decoder + parser | `DecapsulatedMessage` | `ParsedMessage` | Deserialize/semantic decode and normalize message body shape. |
| 6 | Normalizer (`VendorObservationTransformer`) | `ParsedMessage` | SensorThings observation tuples | Build `Observation` + datastream name tuples (`to_stObservations`). |
| 7 | FROST uploader (`frost_observation_upload`) | `(sensor_id, observation tuple)` | Persisted Observation in FROST | Resolve datastream and POST observation to FROST. |

See [`.cursor/ingress-pipeline-refactor-report.md`](../../../.cursor/ingress-pipeline-refactor-report.md) for diagrams and history.

## Adding a new sensor line

1. **Decapsulator** (if the provider envelope is new) under `decapsulators/`.
2. **Ingest components** under `deserializers/`, `decoders/`, and `normalizers/`, then register in [`ingest_registry.py`](ingest_registry.py).
3. **Provider** — implement `_decapsulate_wire` (see [`providers/README.md`](../providers/README.md)).

## See also

- [`../providers/README.md`](../providers/README.md) — where `_decapsulate_wire` lives.
- [`../transport/README.md`](../transport/README.md) — threading and `_process_payload`.

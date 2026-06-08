# `transformers`

Maps **upstream wire messages** into **SensorThings-shaped observations** and FROST uploads. The package is split by **pipeline stage** so each concern stays small and testable.

## Vocabulary

| Term | Meaning |
|------|---------|
| **wire message** | Raw provider artifact received from the network (MQTT packet, HTTP webhook body, API response). Untyped; no rime contract applies until decapsulation. |
| **Payload** | The sensor-native reading as emitted by the sensor firmware. Provider-independent: the same sensor model on a different upstream provider produces the same payload shape. |
| **IdentifiedPayload** | A `Payload` + rime routing identity (`sensor_uuid`). Compositionally: `IdentifiedPayload = Payload + identity`. |
| **DecapsulatedMessage** | The ingest unit produced by a decapsulator. One wire message fans out into 0–N `IdentifiedPayload` entries. |
| **observations** | The observation-ready key/value dict on an `ObservationRecord`. Timestamps and non-observation metadata are extracted or dropped by the parser before this point. |

## Layout

| Path | Role |
|------|------|
| [`types.py`](types.py) | Shared enums and aliases: `SensorUUID`, `SupportedSensors`, `ObservedProperties`. |
| [`messages.py`](messages.py) | **All pipeline carrier types**: `IdentifiedPayload`, `EnvelopeMetadata`, `DecapsulatedMessage`, `ObservationRecord`. |
| [`ingest_registry.py`](ingest_registry.py) | **Per-model ingest components**: `parser` + `VendorObservationNormalizer`. |
| [`decapsulators/`](decapsulators/README.md) | **Decapsulation** — provider shell → `DecapsulatedMessage` containing `list[IdentifiedPayload]`. ABC in `core.py`. |
| [`parsers/`](parsers/README.md) | **Parsing** — `IdentifiedPayload` + `EnvelopeMetadata` → `ObservationRecord`. |
| [`normalizers/`](normalizers/README.md) | **STA projection** — `ObservationRecord.observations` → `Observation` via `VendorObservationNormalizer` implementations. |
| [`decoders/`](decoders/README.md) | Optional binary/codec decoders (not in the default pipeline). |

Providers only decapsulate (`_decapsulate_wire`). `SensorTransport` iterates the resulting `identified_payloads`, resolves per-model components from [`ingest_registry.py`](ingest_registry.py), and runs parser → normalizer (`IdentifiedPayload` → `ObservationRecord` → observations).

## Wire message lifecycle (transport → FROST)

| Stage | Owner | Input | Output | Responsibility |
|-------|-------|-------|--------|----------------|
| 1 | Transport (`SensorTransport._run`) | Wire message from poll/subscription | `wire_message` | Acquire one upstream wire message and forward it to shared processing. |
| 2 | Transport (`SensorTransport._process_wire_message`) | `wire_message` | `DecapsulatedMessage` | Call provider decode/deserialize/decapsulate hooks. |
| 3 | Provider (`_decapsulate_wire`) + `decapsulators/*` | Provider envelope | `DecapsulatedMessage(identified_payloads[], envelope_metadata)` | Strip envelope; pair each sensor fragment with its registry ID. |
| 4 | Transport loop | `identified_payloads[]` | per-`IdentifiedPayload` iteration | Registry lookup; select model components. |
| 5 | Parser (`parser.parse`) | `IdentifiedPayload` + `EnvelopeMetadata` | `ObservationRecord` | Assemble fully-resolved record: `sensor_uuid`, observation-only `observations` dict, timestamps. |
| 6 | Normalizer (`VendorObservationNormalizer`) | `ObservationRecord` | SensorThings observation tuples | Build `Observation` + datastream name tuples (`to_stObservations`). |
| 7 | FROST uploader (`frost_observation_upload`) | `(sensor_uuid, observation tuple)` | Persisted Observation in FROST | Resolve datastream and POST observation to FROST. |

## Adding a new sensor line

1. **Decapsulator** (if the provider envelope is new) under `decapsulators/`.
2. **Parser** under `parsers/` — every sensor model requires a concrete `Parser` with `_REQUIRED_FIELDS` validation.
3. **Normalizer** under `normalizers/`, then register both in [`ingest_registry.py`](ingest_registry.py).
4. **Provider** — implement `_decapsulate_wire` (see [`providers/README.md`](../providers/README.md)).

## See also

- [`../providers/README.md`](../providers/README.md) — where `_decapsulate_wire` lives.
- [`../transport/README.md`](../transport/README.md) — threading and `_process_wire_message`.

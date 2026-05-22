# `transformers`

Maps **upstream application payloads** into **SensorThings-shaped observations** and FROST uploads. The package is split by **pipeline stage** so each concern stays small and testable.

## Layout

| Path | Role |
|------|------|
| [`types.py`](types.py) | Shared enums and aliases: `SensorUUID`, `SupportedSensors`, `ObservedProperties`. |
| [`messages.py`](messages.py) | **Message** types: `ParsedMessage` (pipeline output of parsers) and optional `DecodedMessage` (for binary decoder paths). |
| [`ingest_registry.py`](ingest_registry.py) | **Per-model ingest components**: `parser` + `VendorObservationNormalizer`. |
| [`decapsulators/`](decapsulators/README.md) | **Decapsulation** — provider shell → `DecapsulatedMessage` containing `list[IdentifiedPayload]`. |
| [`parsers/`](parsers/README.md) | **Parsing** — `IdentifiedPayload` + `EnvelopeMetadata` → `ParsedMessage`. |
| [`normalizers/`](normalizers/README.md) | **STA projection** — `ParsedMessage.body` → `Observation` via `VendorObservationNormalizer` implementations. |
| [`decoders/`](decoders/README.md) | Optional binary/codec decoders (not in the default pipeline). |

Providers only decapsulate (`_decapsulate_wire`). `SensorTransport` iterates the resulting `sensor_payloads`, resolves per-model components from [`ingest_registry.py`](ingest_registry.py), and runs parser → transformer.

## Wire payload lifecycle (transport → FROST)

| Stage | Owner | Input | Output | Responsibility |
|-------|-------|-------|--------|----------------|
| 1 | Transport (`SensorTransport._run`) | Wire payload from poll/subscription | `wire_payload` | Acquire one upstream payload and forward it to shared processing. |
| 2 | Transport (`SensorTransport._process_payload`) | `wire_payload` | `DecapsulatedMessage` | Call provider decode/deserialize/decapsulate hooks. |
| 3 | Provider (`_decapsulate_wire`) + `decapsulators/*` | Provider envelope | `DecapsulatedMessage(sensor_payloads[], envelope_metadata)` | Strip envelope; pair each sensor fragment with its registry ID. |
| 4 | Transport loop | `sensor_payloads[]` | per-`IdentifiedPayload` iteration | Registry lookup; select model components. |
| 5 | Parser (`parser.parse`) | `IdentifiedPayload` + `EnvelopeMetadata` | `ParsedMessage` | Assemble fully-resolved record: `sensor_uuid`, normalised `body`, timestamps. |
| 6 | Normalizer (`VendorObservationNormalizer`) | `ParsedMessage` | SensorThings observation tuples | Build `Observation` + datastream name tuples (`to_stObservations`). |
| 7 | FROST uploader (`frost_observation_upload`) | `(sensor_uuid, observation tuple)` | Persisted Observation in FROST | Resolve datastream and POST observation to FROST. |

## Adding a new sensor line

1. **Decapsulator** (if the provider envelope is new) under `decapsulators/`.
2. **Parser** under `parsers/` (use `NullParser` if the payload needs no restructuring).
3. **Normalizer** under `normalizers/`, then register both in [`ingest_registry.py`](ingest_registry.py).
4. **Provider** — implement `_decapsulate_wire` (see [`providers/README.md`](../providers/README.md)).

## See also

- [`../providers/README.md`](../providers/README.md) — where `_decapsulate_wire` lives.
- [`../transport/README.md`](../transport/README.md) — threading and `_process_payload`.

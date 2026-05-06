# `transformers`

Maps **upstream application payloads** into **SensorThings–shaped observations** and FROST uploads. The package is split by **pipeline stage** so each concern stays small and testable.

## Layout

| Path | Role |
|------|------|
| [`types.py`](types.py) | Shared enums and aliases: `SensorUUID`, `SupportedSensors`, `ObservedProperties`. |
| [`messages.py`](messages.py) | **Message** types: `DecodedMessage`, `ParsedMessage`, and list helpers. |
| [`ingest_registry.py`](ingest_registry.py) | **Per-model ingest components**: deserializer, decoder, and `VendorObservationTransformer`. |
| [`envelopes/`](envelopes/README.md) | **Envelope strip** — wire / vendor shells → `list[DecapsulatedMessage]`. |
| [`normalizers/`](normalizers/README.md) | **STA projection** — `ParsedMessage.body` → `Observation` via `VendorObservationTransformer` and `TRANSFORMER_MAP`. |
| [`frames/`](frames/README.md) | *Stub* — stream / packet framing (not wired yet). |
| [`deserializers/`](deserializers/README.md) | Post-decapsulation payload deserializers; includes **identity** [`NullDeserializer`](deserializers/null.py). |
| [`decoders/`](decoders/README.md) | Post-decapsulation semantic decoders; includes **identity** [`NullDecoder`](decoders/null.py). |

Providers now only decapsulate (`_decapsulate_application_payload`). `SensorTransport` resolves per-model ingest components from [`ingest_registry.py`](ingest_registry.py), then runs deserializer → decoder → parse → transformer.

## End-to-end flow (current)

1. **Transport** — `SensorTransport._process_payload` receives a wire-level payload.
2. **Provider** — `_decapsulate_application_payload` returns `list[DecapsulatedMessage]`.
3. **Normalizers** — For each `ParsedMessage`, `TRANSFORMER_MAP` selects a model; `from_parsed` + `to_stObservations` build STA tuples.
4. **FROST** — `frost_observation_upload` (outside this package).

See [`.cursor/ingress-pipeline-refactor-report.md`](../../../.cursor/ingress-pipeline-refactor-report.md) for diagrams and history.

## Adding a new sensor line

1. **Decapsulator** (if the app envelope is new) under `envelopes/`.
2. **Ingest components** under `deserializers/`, `decoders/`, and `normalizers/`, then register in [`ingest_registry.py`](ingest_registry.py).
3. **Provider** — implement `_decapsulate_application_payload` (see [`providers/README.md`](../providers/README.md)).

## See also

- [`../providers/README.md`](../providers/README.md) — where `_decapsulate_application_payload` lives.
- [`../transport/README.md`](../transport/README.md) — threading and `_process_payload`.

# `transformers`

Maps **upstream application payloads** into **SensorThings–shaped observations** and FROST uploads. The package is split by **pipeline stage** so each concern stays small and testable.

## Layout

| Path | Role |
|------|------|
| [`types.py`](types.py) | Shared enums and aliases: `SensorUUID`, `SupportedSensors`, `ObservedProperties`. |
| [`messages.py`](messages.py) | **Message** types: `DecodedMessage`, `ParsedMessage`, and list helpers. |
| [`ingress_pipeline.py`](ingress_pipeline.py) | **Compose** deserialize → decapsulate → decode → parse (`ingest_to_parsed_messages`). |
| [`envelopes/`](envelopes/README.md) | **Envelope strip** — wire / vendor shells → `list[DecapsulatedMessage]`. |
| [`normalizers/`](normalizers/README.md) | **STA projection** — `ParsedMessage.body` → `Observation` via `NativePayloadTransformer` and `TRANSFORMER_MAP`. |
| [`frames/`](frames/README.md) | *Stub* — stream / packet framing (not wired yet). |
| [`deserializers/`](deserializers/README.md) | Wire format → Python; includes **identity** [`NullDeserializer`](deserializers/null.py) used by the ingress pipeline. |
| [`decoders/`](decoders/README.md) | Post-envelope semantic decode; includes **identity** [`NullDecoder`](decoders/null.py). |

Providers call [`ingest_to_parsed_messages`](ingress_pipeline.py) with a decapsulator class; **deserialize** and **decode** default to the null implementations. **Framing** and raw **JSON** are still often handled by the transport (e.g. MQTT `json.loads`) before `_parse_application_payload` runs.

## End-to-end flow (current)

1. **Transport** — `SensorTransport._process_payload` receives a wire-level payload.
2. **Provider** — `_parse_application_payload` uses [`ingest_to_parsed_messages`](ingress_pipeline.py) (deserialize → decapsulate → decode → parse) with vendor **decapsulators** and default **null** deserialize/decode.
3. **Normalizers** — For each `ParsedMessage`, `TRANSFORMER_MAP` selects a model; `from_parsed` + `to_stObservations` build STA tuples.
4. **FROST** — `frost_observation_upload` (outside this package).

See [`.cursor/ingress-pipeline-refactor-report.md`](../../../.cursor/ingress-pipeline-refactor-report.md) for diagrams and history.

## Adding a new sensor line

1. **Decapsulator** (if the app envelope is new) under `envelopes/`.
2. **Normalizer** class under `normalizers/` + register in [`normalizers/registry.py`](normalizers/registry.py).
3. **Provider** — implement `_parse_application_payload` (see [`providers/README.md`](../providers/README.md)).

## See also

- [`../providers/README.md`](../providers/README.md) — where `_parse_application_payload` lives.
- [`../transport/README.md`](../transport/README.md) — threading and `_process_payload`.

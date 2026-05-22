# Contributing checklist

Use this checklist when adding new ingestion capabilities to `rime`.

## Definitions

- IoT is the Internet of Things. Any device which is internet enabled and can communicate with other devices is part of the IoT.
- In IoT, data travels downstream from the IoT device to the client. An upstream source is any intermediate service (e.g., server) which is "closer" to the IoT source.
- A *transport mechanisim* is one or more network protocols, mechanisims and intermediate servers that are used to transfer data from an IoT device downstream to a client. Common examples are HTTP and MQTT.
- A *payload* is a useful component of data, usually an observation or message that an IoT device collects and sends to other devices.
- An *application server* is any upstream device which captures payloads and delivers, through some transport mechanism, downstream to a client.
- A *provider* is any device, infrastructure or application servers which enables the delivery of payloads downstream.
- An IoT payload is *encapsulated* by the transportation mechanism, which adds structure such as headers or trailers to the payload.
- Prior to encapsulation, the payload is transmitted in a native, *serialized wire-format* most often as a packets of bytes.
- Bytes must often be *decoded* into some other formats, such into text through UTF-8 decoding.

## Fast path: what should I change?

| If your change is... | Start here | You usually need to touch |
| --- | --- | --- |
| New data **transport mechanism** | [Transport checklist](#new-transport) | `src/rime/transport/`, then most likely a new one or more providers |
| New **upstream provider** using supported [`transport`](src/rime/transformers) classes | [Provider Checklist](#new-provider) | `src/rime/providers/`, `src/rime/transformers/decapsulators/`, provider tests |
| New **decapsulators** for payloads enveloped by some [`provider`](/src/rime/providers) | [Decapsulator checklist](#new-decapsulator) | `src/rime/transformers/decapsulators/`, provider hook, decapsulation tests |
| New payload **normalizers** for specific sensor models | [Sensor model checklist](#new-sensor-model) | `src/rime/transformers/normalizers/`, `ingest_registry.py`, model tests |
| Compoetely **new pipeline**: transport, new provider and new sensor model | Add new transport → provider → decapsulator → model | Multiple modules + docs + tests |

## What are you adding?

- [ ] **A fundamentally new data acquisition and transport mechanism**
  - Add a new transport under `src/rime/transport/` first, then build providers on top.
- [ ] **Only a new source provider using a supported transport mechanism**
  - Build a new provider under `src/rime/providers/`.
- [ ] **A new payload envelope shape**
  - Add a decapsulator under `src/rime/transformers/decapsulators/`.
- [ ] **A new supported sensor model**
  - Add/extend normalizer + ingest component wiring.

## New Transport

- [ ] Pick interaction model:
  - Poll-style (caller pulls on a schedule, e.g., HTTP) or
  - Subscription-style (source pushes events over a persistent connection, e.g., MQTT).
- [ ] Create transport module in the correct subtree (`transport/poll/` or `transport/subscription/`).
- [ ] Subclass `SensorTransport` (or one of its existing specializations when appropriate).
- [ ] Implement required abstract method(s):
  - Base contract: `_run(self) -> None`
  - If you expose a protocol-specific base class, define its abstract hooks (similar to `_pull_data` in `HTTPTransport` or `_auth` in `MQTTTransport`).
- [ ] Ensure `_run` forwards each wire message into `self._process_wire_message(wire_message)`.
- [ ] Respect lifecycle and failure semantics:
  - Honor `self._stop_event`
  - Use `self._exception_handler(...)`
  - Stop when retries exceed `max_retries`.
- [ ] Document the transport in `src/rime/transport/README.md`.

## New Provider

- [ ] Add `src/rime/providers/<name>.py`.
- [ ] Subclass the correct transport class, e.g.: `HTTPTransport`, or `MQTTTransport`.
- [ ] Implement `_decapsulate_wire(self, wire_message) -> DecapsulatedMessage` — usually a wrapper around a new or existing decapsulator.
- [ ] Implement provider auth method:
  - HTTP/MQTT provider still owns credential lookup and `_auth`.
- [ ] Implement any `@abstractmethods` in the parent class, e.g.: `HTTPTransport` requires `_pull_data(self) -> Any` and `_auth`.
- [ ] Optionally implement `_preflight(self) -> bool` for sanity checks.
- [ ] Re-export provider in `src/rime/providers/__init__.py`.
- [ ] Add/refresh provider docs in `src/rime/providers/README.md`.

## New Decapsulator

- [ ] Add module in `src/rime/transformers/decapsulators/`.
- [ ] Implement class that subclasses `Decapsulator`.
- [ ] Implement `decapsulate(wire_message: Any) -> DecapsulatedMessage`.
- [ ] Ensure the output contains:
  - `identified_payloads: list[IdentifiedPayload]` — one entry per logical sensor, each with `sensor_uuid` (the registry key) and `payload` (provider-independent native sensor data).
  - `envelope_metadata: EnvelopeMetadata | None` — `provider_timestamp`, `phenomenon_timestamp`, and any other provider-level context not embedded in the payload.
- [ ] Log a warning (do not raise) when `identified_payloads` is empty.
- [ ] Raise `MissingPayloadKeysError` on required-key shape failures; wrap unknown errors as `UnpackError`.
- [ ] Export class in `decapsulators/__init__.py`.
- [ ] Add/refresh docs in `decapsulators/README.md`.

## New Parser

Every sensor model requires a concrete `Parser`.  The parser is responsible for
field validation, key normalization, timestamp extraction, and ensuring that
`ObservationRecord.observations` contains only observation-ready fields.

- [ ] Add module in `src/rime/transformers/parsers/`.
- [ ] Implement class that subclasses `Parser`.
- [ ] Define `_REQUIRED_FIELDS` and validate them; raise `MissingPayloadKeysError` on missing keys.
- [ ] Implement `parse(identified: IdentifiedPayload, envelope: EnvelopeMetadata | None) -> ObservationRecord`.
- [ ] Ensure `ObservationRecord.observations` contains only physical observation fields (no timestamps, no metadata).
- [ ] Register in `INGEST_COMPONENT_MAP` under the relevant `SupportedSensors` key.

## New Sensor Model

- [ ] Add/extend normalizer class in `src/rime/transformers/normalizers/`, subclass `VendorObservationNormalizer`.
- [ ] Ensure field mapping and transforms are correct:
  - [ ] `NAME_TRANSFORM` — maps vendor field names to `ObservedProperties`.
  - [ ] `TRANSFORM` — per-field coercion callables (e.g. unix epoch → `datetime`).
- [ ] Register parser and normalizer in `src/rime/transformers/ingest_registry.py` via `INGEST_COMPONENT_MAP`.
- [ ] Ensure sensor config `sensor_model` matches `SupportedSensors` entry.
- [ ] Update docs in `src/rime/transformers/normalizers/README.md` and `src/rime/transformers/README.md`.

## Validation

- [ ] Add or update tests for:
  - decapsulation behavior,
  - provider integration behavior,
  - model ingest/normalization behavior.
- [ ] Run local checks/tests used by this repo.
- [ ] Verify docs and diagrams reflect the final pipeline names/paths.
- [ ] Confirm no stale references remain (e.g., old module names).


# Contributing checklist

Use this checklist when adding new ingestion capabilities to `rime`.

## Fast path: what should I change?

| If your change is... | Start here | You usually need to touch |
| --- | --- | --- |
| New upstream app using existing HTTP/MQTT patterns | Provider checklist | `src/rime/providers/`, `src/rime/transformers/decapsulators/`, provider tests |
| New acquisition mechanism (not just HTTP poll / MQTT subscribe) | Transport checklist | `src/rime/transport/`, then one or more providers |
| New envelope/input payload shape | Decapsulator checklist | `src/rime/transformers/decapsulators/`, provider hook, decapsulation tests |
| New sensor model already reachable from existing provider | Sensor model checklist | `src/rime/transformers/normalizers/`, `ingest_registry.py`, model tests |
| New vendor + new transport + new model | Do all in order: transport -> provider -> decapsulator -> model | Multiple modules + docs + tests |

## 0) Decide what you are adding

- [ ] **Only a new source application on existing HTTP/MQTT patterns**
  - Build a new provider under `src/rime/providers/`.
- [ ] **A fundamentally new data acquisition mechanism**
  - Add a new transport under `src/rime/transport/` first, then build providers on top.
- [ ] **A new payload envelope shape**
  - Add a decapsulator under `src/rime/transformers/decapsulators/`.
- [ ] **A new supported sensor model**
  - Add/extend normalizer + ingest component wiring.

## 1) If you need a new transport mechanism

- [ ] Pick interaction model:
  - Poll-style (caller pulls on a schedule) or
  - Subscription-style (source pushes events over a persistent connection).
- [ ] Create transport module in the correct subtree (`transport/poll/` or `transport/subscription/`).
- [ ] Subclass `SensorTransport` (or one of its existing specializations when appropriate).
- [ ] Implement required abstract method(s):
  - Base contract: `_run(self) -> None`
  - If you expose protocol-specific base class, define its abstract hooks (similar to `_pull_data` in `HTTPTransport` or `_auth` in `MQTTTransport`).
- [ ] Ensure `_run` forwards each payload into `self._process_payload(app_payload)`.
- [ ] Respect lifecycle and failure semantics:
  - Honor `self._stop_event`
  - Use `_exception_handler(...)`
  - Stop when retries exceed `max_retries`.
- [ ] Document the transport in `src/rime/transport/README.md`.

## 2) If you are adding a new provider

- [ ] Add `src/rime/providers/<name>.py`.
- [ ] Subclass the correct transport class:
  - `HTTPTransport` for polling providers
  - `MQTTTransport` for broker subscription providers.
- [ ] Implement `_decapsulate_application_payload(self, app_payload) -> list[DecapsulatedMessage]`.
- [ ] Implement provider auth method:
  - HTTP/MQTT provider still owns credential lookup and `_auth`.
- [ ] For HTTP providers, implement `_pull_data(self) -> Any`.
- [ ] Optionally implement `_preflight(self) -> bool` for config sanity checks.
- [ ] Set `auth_method: ClassVar[Literal["tokens", "credentials"]]`.
- [ ] Re-export provider in `src/rime/providers/__init__.py`.
- [ ] Add/refresh provider docs in `src/rime/providers/README.md`.

## 3) If you need a new decapsulator

- [ ] Add module in `src/rime/transformers/decapsulators/`.
- [ ] Implement class that subclasses `Decapsulator`.
- [ ] Implement `decapsulate(app_payload: Any) -> list[DecapsulatedMessage]`.
- [ ] Ensure each output message contains:
  - `sensor_id` for `sensor_registry` lookup
  - `payload`
  - optional `application_timestamp` and `phenomenon_timestamp`.
- [ ] Raise `MissingPayloadKeysError` on required-key shape failures; wrap unknown errors as `UnpackError`.
- [ ] Export class in `decapsulators/__init__.py`.
- [ ] Add/refresh docs in `decapsulators/README.md`.

## 4) If you are adding a new sensor model mapping

- [ ] Add/extend normalizer class in `src/rime/transformers/normalizers/` (subclass `VendorObservationTransformer`).
- [ ] Ensure field mapping and transforms are correct (`NAME_TRANSFORM`, optional `TRANSFORM`).
- [ ] Register transformer in `src/rime/transformers/ingest_registry.py` via `INGEST_COMPONENT_MAP`.
- [ ] Choose deserializer/decoder classes for that model:
  - `NullDeserializer` / `NullDecoder` if identity stages are sufficient.
- [ ] Ensure sensor config `sensor_model` matches `SupportedSensors` entry.
- [ ] Update docs in `src/rime/transformers/normalizers/README.md` and `src/rime/transformers/README.md`.

## 5) Validate before opening PR

- [ ] Add or update tests for:
  - decapsulation behavior,
  - provider integration behavior,
  - model ingest/normalization behavior.
- [ ] Run local checks/tests used by this repo.
- [ ] Verify docs and diagrams reflect the final pipeline names/paths.
- [ ] Confirm no stale references remain (e.g., old module names).


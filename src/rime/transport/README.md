# `transport`

Abstractions describing **how** sensor data moves from an upstream source
into the rime pipeline. This package is framework code: it changes
rarely, and only when adding support for a fundamentally new way of
communicating with a sensor application.

If you are integrating a new sensor application (Chirpstack, Helium,
Sigfox, ...) you almost certainly want
[`../providers/`](../providers/README.md) instead. You only need to add
something here when no existing transport fits — for example, a SeedLink
TCP stream, a CoAP poller, or a directory watcher.

## Architecture

```
transport/
├── base.py                  # SensorTransport (ABC) -- protocol-agnostic core
├── poll/                    # caller drives the rhythm; stateless requests
│   └── http.py              # HTTPTransport (ABC)
└── subscription/            # source pushes to caller; persistent connection
    ├── mqtt.py              # MQTTTransport (ABC)
    └── seedlink.py          # SeedLinkTransport (ABC, ObsPy SeedLink TCP)
```

The package is organised in two layers:

1. **Interaction model** (`poll/`, `subscription/`) — *who drives the data
   flow*. Polling means the caller asks on a schedule; subscription means
   the source pushes when something happens. These are the most stable
   architectural divisions because they are about control flow, not wire
   format.
2. **Protocol implementation** (`http.py`, `mqtt.py`, `seedlink.py`, ...) — the
   concrete abstract class that handles a specific wire protocol within an
   interaction model. Filesystem polling would land in `poll/filesystem.py`.

## Ingest pipeline (transport → FROST)

The pipeline runs in two tiers inside `SensorTransport._process_payload`.

### Application tier  *(transport / provider level)*

| Step | Hook | Default | Responsibility |
|------|------|---------|----------------|
| 1 | `_run` | — | Receive one wire payload from upstream; call `_process_payload`. |
| 2 | `_decode_wire` | identity | Convert raw bytes to a decoded form (e.g. base64 → bytes, bytes → UTF-8). |
| 3 | `_deserialize_wire` | identity (`json.loads` on MQTT) | Parse the decoded form into a Python object (JSON, CBOR, Protobuf, ...). |
| 4 | `_decapsulate_provider_payload` | **abstract** | Strip the provider envelope; return one `DecapsulatedMessage` per sensor reading. |

Steps 2 and 3 default to the identity on `SensorTransport`. Transport
subclasses override where needed: `MQTTTransport` overrides
`_deserialize_wire` with `json.loads`; SeedLink and HTTP leave both as
identity because their underlying libraries (ObsPy, lnetatmo) already return
Python objects.

### Model tier  *(per `DecapsulatedMessage`, keyed by sensor model)*

| Step | Component | Source | Responsibility |
|------|-----------|--------|----------------|
| 5 | `deserializer.deserialize` | `INGEST_COMPONENT_MAP[model]` | Any remaining payload-level deserialization. |
| 6 | `decoder.decode` | `INGEST_COMPONENT_MAP[model]` | Raw sensor readings → physical values. |
| 7 | `transformer.from_parsed` + `to_stObservations` | `INGEST_COMPONENT_MAP[model]` | Vendor fields → SensorThings Observation tuples. |
| 8 | `frost_observation_upload` | `SensorTransport` | Push each observation to FROST. |

## What `SensorTransport` owns

- Threading lifecycle: `start()`, `stop()`, `restart()`, `is_alive`.
- The shared processing pipeline: `_process_payload` orchestrates both
  tiers above, calling the application-tier hooks then the model-tier
  components, regardless of which transport is in use.
- Exception classification: `_exception_handler` returns `0` for
  transient errors and `1` for real failures, with `max_retries`
  governing when the transport gives up.
- Construction from YAML: `from_config` introspects the constructor
  signature and forwards matching keys; subclasses rarely need to
  override.

What it intentionally does **not** own:

- **Authentication.** Credential storage and resolution differ enough
  between providers (OAuth, API keys, TLS certificates, no auth) that
  forcing a shape here would be the wrong abstraction. Providers handle
  their own auth.
- **Sensor-specific decoding.** That is the
  [`transformers`](../transformers/) and
  [`providers`](../providers/README.md) concern.

## Adding a new transport

When adding a new transport you are answering two questions:

1. *Is this poll or subscription?* — pick the right subdirectory.
2. *What is the protocol's lifecycle?* — implement `_run` (and helpers
   such as `_connect`, `_pull_data`) to drive `_process_payload`. Override
   `_decode_wire` and/or `_deserialize_wire` if the wire format requires
   it; leave them as identity if the underlying library already returns a
   Python object.

Then export from `transport/__init__.py` and document the contract in the
module docstring.

## Adding a new interaction model

This is rarer. You would only do this if a new model fundamentally
differs from poll-and-subscribe — for example, a one-shot batch
ingestion that runs once and exits. Create a new subdirectory under
`transport/` with its own protocol files inside.

## See also

- [`../providers/`](../providers/README.md) — concrete integrations with
  specific applications, built on top of these transports.
- [`../transformers/`](../transformers/) — payload normalisation and
  conversion to SensorThings observations.
- [`../monitor.py`](../monitor.py) — health monitoring; transports report
  payload counts and the monitor restarts dead threads.

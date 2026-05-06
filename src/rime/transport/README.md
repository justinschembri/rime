# `transport`

Abstractions describing **how** sensor data moves from an upstream source
into the RIME pipeline. This package is framework code: it changes
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
    └── mqtt.py              # MQTTTransport (ABC)
```

The package is organised in two layers:

1. **Interaction model** (`poll/`, `subscription/`) — *who drives the data
   flow*. Polling means the caller asks on a schedule; subscription means
   the source pushes when something happens. These are the most stable
   architectural divisions because they are about control flow, not wire
   format.
2. **Protocol implementation** (`http.py`, `mqtt.py`, ...) — the concrete
   abstract class that handles a specific wire protocol within an
   interaction model. SeedLink would land in `subscription/seedlink.py`;
   filesystem polling would land in `poll/filesystem.py`.

## What `SensorTransport` owns

- Threading lifecycle: `start()`, `stop()`, `restart()`, `is_alive`.
- The shared processing pipeline: `_process_payload` runs provider
  `_decapsulate_application_payload`, model-component lookup (`INGEST_COMPONENT_MAP`),
  deserialize/decode/parse + STA normalizers, and Frost push for each
  payload, regardless of transport.
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
2. *What is the protocol's lifecycle?* — implement `_run` (and any
   helper methods such as `_connect`, `_pull_data`) in a way that drives
   the shared `_process_payload` pipeline.

Skeleton:

```python
# transport/subscription/seedlink.py
from abc import abstractmethod
from ..base import SensorTransport


class SeedLinkTransport(SensorTransport):
    """Long-lived SeedLink TCP stream."""

    def __init__(self, app_name: str, host: str, *, max_retries: int = 3):
        super().__init__(app_name, max_retries=max_retries)
        self.host = host

    @abstractmethod
    def _auth(self) -> None:
        """Configure stream credentials. May be a no-op."""
        ...

    def _connect(self) -> None:
        """Open the SeedLink stream and start receiving packets."""
        ...

    def _run(self) -> None:
        """Drain packets and feed them into self._process_payload."""
        ...
```

Then export it from `transport/__init__.py` and document the contract in
the module docstring.

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

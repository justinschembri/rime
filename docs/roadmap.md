# RIME Architecture Roadmap

Internal working document. This is a living record of where we are going and why — not a polished spec.

---

## Where we are today

The current codebase is a single Python application (`packages/rime-ingest/`) that:

- Polls or subscribes to external IoT providers (Netatmo via HTTP, TTS via MQTT).
- Runs a decode → deserialize → decapsulate → normalise pipeline on each payload.
- POSTs observations to a FROST SensorThings server running in Docker.
- Is operated entirely via the `rime` CLI and a set of Docker Compose files under `deploy/`.
- Has a static read-only browser dashboard (`web/rime/`) served through Tomcat.

The deployment is Docker Compose only. Auth is fragmented across three independent systems (Tomcat BasicAuth, FROST BasicAuth, Mosquitto ACL files). The Mosquitto integration is a stub. There is no web-based management interface.

---

## Target architecture

We are splitting the application into three distinct, separately deployable services. FROST remains a fully internal service with no external exposure.

```
External world
  │
  ├── External providers (Netatmo, TTS, …)
  │       └──► rime-ingest ──────────────────────► FROST (internal)
  │                  ▲
  ├── IoT devices ───► rime-server-{http,mqtt,…} ──►┘
  │
  └── Operators ──────────────────────────────────► rime-ctrl (web UI)
                                                         │
                                                  manages ingest config
                                                  manages server config
                                                  reads FROST lightly
```

### rime-ingest

This is largely the current application, refactored. Its job is to consume data from providers — both external (Netatmo, TTS) and internal (rime-server cluster) — and push observations to FROST.

Key characteristics:

- **Stateless**: ingest reads its config on startup and does not hold mutable state that needs to be commanded at runtime.
- **FROST is the source of truth** for what is actually provisioned. YAML sensor config files are the *desired state*. On startup, ingest reconciles: it ensures the FROST database reflects the declared YAML configuration (creating missing entities, skipping existing ones). This is the GitOps framing.
- Ingest treats internal rime-server containers as providers: it polls `rime-server-http` the same way it polls Netatmo, and subscribes to `rime-server-mqtt`'s broker the same way it subscribes to TTS. No special IPC layer is needed — the existing transport mechanisms are reused, just pointed internally.
- **Structured logs replace `netmon`**: rather than the current `netmon.report` loop, ingest should emit structured, machine-readable log lines per transport event (payload received, decode error, FROST upload success/failure, etc.). Ctrl consumes these for health monitoring.

### rime-server cluster

Dumb protocol forwarders. A device connects to a rime-server endpoint; the server authenticates it and makes the raw wire payload available for ingest to consume. No interpretation of payloads happens here.

Planned server types:

- `rime-server-http` — devices POST sensor data to an HTTP endpoint
- `rime-server-mqtt` — an MQTT broker that devices publish to (replaces the current Mosquitto stub)
- `rime-server-seedlink` — *would-have*; a SeedLink server that seismic instruments connect to

The current Mosquitto integration is inadequate for this role because it has no runtime management API. We intend to replace it with a broker that exposes a proper REST management API (EMQX is the leading candidate). This is deferred but should inform how we design the `rime-ctrl` server management interface — we should not build against Mosquitto-specific mechanisms.

### rime-ctrl

The control plane. A web application (backend API + frontend) through which operators manage the rime deployment. This is the primary near-term deliverable.

Its scope covers three functional areas:

**1. Sensor arrangement management (FROST / STA operations)**

Operators create, inspect, update, and delete sensor arrangements through the UI. Under the hood, ctrl:

- Writes or updates YAML sensor config files (the desired-state record).
- For deletions, also issues the corresponding DELETE to FROST directly — if we only removed the YAML, ingest would recreate the entity on next startup.
- Reads FROST to show what is actually provisioned (actual state, as distinct from desired state).
- Manually triggering an ingest reconciliation restart is the operator's explicit action after config changes.

**2. Ingest health monitoring**

Ctrl monitors the health of the ingestion pipeline by two complementary means:

- **FROST-derived health (MVP)**: query each Datastream's most recent observation timestamp. Staleness beyond a configurable threshold indicates that transport is degraded. No IPC required.
- **Structured log consumption (next iteration)**: ingest emits structured JSON log lines. Ctrl reads from a shared log volume or a log stream. This provides granular diagnostics: connection errors, decode failures, queue depth, per-transport event rates.

**3. Transport and server management**

Operators configure which providers and transports are active, and manage device credentials for the server cluster (adding a new MQTT device, opening an HTTP ingestion endpoint, etc.). The interface for server management will be designed against the final broker's management API, not Mosquitto's.

---

## Confirmed architectural decisions

| Topic | Decision |
|---|---|
| Ingest lifecycle | Stateless; config is read on startup; reconciliation is triggered by manual restart |
| Source of truth | FROST DB is authoritative runtime state; YAMLs are desired state |
| YAML on deletion | Ctrl must DELETE from both YAML and FROST; YAML-only removal would cause recreation |
| Internal server → ingest channel | Ingest uses existing transport mechanisms pointed at internal servers; no special bus |
| FROST exposure | Completely internal; no external port; all FROST writes come from ingest |
| Ctrl FROST access | Read (actual state display) + light write (DELETE on sensor removal); not a FROST proxy |
| Auth | Single identity provider long-term; current per-service auth is a known mess; deferred |
| Mosquitto | Current implementation is a stub; replacement with a proper managed broker is planned |
| SeedLink server | Would-have; design the slot but do not implement yet |
| Ingest health | Structured logs from ingest; FROST-derived staleness for MVP |
| Frontend (ctrl) | HTMX vs SPA left open for exploration; do not over-commit before we build |
| Package structure | Monorepo with `uv` workspaces as the long-term target (see below) |

---

## Package and repository structure (target)

We are moving toward a monorepo with multiple distinct packages sharing a common core. The top-level layout we are working toward:

```
rime/
  packages/
    rime-core/        # shared: STA types, sensor config schema, transport interfaces
    rime-ingest/      # current application, refactored; depends on rime-core
    rime-ctrl/        # new: control plane API + web UI; depends on rime-core
    rime-servers/     # new: server implementations; depends on rime-core
    rime-edge/        # reference edge producers, by language (python/, c/, …)
  deploy/             # Compose files, init scripts, secrets layout
  docs/               # this file lives here
  docs/protocols/     # normative wire contracts (e.g. rime-http-ingest-v1.md)
  tests/              # integration tests spanning packages
```

`rime-edge` is intentionally **not** a dependency of ingest. Edge hosts deploy
from per-language release tarballs or sparse git checkout — not by cloning the
full platform repo. See [`packages/rime-edge/README.md`](../packages/rime-edge/README.md).

Each package builds from its own directory (`packages/rime-ingest/Dockerfile`, etc.).
`deploy/` compose files wire services together at runtime.

Within `rime-ingest`, the transport taxonomy becomes:

```
transport/
  client/
    poll/             # outbound HTTP polling (Netatmo)
    subscription/     # outbound subscribe (MQTT/TTS, SeedLink client)
  server/             # inbound: consumes from internal rime-server containers
    http.py
    mqtt.py           # MQTTTransport variant pointed at internal broker
    seedlink.py       # would-have
```

The monorepo split is in progress. `packages/rime-ingest/` holds the current application; the remaining packages (`rime-ctrl`, `rime-servers`, `rime-core`) are added as their scope becomes clear. The full workspace split happens when `rime-ctrl` is being built out in earnest and the shared type boundary is stable.

---

## Near-term focus: rime-ctrl

This is what we are building first. Everything else (rime-server refactor, broker replacement, monorepo split) is downstream of having a working control plane.

### What rime-ctrl needs to do at MVP

- **Sensor listing**: read FROST and display all provisioned Things, their Datastreams, and last observation timestamps.
- **Sensor creation**: walk an operator through the same information currently gathered by `rime generate-config`; write a YAML; notify the operator to restart ingest.
- **Sensor deletion**: remove the YAML and issue a FROST DELETE.
- **YAML validation**: expose the same validation logic as `rime validate` in the UI.
- **Health overview**: per-transport staleness view derived from FROST observation timestamps.
- **Structured log view**: read ingest's structured log output from a shared volume; display recent events per transport.

### What rime-ctrl defers

- Server management (device credential provisioning, topic management) — depends on broker choice.
- Auth and role separation — deferred deliberately; we will add it as a distinct phase.
- Multi-instance ingest orchestration — not relevant until we have more than one ingest container.

### Backend

FastAPI. It can access the shared sensor config volume directly (read/write YAMLs), call FROST over the internal Docker network, and read the ingest log volume. No database of its own at MVP.

### Frontend

Left open for now — we will explore the HTMX vs SPA question during early implementation. Do not couple the backend API design to either choice.

---

## Deployment shape (near-term Compose delta)

The immediate step is adding `rime-ctrl` as a new service alongside the existing `python-app`. Rough shape:

```yaml
rime-ctrl:
  build: ./packages/rime-ctrl     # or wherever it lives
  ports:
    - "8001:8001"
  volumes:
    - sensor_configs:/sensor_configs   # shared with rime-ingest
    - ingest_logs:/ingest_logs         # read ingest structured logs
  environment:
    - FROST_URL=http://web:8080/FROST-Server
  secrets:
    - frost_credentials
```

No Docker socket access for MVP — manual restarts are explicit operator actions, not automated by ctrl.

---

## Open / deferred items

- **Broker replacement**: Mosquitto → EMQX (or alternative). Prerequisite for real server management in ctrl.
- **Auth unification**: single identity provider (Keycloak, Authentik, or a lightweight custom JWT issuer). Affects ctrl API, rime-server auth layer, and eventually FROST access.
- **Structured log schema**: we need to define the JSON log line format ingest will emit before ctrl can reliably consume it. This should be done as part of the netmon replacement work.
- **Frontend choice**: HTMX + Jinja2 vs. SPA — explore during rime-ctrl early implementation.
- **Monorepo split**: when rime-ctrl reaches a stable shape and the shared type boundary is clear.
- **Load-balanced ingest**: multiple ingest instances behind a load balancer. Requires ctrl to assign provider partitions to instances (likely via separate config sets per instance). Not needed until we have scale pressure.
- **SeedLink server**: slot is reserved in the transport taxonomy; implement when there is a concrete seismic instrument to connect.
- **Kubernetes**: current Compose deployment is adequate. Revisit when multi-instance ingest or multi-region deployment becomes a real requirement.

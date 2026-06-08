# `rime-edge`

Reference **edge producers** — small programs that run next to a sensor (or on a
field gateway) and push `wire_message` payloads to a central
[`rime-server-http`](../rime-servers/README.md) instance. They are clients of the
platform, not part of the ingest pipeline.

Ingest, decapsulation, and FROST upload happen centrally. Edge code only needs to
observe a local data source and `POST` bytes that match the
[HTTP ingest protocol](../../docs/protocols/rime-http-ingest-v1.md).

## Layout

Edge implementations are grouped **by language**, not by sensor type. A given
deployment picks one language tree and one or more scripts from it.

```
rime-edge/
├── README.md           # this file
└── python/             # reference Python producers (pip / uv installable)
```

Additional language trees (`c/`, `rust/`, …) follow the same pattern when needed.

Each language directory is **self-contained**: its own build file, dependencies,
and install instructions. Nothing under `rime-edge/` may import `rime-ingest`.

## Choosing an implementation

| Directory | When to use |
|-----------|-------------|
| [`python/`](python/README.md) | Prototyping, Linux gateways with Python, integration tests against the monorepo |

Sensor-specific logic (filesystem tail, serial port, vendor SDK) lives as
**scripts or small modules inside the chosen language tree**, not as shared
rime-core libraries.

## Deploying from a monorepo (without cloning all of rime)

The full `rime` repository is oriented at the central stack (ingest, servers,
deploy). Edge hosts usually need only a few files. Options:

### 1. Release tarball (recommended for production)

CI can publish per-language artifacts, e.g. `rime-edge-python-<version>.tar.gz`
containing only `packages/rime-edge/python/` plus the protocol doc.

### 2. Git sparse checkout

Clone just the edge subtree:

```bash
git clone --filter=blob:none --sparse https://github.com/<org>/rime.git
cd rime
git sparse-checkout set packages/rime-edge/python docs/protocols
```

Useful for developers; still requires git on the edge host.

### 3. Copy via rsync/scp from a dev machine

```bash
rsync -av packages/rime-edge/python/ user@gateway:/opt/rime-edge/
```

Fine for lab and one-off gateways.

### 4. Container image (optional)

A minimal `rime-edge-python` image can wrap one script. Heavier than a tarball
but familiar if the gateway already runs Docker.

### 5. Separate repository (later)

If edge implementations multiply (many languages, OTA, device fleets), split
`rime-edge` into its own repo and treat
[`docs/protocols/rime-http-ingest-v1.md`](../../docs/protocols/rime-http-ingest-v1.md)
as the normative contract. The monorepo keeps the reference implementations and
contract tests until then.

## Relationship to other packages

```
  [sensor] → local FS / bus
        ↓
  rime-edge/<lang>/script   ──POST──►  rime-server-http  ◄──poll──  rime-ingest  →  FROST
```

| Package | Role |
|---------|------|
| `rime-edge` | Push client (this tree) |
| `rime-servers` | Buffer + ingress API |
| `rime-ingest` | Pull, decapsulate, upload |
| `rime-core` | Shared types (platform only; edge should not depend on it) |

## See also

- [HTTP ingest protocol v1](../../docs/protocols/rime-http-ingest-v1.md)
- [Architecture roadmap](../../docs/roadmap.md)

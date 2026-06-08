# `rime-edge` — Python

Reference edge producers implemented in Python. Intended for gateways that
already run Python 3.12+ and for monorepo integration tests.

## Scope

- Small scripts (filesystem tail, one-shot file upload, stdin pipe).
- HTTP delivery via `requests` or stdlib `urllib` — no dependency on
  `rime-ingest`.
- Configuration via env vars or a local YAML/JSON file on the edge host.

Implementations will be added here as concrete sensor integrations are defined.
Until then, this directory defines the packaging and deployment contract only.

## Install on an edge host

**From a release tarball** (preferred — see parent
[`../README.md`](../README.md)):

```bash
tar -xzf rime-edge-python-<version>.tar.gz -C /opt/rime-edge
cd /opt/rime-edge
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**From a monorepo checkout** (development):

```bash
cd packages/rime-edge/python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configuration (illustrative)

Edge scripts are expected to read settings from the environment:

| Variable | Purpose |
|----------|---------|
| `RIME_SERVER_URL` | Base URL of `rime-server-http` |
| `RIME_APP_ID` | Application id (routes to ingest application config) |
| `RIME_API_KEY` | Ingress credential |
| `RIME_WATCH_PATH` | File or directory to observe (filesystem producers) |

Exact names will be fixed when the first producer lands.

## Protocol

All HTTP producers must conform to
[rime-http-ingest-v1](../../../docs/protocols/rime-http-ingest-v1.md).

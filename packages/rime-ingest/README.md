# `rime-ingest`

Ingest layer for the rime platform: polls/subscribes to upstream providers,
runs the decode → decapsulate → normalize pipeline, and uploads observations
to FROST.

This package is **self-contained**. Runtime configuration and secrets are
mounted by `deploy/` compose files — ingest does not depend on a monorepo
layout inside the container.

## Build and run

```bash
cd packages/rime-ingest
uv sync
rime setup
rime   # start ingest (or: python -m rime_ingest.main)
```

## Docker

Built from this directory only:

```bash
docker build -t rime-ingest .
```

In production, use the compose overlays under `deploy/` at the monorepo root.
Compose mounts host paths into the container runtime directories below.

## Runtime paths

When `CONTAINER_ENVIRONMENT=true` (set in the Dockerfile), defaults are:

| Env var | Container default | Purpose |
|---------|-------------------|---------|
| `SENSOR_CONFIG_PATH` | `/app/runtime/sensor_configs` | Sensor YAML configs |
| `APPLICATION_CONFIG_FILE` | `/app/runtime/application-configs.yml` | Application config |
| `RIME_CREDENTIALS_DIR` | `/app/runtime/secrets/credentials` | Provider credentials |
| `RIME_TOKENS_DIR` | `/app/runtime/secrets/tokens` | OAuth token files |
| `RIME_LOGS_DIR` | `/app/logs` | Log output |

Locally (no container), defaults fall back to `packages/rime-ingest/runtime/`.

When developing inside the monorepo, point at the shared `deploy/` configs:

```bash
export SENSOR_CONFIG_PATH=../../deploy/sensor_configs
export APPLICATION_CONFIG_FILE=../../deploy/application-configs.yml
export RIME_CREDENTIALS_DIR=../../deploy/secrets/credentials
export RIME_TOKENS_DIR=../../deploy/secrets/tokens
```

FROST connectivity uses `FROST_ENDPOINT` or `FROST_ROOT_URL` + `FROST_VERSION`.

## Stack lifecycle (`rime start` / `rime stop`)

These commands invoke scripts in `deploy/` and require:

```bash
export RIME_COMPOSE_DIR=/path/to/rime/deploy
```

Prefer running `docker compose` from `deploy/` directly in production.

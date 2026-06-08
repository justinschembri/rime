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

When developing inside the monorepo, local defaults automatically use
`deploy/` (sensor configs, credentials, application config). No extra env vars
are needed for `rime setup` or `rime validate`.

Standalone installs (without a sibling `deploy/` directory) fall back to
`packages/rime-ingest/runtime/`.

FROST connectivity uses `FROST_ENDPOINT` or `FROST_ROOT_URL` + `FROST_VERSION`.

## Stack lifecycle (`rime start` / `rime stop`)

These commands invoke scripts in `deploy/`. From a monorepo checkout,
`deploy/` is discovered automatically. Otherwise set:

```bash
export RIME_COMPOSE_DIR=/path/to/deploy
```

Prefer running `docker compose` from `deploy/` directly in production.

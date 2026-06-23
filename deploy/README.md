# Deployment

`rime` may be deployed in two modes:

- **Ingest-only** — runs `rime-ingest` only; pushes observations to an external FROST server.
- **Full-stack** — runs `rime-ingest`, FROST, PostgreSQL, and Mosquitto together.

It is assumed that if you are deploying this application you have access (e.g.,
hostaddress, credentials, OAuth tokens, etc.) to observations from an upstream
provider such as a Netatmo HTTP Server, a TheThingsNetwork MQTT Broker or a
generic SeedLink provider.

---

## Common Setup: Provider Configurations

Whatever your deployment path you must specify the applications you have access
to. The `rime-ingest` service uses this configuration file to know what upstream
providers to contact and how to communicate.

By default, docker compose will mount the file `application-configs.yml` found
in this deployment directory to `/app/runtime/application-configs.yml`. You can
override this by specifying the path in the `APPLICATION_CONFIG_FILE` env
variable in a `.env` placed in this deployment directory.

The format of the application YML is as follows:

```yaml
applications:
  <application-name>:
    provider: <supported-provider>
      max-retries: <int>
      <provider-specific-key>: <provider-specific-value>
      ...
```

## Common Setup: Provider Credentials

Providers often need authentication keys or tokens. API keys are static while
OAuth tokens need to be rewritten and are thus handled differently by Docker.

Static credential keys are kept in `application_credentials.json` in
`./secrets/credentials/` and mounted read-only into the container. You can
override this path by setting `CREDENTIALS_DIR` in a `.env` in this deployment
directory. The format of this file is:

```json
{
  "<application-name>": {
    "api_key": "<application-key>"
  }
}
```

OAuth tokens, which the container runtime may overwrite, are stored in
`./secrets/tokens/`. A `json` file is required for each application; the schema
depends on the `Provider` implementation. The filename should match the
application name used elsewhere. The tokens directory is bind-mounted (not a
named volume) so that tokens persist and remain accessible to the host.

## Common Setup: Sensor Configurations

You will need to set up the configs that define each Sensor according to the
SensorThings API model.

By default, docker compose will mount the directory `sensor_configs` found in
this deployment directory to `/app/runtime/sensor_configs/`. You can override
this by specifying `SENSOR_CONFIG_PATH` in a `.env` in this directory.

---

## Ingest-only Deployment

If you only need the ingestion pipeline and already have a FROST server, set
`FROST_ENDPOINT` in a `.env` file in this directory:

```dotenv
FROST_ENDPOINT=https://your-frost-server/FROST-Server
```

Then start only the `rime-ingest` service:

```sh
docker compose -f docker-compose.base.yml up --no-deps rime-ingest -d
```

---

## Full Stack Deployment

The full stack brings up `frost`, `database`, `mosquitto`, and `rime-ingest`
together. Two variants are supported depending on whether FROST authentication
is required.

### Without authentication (anonymous read and write)

```sh
docker compose -f docker-compose.base.yml up -d
```

FROST allows anonymous reads by default (`FROST_ALLOW_ANONYMOUS_READ=true`).
No `frost_credentials.json` is strictly required in this mode.

### With authentication

```sh
docker compose -f docker-compose.base.yml -f docker-compose.auth.yml up -d
```

The `auth` overlay enables FROST's BasicAuth provider and runs `init-db.sh`
to replace the default FROST user credentials with the values from
`frost_credentials.json`. The `FROST_REQUIRE_READ_AUTH` and
`FROST_REQUIRE_WRITE_AUTH` variables control which credential pairs are
updated (both default to `true`).

---

## Environment Variables

All variables are optional and have defaults. Place overrides in a `.env` file
in this deployment directory.

### `frost` service

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `FROST_URL` | Service root URL that FROST uses when building entity URLs. Must be the publicly reachable address. | `http://localhost:8080/FROST-Server` |
| `FROST_BIND_PORT` | Host port to bind the FROST HTTP interface to. | `8080` |
| `FROST_ALLOW_ANONYMOUS_READ` | Whether unauthenticated clients may read from FROST. | `true` |

### `rime-ingest` service

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `FROST_ENDPOINT` | FROST endpoint that `rime-ingest` pushes observations to (no version stem). | `http://frost:8080/FROST-Server` |
| `FROST_VERSION` | FROST API version stem appended to `FROST_ENDPOINT`. | `v1.1` |
| `CREDENTIALS_DIR` | **Host** path bind-mounted to `/app/runtime/secrets/credentials`. | `./secrets/credentials` |
| `TOKENS_PATH` | **Host** path bind-mounted to `/app/runtime/secrets/tokens`. | `./secrets/tokens` |
| `SENSOR_CONFIG_PATH` | **Host** path bind-mounted to `/app/runtime/sensor_configs`. | `./sensor_configs` |
| `APPLICATION_CONFIG_FILE` | **Host** path bind-mounted to `/app/runtime/application-configs.yml`. | `./application-configs.yml` |

### `database` service (auth overlay only)

These control which credential pairs `init-db.sh` replaces in the FROST auth
tables. They are only meaningful when using `docker-compose.auth.yml`.

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `FROST_REQUIRE_READ_AUTH` | Replace the default FROST `read` user credentials. | `true` |
| `FROST_REQUIRE_WRITE_AUTH` | Replace the default FROST `write` user credentials. | `true` |

---

## Secrets

Secrets are passed to containers as Docker secrets (files under
`./secrets/credentials/`). This directory is gitignored. Create each file
before first launch.

### `postgres_credentials.json` — required

Used by `database` and `frost`.

```json
{
  "postgres_user": "<db-username>",
  "postgres_password": "<db-password>"
}
```

### `frost_credentials.json` — required for auth overlay

Used by `database` (to update FROST auth tables) and `rime-ingest` (to
authenticate pushes). Only the pairs corresponding to enabled auth flags need
to be populated.

```json
{
  "frost_read_user": "<read-username>",
  "frost_read_password": "<read-password>",
  "frost_write_user": "<write-username>",
  "frost_write_password": "<write-password>"
}
```

### `mqtt_credentials.json` — required

Used by `mosquitto` to create users, passwords, and ACLs at startup.

```json
[
  {
    "username": "<mqtt-username>",
    "password": "<mqtt-password>",
    "topics": [
      { "name": "<topic>", "perm": "read" },
      { "name": "<topic>", "perm": "write" }
    ]
  }
]
```

Valid `perm` values are `read`, `write`, and `readwrite`.

### `application_credentials.json` — required

Used by `rime-ingest` for provider API keys. See
[Common Setup: Provider Credentials](#common-setup-provider-credentials).

### `tomcat-users.xml` — required for full stack

Mounted into the Tomcat configuration for the `frost` service web application.
Place it at `./secrets/credentials/tomcat-users.xml`.

#!/bin/sh
# PostgreSQL first-time setup for FROST Basic Auth: after FROST creates USERS /
# USER_ROLES, replace default admin/read/write credentials with frost_credentials.

export POSTGRES_USER=$(awk -F'"' '/"postgres_user"/ {print $4}' /run/secrets/postgres_credentials)
export POSTGRES_PASSWORD=$(awk -F'"' '/"postgres_password"/ {print $4}' /run/secrets/postgres_credentials)

FROST_SERVICE_URL="${FROST_SERVICE_URL:-http://frost:8080/FROST-Server/v1.1}"
set -e
/usr/local/bin/docker-entrypoint.sh postgres &

until pg_isready -h localhost -U "${POSTGRES_USER}" -d sensorthings; do
    echo "Waiting for PostgreSQL to be ready"
    sleep 2
done

# FROST must be up and have run auth liquibase before USERS exists.
until wget -q --spider "${FROST_SERVICE_URL}/Datastreams" 2>/dev/null; do
    echo "Waiting for FROST to be ready at ${FROST_SERVICE_URL}"
    sleep 5
done

if [ "${auth_requireReadAuth:-}" = "true" ]; then
# the first request builds the USERS table
wget --header="Authorization: Basic $(echo -n 'username:password' | base64)" -O Datastreams.json http://frost:8080/FROST-Server/v1.1/Datastreams
export FROST_READ_USER=$(awk -F'"' '/"frost_read_username"/ {print $4}' /run/secrets/frost_credentials)
export FROST_READ_PASSWORD=$(awk -F'"' '/"frost_read_password"/ {print $4}' /run/secrets/frost_credentials)

psql -U "${POSTGRES_USER}" -d sensorthings <<EOF
UPDATE "USERS"
SET "USER_PASS" = '${FROST_READ_PASSWORD}'
WHERE "USER_NAME" = 'read';

UPDATE "USER_ROLES"
SET "USER_NAME" = '${FROST_READ_USER}'
WHERE "USER_NAME" = 'read';

UPDATE "USERS"
SET "USER_NAME" = '${FROST_READ_USER}'
WHERE "USER_NAME" = 'read';
EOF
fi

if [ "${auth_requireWriteAuth:-}" = "true" ]; then
# the first request builds the USERS table
wget --header="Authorization: Basic $(echo -n 'username:password' | base64)" -O Datastreams.json http://frost:8080/FROST-Server/v1.1/Datastreams
export FROST_WRITE_USER=$(awk -F'"' '/"frost_write_username"/ {print $4}' /run/secrets/frost_credentials)
export FROST_WRITE_PASSWORD=$(awk -F'"' '/"frost_write_password"/ {print $4}' /run/secrets/frost_credentials)

psql -U "${POSTGRES_USER}" -d sensorthings <<EOF
UPDATE "USERS"
SET "USER_PASS" = '${FROST_WRITE_PASSWORD}'
WHERE "USER_NAME" = 'write';

UPDATE "USER_ROLES"
SET "USER_NAME" = '${FROST_WRITE_USER}'
WHERE "USER_NAME" = 'write';

UPDATE "USERS"
SET "USER_NAME" = '${FROST_WRITE_USER}'
WHERE "USER_NAME" = 'write';
EOF
fi

echo "Database initialization complete."
wait $!

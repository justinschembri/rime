#!/bin/sh
# startup the full production stack
MODE=${1:-public}  # default to public

if [ "$MODE" = "private" ]; then
    APP_COMPOSE="./docker-compose.app.yml"
else
    APP_COMPOSE="./docker-compose.app-public.yml"
fi

docker compose \
  -p rime-production \
  -f ./docker-compose.base.yml \
  -f ./docker-compose.auth.yml \
  -f ./docker-compose.persistent.yml \
  -f "$APP_COMPOSE" \
  up -d

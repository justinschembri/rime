#!/bin/sh
docker compose \
  -p rime-production \
  -f ./docker-compose.base.yml \
  -f ./docker-compose.auth.yml \
  up -d

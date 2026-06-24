#!/bin/sh
docker compose \
  -p rime-production \
  -f ./docker-compose.base.yml \
  up -d

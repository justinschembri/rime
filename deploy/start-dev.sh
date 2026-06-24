#!/bin/sh
docker compose \
  -p rime-dev \
  -f ./docker-compose.base.yml
  up -d

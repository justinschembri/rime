#!/bin/sh
docker compose -p rime-dev down --remove-orphans -v
docker volume rm rime-dev_postgis_volume


#!/bin/sh
# stop the full production stack
# Uses project name to stop regardless of which compose files were used
docker compose -p rime-production down

#!/usr/bin/env python3
"""Watch a filesystem path and POST changes to rime-server-http.

Reads configuration from environment variables (see deploy/examples/edge.env.example).
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from watchfiles import Change, watch

from rime_edge.client import RimeHttpClient
from rime_edge.config import EdgeConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rime-edge.watch_file")


def _read_tail(path: Path, offset: int) -> tuple[bytes, int]:
    data = path.read_bytes()
    if offset > len(data):
        offset = 0
    chunk = data[offset:]
    return chunk, len(data)


def _read_snapshot(path: Path) -> bytes:
    return path.read_bytes()


def _push_chunk(client: RimeHttpClient, config: EdgeConfig, body: bytes) -> None:
    if not body:
        return
    client.push(
        body,
        sensor_uuid=config.sensor_uuid,
        content_type=config.content_type,
        emitted_at=datetime.now(timezone.utc),
    )


def run_tail(config: EdgeConfig, client: RimeHttpClient) -> None:
    path = config.watch_path
    if not path.exists():
        raise SystemExit(f"Watch path does not exist: {path}")

    offset = path.stat().st_size
    logger.info("Tailing %s from offset %d", path, offset)

    pending = False
    last_event = 0.0
    while True:
        if pending and (time.monotonic() - last_event) >= config.debounce_seconds:
            chunk, offset = _read_tail(path, offset)
            _push_chunk(client, config, chunk)
            pending = False

        for changes in watch(path.parent, stop_event=None, step=config.poll_interval_ms):
            for change, changed_path in changes:
                if Path(changed_path) != path:
                    continue
                if change not in {Change.modified, Change.added}:
                    continue
                pending = True
                last_event = time.monotonic()
            break


def run_snapshot(config: EdgeConfig, client: RimeHttpClient) -> None:
    path = config.watch_path
    if not path.exists():
        raise SystemExit(f"Watch path does not exist: {path}")

    logger.info("Watching %s in snapshot mode", path)
    pending = False
    last_event = 0.0
    while True:
        if pending and (time.monotonic() - last_event) >= config.debounce_seconds:
            _push_chunk(client, config, _read_snapshot(path))
            pending = False

        for changes in watch(path.parent, stop_event=None, step=config.poll_interval_ms):
            for change, changed_path in changes:
                if Path(changed_path) != path:
                    continue
                if change not in {Change.modified, Change.added}:
                    continue
                pending = True
                last_event = time.monotonic()
            break


def main() -> None:
    config = EdgeConfig.from_env()
    if not config.watch_path.parent.exists():
        raise SystemExit(f"Watch directory does not exist: {config.watch_path.parent}")

    client = RimeHttpClient(
        server_url=config.server_url,
        app_id=config.app_id,
        api_key=config.api_key,
    )

    logger.info(
        "Starting edge watcher app=%s sensor=%s mode=%s",
        config.app_id,
        config.sensor_uuid,
        config.watch_mode,
    )

    if config.watch_mode == "tail":
        run_tail(config, client)
    else:
        run_snapshot(config, client)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped.")
        sys.exit(0)

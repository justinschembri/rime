#!/usr/bin/env python3
"""Watch a filesystem path and POST changes to rime-server-http.

Reads configuration from environment variables (see deploy/examples/edge.env.example).
Set RIME_DEBUG=1 for verbose filesystem and push diagnostics.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from watchfiles import Change, watch

from rime_edge.client import RimeHttpClient
from rime_edge.config import EdgeConfig

logger = logging.getLogger("rime-edge.watch_file")


def _setup_logging() -> None:
    debug = os.getenv("RIME_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    if debug:
        logger.debug("RIME_DEBUG enabled")


def _same_path(watched: Path, changed: str | Path) -> bool:
    try:
        return Path(changed).resolve() == watched.resolve()
    except OSError:
        return Path(changed) == watched


def _log_fs_batch(changes: set[tuple[Change, str]], watch_path: Path) -> bool:
    """Log filesystem events; return True if watch_path was modified or added."""
    if not changes:
        logger.debug("watch() returned no changes")
        return False

    logger.info("%d filesystem change(s) in %s", len(changes), watch_path.parent)
    matched = False
    for change, changed_path in changes:
        is_target = _same_path(watch_path, changed_path)
        if is_target:
            if change in {Change.modified, Change.added}:
                logger.info("  -> %s %s (watch target)", change.name, changed_path)
                matched = True
            else:
                logger.info("  -> %s %s (watch target, ignored type)", change.name, changed_path)
        else:
            logger.info("  -> %s %s (ignored, not watch target)", change.name, changed_path)
    return matched


def _read_tail(path: Path, offset: int) -> tuple[bytes, int]:
    data = path.read_bytes()
    file_size = len(data)
    if offset > file_size:
        logger.info(
            "File shrank (%d -> %d bytes); resetting tail offset to 0",
            offset,
            file_size,
        )
        offset = 0
    chunk = data[offset:]
    return chunk, file_size


def _read_snapshot(path: Path) -> bytes:
    return path.read_bytes()


def _push_chunk(client: RimeHttpClient, config: EdgeConfig, body: bytes) -> None:
    if not body:
        logger.info("Skip push: 0 bytes to send (tail mode only uploads appended data)")
        return
    logger.info("Pushing %d bytes to %s", len(body), config.server_url)
    client.push(
        body,
        sensor_uuid=config.sensor_uuid,
        content_type=config.content_type,
        emitted_at=datetime.now(timezone.utc),
    )


def _wait_debounce(seconds: float) -> None:
    if seconds <= 0:
        return
    logger.info("Debounce: waiting %.1fs before read/push", seconds)
    time.sleep(seconds)


def run_tail(config: EdgeConfig, client: RimeHttpClient) -> None:
    path = config.watch_path.resolve()
    if not path.exists():
        raise SystemExit(f"Watch path does not exist: {path}")

    offset = path.stat().st_size
    logger.info("Tailing %s from offset %d", path, offset)

    while True:
        for changes in watch(path.parent, stop_event=None, step=config.poll_interval_ms):
            if not _log_fs_batch(changes, path):
                break

            _wait_debounce(config.debounce_seconds)
            chunk, offset = _read_tail(path, offset)
            logger.info(
                "Tail read: %d byte(s) to push, file size now %d",
                len(chunk),
                offset,
            )
            _push_chunk(client, config, chunk)
            break


def run_snapshot(config: EdgeConfig, client: RimeHttpClient) -> None:
    path = config.watch_path.resolve()
    if not path.exists():
        raise SystemExit(f"Watch path does not exist: {path}")

    logger.info("Watching %s in snapshot mode", path)

    while True:
        for changes in watch(path.parent, stop_event=None, step=config.poll_interval_ms):
            if not _log_fs_batch(changes, path):
                break

            _wait_debounce(config.debounce_seconds)
            body = _read_snapshot(path)
            logger.info("Snapshot read: %d byte(s) to push", len(body))
            _push_chunk(client, config, body)
            break


def main() -> None:
    _setup_logging()
    config = EdgeConfig.from_env()
    watch_path = config.watch_path.resolve()
    if not watch_path.parent.exists():
        raise SystemExit(f"Watch directory does not exist: {watch_path.parent}")

    client = RimeHttpClient(
        server_url=config.server_url,
        app_id=config.app_id,
        api_key=config.api_key,
    )

    logger.info(
        "Starting edge watcher app=%s sensor=%s mode=%s path=%s",
        config.app_id,
        config.sensor_uuid,
        config.watch_mode,
        watch_path,
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

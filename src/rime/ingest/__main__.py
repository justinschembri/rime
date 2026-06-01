"""Entry point for the rime-ingest service.

Starts two things in parallel:
  1. The FastAPI HTTP server (uvicorn) — receives transport commands from ctrl.
  2. The netmon background loop — watches thread health and writes reports.

Usage:
    python -m rime.ingest

Environment variables:
    INGEST_HOST   Host to bind the API server (default: 0.0.0.0)
    INGEST_PORT   Port to bind the API server (default: 8001)
"""

from __future__ import annotations

import logging
import os
import threading

import uvicorn

from rime.ingest.api import create_app
from rime.ingest.runtime import IngestRuntime
from rime.loggers import setup_loggers
from rime.monitor import netmon

setup_loggers()
logger = logging.getLogger("ingest.main")


def _run_netmon_loop() -> None:
    """Run the netmon health-report loop in a background thread."""
    while True:
        netmon.report(interval=5)


def main() -> None:
    host = os.getenv("INGEST_HOST", "0.0.0.0")
    port = int(os.getenv("INGEST_PORT", "8001"))

    runtime = IngestRuntime()
    app = create_app(runtime)

    # Start the netmon loop as a daemon thread — it will not block shutdown.
    monitor_thread = threading.Thread(
        target=_run_netmon_loop,
        daemon=True,
        name="netmon",
    )
    monitor_thread.start()
    logger.info("Network monitor started.")

    logger.info("Starting ingest API on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

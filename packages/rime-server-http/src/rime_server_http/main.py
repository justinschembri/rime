"""Entry point for rime-server-http.

Environment variables
---------------------
RIME_SERVER_CREDENTIALS_FILE
    Path to the YAML credentials file. Defaults to
    ``/app/runtime/server-credentials.yml``.
RIME_SERVER_HOST
    Bind host. Defaults to ``0.0.0.0``.
RIME_SERVER_PORT
    Bind port. Defaults to ``8080``.
RIME_SERVER_LOG_LEVEL
    uvicorn log level. Defaults to ``info``.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from .app import create_app
from .buffer import MessageBuffer
from .config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)


def main() -> None:
    config = load_config()
    buffer = MessageBuffer(max_depth_per_app=config.limits.max_queue_depth_per_app)
    app = create_app(config, buffer)

    uvicorn.run(
        app,
        host=os.getenv("RIME_SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("RIME_SERVER_PORT", "8080")),
        log_level=os.getenv("RIME_SERVER_LOG_LEVEL", "info"),
        access_log=True,
    )


if __name__ == "__main__":
    main()

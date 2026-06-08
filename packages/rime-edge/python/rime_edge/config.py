"""Edge configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EdgeConfig:
    server_url: str
    app_id: str
    api_key: str
    sensor_uuid: str
    watch_path: Path
    watch_mode: str
    content_type: str
    debounce_seconds: float
    poll_interval: float

    @classmethod
    def from_env(cls) -> EdgeConfig:
        missing = [
            name
            for name, value in (
                ("RIME_SERVER_URL", os.getenv("RIME_SERVER_URL")),
                ("RIME_APP_ID", os.getenv("RIME_APP_ID")),
                ("RIME_API_KEY", os.getenv("RIME_API_KEY")),
                ("RIME_SENSOR_UUID", os.getenv("RIME_SENSOR_UUID")),
                ("RIME_WATCH_PATH", os.getenv("RIME_WATCH_PATH")),
            )
            if not value
        ]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

        watch_mode = os.getenv("RIME_WATCH_MODE", "tail").strip().lower()
        if watch_mode not in {"tail", "snapshot"}:
            raise SystemExit("RIME_WATCH_MODE must be 'tail' or 'snapshot'.")

        return cls(
            server_url=os.environ["RIME_SERVER_URL"].rstrip("/"),
            app_id=os.environ["RIME_APP_ID"],
            api_key=os.environ["RIME_API_KEY"],
            sensor_uuid=os.environ["RIME_SENSOR_UUID"],
            watch_path=Path(os.environ["RIME_WATCH_PATH"]),
            watch_mode=watch_mode,
            content_type=os.getenv("RIME_CONTENT_TYPE", "application/octet-stream"),
            debounce_seconds=float(os.getenv("RIME_DEBOUNCE_SECONDS", "1.0")),
            poll_interval=float(os.getenv("RIME_POLL_INTERVAL", "0.5")),
        )

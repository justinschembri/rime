"""Server configuration loaded from a YAML credentials file.

Expected file format (mounted at ``RIME_SERVER_CREDENTIALS_FILE``):

.. code-block:: yaml

    limits:
      max_body_bytes: 1048576       # 1 MiB default
      max_queue_depth_per_app: 1000

    apps:
      seismic-edge-01:
        ingress_token: "edge-secret"
        egress_token: "ingest-secret"
      weather-station:
        ingress_token: "another-edge-secret"
        egress_token: "another-ingest-secret"

``ingress_token`` is used by edge producers (POST).
``egress_token`` is used by rime-ingest (GET + ACK).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_CREDENTIALS_FILE = "/app/runtime/server-credentials.yml"


@dataclass
class AppCredentials:
    ingress_token: str
    egress_token: str


@dataclass
class Limits:
    max_body_bytes: int = 1_048_576      # 1 MiB
    max_queue_depth_per_app: int = 1_000


@dataclass
class ServerConfig:
    limits: Limits
    apps: dict[str, AppCredentials] = field(default_factory=dict)


def load_config(path: str | Path | None = None) -> ServerConfig:
    """Load and validate the server credentials file.

    Falls back to ``RIME_SERVER_CREDENTIALS_FILE`` env var, then the
    container default ``/app/runtime/server-credentials.yml``.
    """
    resolved = Path(
        path
        or os.getenv("RIME_SERVER_CREDENTIALS_FILE", _DEFAULT_CREDENTIALS_FILE)
    )
    if not resolved.exists():
        raise FileNotFoundError(
            f"rime-server-http credentials file not found: {resolved}\n"
            "Set RIME_SERVER_CREDENTIALS_FILE or mount the file at the default path."
        )

    with resolved.open() as fh:
        raw = yaml.safe_load(fh) or {}

    raw_limits = raw.get("limits", {})
    limits = Limits(
        max_body_bytes=int(raw_limits.get("max_body_bytes", 1_048_576)),
        max_queue_depth_per_app=int(raw_limits.get("max_queue_depth_per_app", 1_000)),
    )

    apps: dict[str, AppCredentials] = {}
    for app_id, creds in (raw.get("apps") or {}).items():
        if "ingress_token" not in creds or "egress_token" not in creds:
            raise ValueError(
                f"App '{app_id}' in credentials file is missing "
                "'ingress_token' or 'egress_token'."
            )
        apps[str(app_id)] = AppCredentials(
            ingress_token=str(creds["ingress_token"]),
            egress_token=str(creds["egress_token"]),
        )

    return ServerConfig(limits=limits, apps=apps)

"""HTTP client for posting wire payloads to rime-server-http."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


class RimeHttpClient:
    """Minimal edge ingress client for rime-http-ingest-v1."""

    def __init__(
        self,
        *,
        server_url: str,
        app_id: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.app_id = app_id
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    def push(
        self,
        body: bytes,
        *,
        sensor_uuid: str,
        content_type: str = "application/octet-stream",
        emitted_at: datetime | None = None,
    ) -> None:
        url = f"{self.server_url}/v1/apps/{self.app_id}/messages"
        headers = {
            "Content-Type": content_type,
            "X-Rime-Message-Id": sensor_uuid,
        }
        if emitted_at is not None:
            headers["X-Rime-Emitted-At"] = emitted_at.astimezone(timezone.utc).isoformat()

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.post(
                    url,
                    data=body,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                delay = min(2 ** attempt, 30)
                logger.warning("POST failed (attempt %d/%d): %s", attempt, self.max_retries, exc)
                time.sleep(delay)
                continue

            if response.status_code == 202:
                logger.info(
                    "Accepted %d bytes for app=%s sensor=%s",
                    len(body),
                    self.app_id,
                    sensor_uuid,
                )
                return

            if response.status_code in {429, 500, 502, 503, 504}:
                retry_after = int(response.headers.get("Retry-After", min(2 ** attempt, 30)))
                logger.warning(
                    "POST returned %d (attempt %d/%d); retrying in %ds",
                    response.status_code,
                    attempt,
                    self.max_retries,
                    retry_after,
                )
                time.sleep(retry_after)
                continue

            response.raise_for_status()

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to POST after {self.max_retries} attempts.")

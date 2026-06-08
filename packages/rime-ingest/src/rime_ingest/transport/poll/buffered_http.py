"""Buffered-HTTP poll transport.

``BufferedHTTPTransport`` is purpose-built for sources that act as reliable
queues — specifically ``rime-server-http``. It differs from
:class:`~rime_ingest.transport.poll.http.HTTPTransport` in three fundamental
ways:

1. **Batch pull**: each poll yields *N* discrete messages, not a single
   snapshot.  The transport processes them one by one.

2. **No dedup**: every message has a server-assigned ``id``; equality checks
   on the payload itself are wrong and not performed.

3. **ACK after success**: messages are in-flight on the server until explicitly
   acknowledged.  A successful pass through the pipeline triggers an ack. If the
   process crashes between pull and ack, the server retains the in-flight
   messages and re-delivers them on the next poll (at-least-once semantics).

Providers subclass this and implement:

- ``_pull_batch(limit) -> list[WireEnvelope]``
  Fetch up to *limit* messages.  Each envelope must expose ``.id`` and
  ``.payload`` (plus any metadata the provider needs for decapsulation).

- ``_ack(ids: list[str]) -> None``
  Acknowledge the given server message ids.

- ``_auth() -> None`` (optional)
  Resolve and cache credentials before the run loop starts.

- ``_decapsulate_wire(wire_message: Any) -> DecapsulatedMessage``
  As on any :class:`~rime_ingest.transport.base.SensorTransport`.
"""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from typing import Any

from ...monitor import netmon
from ..base import SensorTransport

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")


class BufferedHTTPTransport(SensorTransport):
    """Abstract transport for reliable-queue HTTP sources.

    Parameters:
        app_name:        Application identifier (should equal server ``app_id``).
        batch_limit:     Maximum messages to drain per poll.
        poll_interval:   Seconds to sleep when the server queue is empty.
        max_retries:     Consecutive hard failures tolerated before stopping.
    """

    def __init__(
        self,
        app_name: str,
        *,
        batch_limit: int = 50,
        poll_interval: float = 2.0,
        max_retries: int = 10,
    ) -> None:
        super().__init__(app_name, max_retries=max_retries)
        self.batch_limit = batch_limit
        self.poll_interval = poll_interval

    # ------------------------------------------------------------------
    # Hooks — implement in the provider
    # ------------------------------------------------------------------

    def _auth(self) -> None:
        """Resolve and cache credentials. No-op by default."""

    @abstractmethod
    def _pull_batch(self, limit: int) -> list[Any]:
        """Fetch up to *limit* wire envelopes from the server.

        Each returned object must have an ``.id`` attribute (string) and must
        be passable to ``_process_wire_message`` / ``_decapsulate_wire``.
        """

    @abstractmethod
    def _ack(self, ids: list[str]) -> None:
        """Acknowledge *ids* so the server removes them from in-flight."""

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        self._auth()
        failures = 0
        while not self._stop_event.is_set():
            try:
                batch = self._pull_batch(self.batch_limit)
            except Exception as e:
                failures += self._exception_handler(e)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) fetching "
                        f"batch for {self.app_name}. Stopping transport."
                    )
                    self._stop_event.set()
                else:
                    time.sleep(self.poll_interval)
                continue

            if not batch:
                # Queue empty — back off before polling again.
                time.sleep(self.poll_interval)
                continue

            # Process each envelope; collect ids of those that succeed.
            acked_ids: list[str] = []
            for envelope in batch:
                try:
                    self._process_wire_message(envelope)
                    netmon.add_named_count(
                        "payloads_received", self.app_name, 1
                    )
                    acked_ids.append(envelope.id)
                    failures = 0
                except Exception as e:
                    failures += self._exception_handler(e, wire_message=envelope)
                    if failures >= self.max_retries:
                        main_logger.critical(
                            f"Exceeded max retries ({self.max_retries}) "
                            f"processing messages for {self.app_name}. "
                            "Stopping transport."
                        )
                        self._stop_event.set()
                        break

            if acked_ids:
                try:
                    self._ack(acked_ids)
                except Exception as e:
                    # Ack failure is non-fatal: server will re-deliver.
                    main_logger.warning(
                        f"{self.app_name}: ACK failed for {len(acked_ids)} "
                        f"messages — they will be re-delivered: {e}"
                    )

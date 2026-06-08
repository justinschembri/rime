"""In-memory message buffer.

One :class:`AppBuffer` per ``app_id``. The global :data:`BUFFER` dict is the
only shared state in the server. All mutations are serialised by
``asyncio``'s single-threaded event loop so no locks are required.

Lifecycle of a message::

    POST /v1/apps/{app_id}/messages
        → StoredMessage appended to AppBuffer.pending

    GET /v1/apps/{app_id}/messages
        → up to `limit` messages popped from pending, copied to in_flight

    POST /v1/apps/{app_id}/messages/ack
        → ids removed from in_flight (messages are now gone)

At-least-once guarantee: if ingest crashes between GET and ACK, the in-flight
messages are stranded until the server restarts. A future ``requeue_stale``
task can move old in_flight entries back to pending; that is deferred for MVP.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class StoredMessage:
    """A wire payload received from an edge producer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    app_id: str = ""
    message_id: str | None = None   # X-Rime-Message-Id supplied by edge (optional)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    emitted_at: datetime | None = None  # X-Rime-Emitted-At supplied by edge (optional)
    content_type: str = "application/octet-stream"
    #TODO: why is this a bytes object?
    body: bytes = b""


@dataclass
class AppBuffer:
    """FIFO queue for one app_id."""
    app_id: str
    max_depth: int = 1000
    pending: deque[StoredMessage] = field(default_factory=deque)
    in_flight: dict[str, StoredMessage] = field(default_factory=dict)

    def enqueue(self, msg: StoredMessage) -> bool:
        """Add *msg* to pending. Return False (without adding) if the queue is full."""
        if len(self.pending) >= self.max_depth:
            return False
        self.pending.append(msg)
        return True

    def drain(self, limit: int) -> list[StoredMessage]:
        """Move up to *limit* messages from pending → in_flight and return them."""
        batch: list[StoredMessage] = []
        for _ in range(min(limit, len(self.pending))):
            msg = self.pending.popleft()
            self.in_flight[msg.id] = msg
            batch.append(msg)
        return batch

    def ack(self, ids: list[str]) -> list[str]:
        """Remove messages from in_flight. Return the ids that were not found."""
        unknown = []
        for mid in ids:
            if mid in self.in_flight:
                del self.in_flight[mid]
            else:
                unknown.append(mid)
        return unknown

    @property
    def depth(self) -> int:
        return len(self.pending)

    @property
    def in_flight_count(self) -> int:
        return len(self.in_flight)


class MessageBuffer:
    """Registry of :class:`AppBuffer` instances, one per ``app_id``."""

    def __init__(self, max_depth_per_app: int = 1000) -> None:
        self._max_depth = max_depth_per_app
        self._apps: dict[str, AppBuffer] = {}

    def get_or_create(self, app_id: str) -> AppBuffer:
        if app_id not in self._apps:
            self._apps[app_id] = AppBuffer(
                app_id=app_id, max_depth=self._max_depth
            )
        return self._apps[app_id]

    def stats(self) -> dict[str, dict[str, int]]:
        return {
            app_id: {
                "pending": buf.depth,
                "in_flight": buf.in_flight_count,
            }
            for app_id, buf in self._apps.items()
        }

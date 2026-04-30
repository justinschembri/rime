"""HTTP poll transport.

`HTTPTransport` drives a polling loop: at a fixed interval it pulls a payload
via the provider's `_pull_data`, deduplicates against the previous payload,
and forwards new payloads to the shared processing pipeline. There is no
persistent network connection — the "transport" here is really a scheduler
on top of stateless requests.
"""

import logging
import time
from abc import abstractmethod
from typing import Any

from ...monitor import netmon
from ..base import SensorTransport

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")


class HTTPTransport(SensorTransport):
    """Abstract HTTP poll transport.

    Parameters:
        app_name: Application identifier.
        max_retries: Consecutive failures tolerated before the thread stops.
        request_interval: Seconds between successful pulls.
    """

    def __init__(
        self,
        app_name: str,
        *,
        max_retries: int = 10,
        # TODO: interval should not be bound to the application. It is plausible
        # to have sensors with different observation intervals to fall under the
        # same application.
        request_interval: int = 300,
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.request_interval = request_interval
        self._last_payload: Any = None

    @abstractmethod
    def _pull_data(self) -> Any:
        """Synchronously fetch the latest application payload."""
        ...

    def _run(self) -> None:
        failures = 0
        app_payload = None
        while not self._stop_event.is_set():
            try:
                app_payload = self._pull_data()
                if self._last_payload == app_payload:
                    # a bit of a 'magic number' here:
                    time.sleep(self.request_interval / 4)
                    continue
                self._last_payload = app_payload
                self._process_payload(app_payload)
                netmon.add_named_count("payloads_received", self.app_name, 1)
                failures = 0
                time.sleep(self.request_interval)
            except Exception as e:
                # TODO: consider carefully which exception types should be 'failures'
                failures += self._exception_handler(e, app_payload=app_payload)
                if failures == self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Killing thread."
                    )
                    self._stop_event.set()

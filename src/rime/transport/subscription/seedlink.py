"""SeedLink subscription transport.

`SeedLinkTransport` opens a long-lived TCP connection to a SeedLink server
using ObsPy's `EasySeedLinkClient`, selects the configured stream set, and
drains incoming :class:`obspy.Trace` objects into the shared processing
pipeline via a thread-safe queue.

ObsPy decodes the binary mini-SEED wire format internally before `on_data`
fires, so the `Trace` arrives as a fully-parsed Python object. Both
``_decode_wire`` and ``_deserialize_wire`` are therefore left as the identity
(inherited from ``SensorTransport``); the provider's
``_decapsulate_provider_payload`` receives a ``Trace`` directly.

Stream selectors are specified as ``"NET.STA.LOC.CHA"`` dot-separated strings
(e.g. ``"GE.WLF.00.BHZ"`` or ``"GE.UGM..HHZ"`` for an empty location code).
Wildcards accepted by ObsPy (``"?"``, ``"*"``) are forwarded as-is.
"""

import logging
import queue
import threading

from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient

from ..base import SensorTransport

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")

URL = str


class SeedLinkTransport(SensorTransport):
    """Abstract SeedLink subscription transport.

    Parameters:
        app_name: Application identifier.
        server_url: SeedLink server URL (e.g. ``"rtserve.iris.washington.edu:18000"``).
            Providers that require credentials may embed them as
            ``"user:pass@host:port"`` inside ``_auth``.
        streams: Stream selectors in ``"NET.STA.LOC.CHA"`` dot-separated format.
            Wildcards (``"?"``, ``"*"``) are forwarded to ObsPy's
            ``select_stream`` unchanged.
        max_retries: Consecutive failures tolerated before the thread stops.
        timeout: Seconds to wait on the trace queue between arrivals.
    """

    def __init__(
        self,
        app_name: str,
        host: URL,
        streams: list[str],
        *,
        max_retries: int = 3,
        timeout: int = 1200,
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.host = host
        self.streams = streams
        self.timeout = timeout
        self._payload_queue: queue.Queue = queue.Queue()
        self._connected: bool = False
        self._seedlink_client: EasySeedLinkClient | None = None

    def _auth(self) -> None:
        """Configure authentication or connection options before the client is created.

        Called by ``_connect`` before the ``EasySeedLinkClient`` is instantiated.
        Implementations may modify ``self.server_url`` (e.g. embed credentials as
        ``"user:pass@host:port"``) or set any other attribute used during
        connection setup. Providers that need no authentication implement this
        as a no-op.
        """
        pass

    def _connect(self) -> None:
        """Authenticate, create the SeedLink client, register streams, and start streaming."""
        self._auth()

        payload_queue = self._payload_queue

        class _Client(EasySeedLinkClient):
            def on_data(self, trace) -> None:
                payload_queue.put(trace)

        self._seedlink_client = _Client(self.host, autoconnect=False)

        for stream in self.streams:
            parts = stream.split(".")
            if len(parts) != 4:
                raise ValueError(
                    f"Stream selector must be 'NET.STA.LOC.CHA', got: {stream!r}"
                )
            net, sta, loc, cha = parts
            self._seedlink_client.select_stream(net, sta, f"{loc}{cha}")

        threading.Thread(
            target=self._seedlink_client.run,
            daemon=True,
            name=f"{self.app_name}-seedlink",
        ).start()
        self._connected = True
        event_logger.info(
            f"SeedLink client started for {self.app_name} @ {self.host}"
        )

    def _run(self) -> None:
        if not self._connected:
            self._connect()

        failures = 0
        wire_payload = None
        while not self._stop_event.is_set():
            try:
                wire_payload = self._payload_queue.get(timeout=self.timeout)
                self._process_payload(wire_payload)
                failures = 0
            except Exception as e:
                failures += self._exception_handler(e, wire_payload=wire_payload)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Stopping connection."
                    )
                    self._stop_event.set()

        event_logger.info(
            f"Gracefully stopping SeedLink connection for {self.app_name}"
        )
        if self._seedlink_client is not None:
            self._seedlink_client.close()
        self._connected = False

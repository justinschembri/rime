"""MQTT subscription transport.

`MQTTTransport` opens a long-lived broker connection, subscribes to a topic,
and uses paho's network thread to push incoming messages into a thread-safe
queue. The main worker thread drains the queue and forwards each message to
the shared processing pipeline.

Provider-specific authentication (username/password, TLS, certificates) is
configured by the provider before `_connect` is called — typically by setting
attributes on `self._mqtt_client` inside its own `_auth` method.
"""

import json
import logging
import queue
from abc import abstractmethod

from paho.mqtt.client import Client as MqttClient
from paho.mqtt.enums import CallbackAPIVersion

from ..base import SensorTransport

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")

URL = str


class MQTTTransport(SensorTransport):
    """Abstract MQTT subscription transport.

    Parameters:
        app_name: Application identifier.
        host: MQTT broker host.
        topic: Topic to subscribe to.
        port: Broker port (default 8883).
        max_retries: Consecutive timeout failures tolerated before stopping.
        timeout: Seconds to wait on the queue between message arrivals.
    """

    def __init__(
        self,
        app_name: str,
        host: URL,
        topic: str,
        *,
        port: int = 8883,
        max_retries: int = 3,
        timeout: int = 1200,
    ):
        super().__init__(app_name, max_retries=max_retries)
        self.host = host
        self.port = port
        self.topic = topic
        self.timeout = timeout
        self._payload_queue: queue.Queue = queue.Queue()
        self._subscribed: bool = False
        self._mqtt_client = MqttClient(CallbackAPIVersion.VERSION2)

    @abstractmethod
    def _auth(self) -> None:
        """Configure broker authentication on `self._mqtt_client`."""
        ...

    def _connect(self) -> None:
        """Authenticate, register callbacks, and connect to the broker.

        Subscriber callbacks fill `_payload_queue`; `_run` drains it.
        """
        self._auth()

        def on_message(client, userdata, message):
            self._payload_queue.put(json.loads(message.payload))

        def on_subscribe(client, userdata, mid, reason_code_list, properties):
            event_logger.info(
                f"Subscribed to {self.topic} - rcodes: {reason_code_list}"
            )

        def on_connect(client, userdata, flags, rc, properties):
            if rc == 0:
                event_logger.info(f"Connected to {self.host}/{self.app_name}")
                self._mqtt_client.subscribe(self.topic)
                self._subscribed = True
            else:
                event_logger.warning(f"connection failed with code {rc}")

        self._mqtt_client.on_connect = on_connect
        self._mqtt_client.on_message = on_message
        self._mqtt_client.on_subscribe = on_subscribe

        self._mqtt_client.loop_start()
        self._mqtt_client.connect(self.host, self.port)

    def _run(self) -> None:
        if not self._subscribed:
            self._connect()

        failures = 0
        app_payload = None
        while not self._stop_event.is_set():
            try:
                app_payload = self._payload_queue.get(timeout=self.timeout)
                self._process_payload(app_payload)
                failures = 0
            except Exception as e:
                failures += self._exception_handler(e, app_payload=app_payload)
                if failures >= self.max_retries:
                    main_logger.critical(
                        f"Exceeded max retries ({self.max_retries}) for "
                        f"{self.app_name}. Stopping connection."
                    )
                    self._stop_event.set()

        event_logger.info(f"Gracefully stopping MQTT connection for {self.app_name}")
        self._mqtt_client.loop_stop()
        self._mqtt_client.disconnect()
        self._subscribed = False

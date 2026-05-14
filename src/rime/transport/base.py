"""Abstract base for sensor transports.

A `SensorTransport` is a managed engagement with an upstream data source. It
owns the threading model, the payload-processing pipeline, and the exception
policy. Concrete subclasses specialise on the interaction model (poll vs.
subscription) and ultimately on the provider (Netatmo, TTS, ...).

## Ingest pipeline

`_process_payload` drives a two-tier pipeline for every wire payload received:

Provider tier (transport / provider level):

    _decode_wire          raw wire data  →  decoded form   (identity by default)
    _deserialize_wire     decoded form   →  Python object  (identity by default)
    _decapsulate_wire        →  list[DecapsulatedMessage]

Model tier (per DecapsulatedMessage, keyed by sensor model from INGEST_COMPONENT_MAP):

    deserializer.deserialize  →  remaining payload deserialization
    decoder.decode            →  raw readings → physical values
    transformer.from_parsed   →  vendor fields → SensorThings observations
    frost_observation_upload  →  push to FROST

The application-tier hooks default to identity so transports whose libraries
already handle wire decoding (ObsPy for SeedLink, lnetatmo for Netatmo) need
not override them. MQTT overrides `_deserialize_wire` with `json.loads`.

Authentication is intentionally *not* a base-class concern — credential
storage and resolution differ enough between providers (OAuth tokens, API
keys, TLS certs, no auth at all) that pinning a shape here would force every
provider to adapt to the lowest common denominator. Providers handle their
own auth in whatever method they need.
"""

import inspect
import logging
import queue
import threading
import traceback
from abc import ABC, abstractmethod
from typing import Any, Literal

from rime.exceptions import FrostUploadFailure, UnpackError, UnregisteredSensorError
from rime.frost.post import frost_observation_upload

from ..monitor import netmon
from ..transformers.decapsulators.types import DecapsulatedMessage
from ..transformers.ingest_registry import INGEST_COMPONENT_MAP
from ..transformers.messages import ParsedMessage
from ..transformers.types import SensorUUID, SupportedSensors

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")


class SensorTransport(ABC):
    """Abstract base for any managed link to an upstream sensor data source."""

    def __init__(self, app_name: str, *, max_retries: int = 1):
        self.app_name = app_name
        self.max_retries = max_retries
        #TODO: sensor_registry as an attr is a codesmell
        self.sensor_registry: dict[SensorUUID, SupportedSensors] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # dunder ###################################################################
    def __hash__(self) -> int:
        return hash(self.app_name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, SensorTransport):
            return False
        return other.app_name == self.app_name

    # construction #############################################################
    @classmethod
    def from_config(cls, app_name: str, config: dict[str, Any]) -> "SensorTransport":
        """Build a transport from a YAML application config dict.

        Constructor parameters are discovered via `inspect.signature`; any keys
        in `config` whose names match a parameter are forwarded. Unknown keys
        are ignored so callers do not have to filter them out.
        """
        sig = inspect.signature(cls)
        kwargs: dict[str, Any] = {"app_name": app_name}
        for param_name in sig.parameters:
            if param_name in config:
                kwargs[param_name] = config[param_name]
        return cls(**kwargs)

    # lifecycle ################################################################
    def _preflight(self) -> bool:
        """Optional pre-start checks. Return False to abort startup."""
        return True

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @abstractmethod
    def _run(self) -> None:
        """
        Long-running loop that drives data acquisition and processing.

        This method must always call _process_payload().
        """
        ...

    def start(self, sensor_registry: dict[SensorUUID, SupportedSensors]) -> None:
        """Start the transport's worker thread.

        Skips startup if `_preflight` fails. Idempotent: re-calling while the
        thread is alive is a no-op.
        """
        self.sensor_registry = sensor_registry
        if not self._preflight():
            event_logger.warning(
                f"Preflight check failed for {self.app_name}; not starting connection."
            )
            return
        if self.is_alive:
            return
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=self.app_name,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def restart(self, join_timeout: int = 15) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(join_timeout)
        if not self.sensor_registry:
            raise AttributeError(
                f"Trying to restart {self.app_name} thread with no "
                "sensor registry available."
            )
        self._stop_event.clear()
        self.start(self.sensor_registry)

    # processing ###############################################################
    def _decode_wire(self, raw: Any) -> Any:
        """Convert raw wire data to a decoded form suitable for deserialization.

        Default: identity. Override when the transport delivers opaque bytes
        that require a codec (e.g. base64, UTF-8) before deserialization.
        """
        return raw

    def _deserialize_wire(self, decoded: Any) -> Any:
        """Parse decoded wire data into a Python object.

        Default: identity. Override when the wire format is a serialized
        representation (JSON, CBOR, Protobuf, ...) that needs parsing into
        an in-memory object before decapsulation. ``MQTTTransport`` overrides
        this with ``json.loads``; SeedLink and HTTP leave it as the identity
        because their libraries already return Python objects.
        """
        return decoded

    @abstractmethod
    def _decapsulate_wire(
        self, wire_payload: Any
    ) -> list[DecapsulatedMessage]:
        """Strip the provider envelope and route to per-sensor messages.

        Receives the output of ``_deserialize_wire`` — always a Python object,
        never raw bytes. Returns one ``DecapsulatedMessage`` per sensor reading
        contained in the payload.
        """

    def _process_payload(self, wire_payload: Any) -> None:
        """Run the full two-tier ingest pipeline for a single wire payload.

        Provider tier:
            _decode_wire → _deserialize_wire → _decapsulate_wire

        Model tier (per DecapsulatedMessage):
            deserializer → decoder → transformer → frost_observation_upload
        """
        decoded = self._decode_wire(wire_payload)
        deserialized = self._deserialize_wire(decoded)
        decapsulated_messages = self._decapsulate_wire(deserialized)
        for decapsulated in decapsulated_messages:
            sensor_id = decapsulated.sensor_id
            try:
                sensor_model = self.sensor_registry.get(sensor_id, None)
                if not sensor_model:
                    raise UnregisteredSensorError

                components = INGEST_COMPONENT_MAP[sensor_model]
                #TODO: might be hidden bugs in this chunk:
                deserialized = components.deserializer.deserialize(decapsulated)
                decoded = components.decoder.decode(deserialized)
                parsed = ParsedMessage.from_decoded(decoded)
                payload = components.transformer.from_parsed(parsed)
                st_observations = payload.to_stObservations()
                for st_obs in st_observations:
                    try:
                        debug_logger.debug(f"{st_obs=} {sensor_id=}")
                        frost_observation_upload(sensor_id, st_obs)
                        event_logger.info(
                            f"Received and processed a payload from {self.app_name} "
                            f"from a {sensor_model.value} sensor."
                        )
                        netmon.add_named_count("push_success", f"{sensor_id}", 1)
                    except FrostUploadFailure as e:
                        self._exception_handler(e, sensor_id=sensor_id)
            except (UnregisteredSensorError, UnpackError, KeyError) as e:
                self._exception_handler(e, sensor_id=sensor_id, stage="model_ingest")
                continue

    #TODO: reconsider exception handler as part of the class, should be a global concern
    def _exception_handler(self, e: Exception | None, **kwargs) -> Literal[0, 1]:
        """Classify an exception. Return 0 if transient, 1 if a real failure."""

        def _log(msg: str, debug_context: dict[str, str]):
            main_logger.error(msg)
            debug_logger.debug(debug_context)

        debug_context = {
            "application": f"{self.app_name}",
            "exception_type": f"{type(e)}",
            "exception_message": f"{e}",
            **kwargs,
        }
        name = e.__repr__()
        if isinstance(e, UnpackError):
            msg = f"{name}: failed to unpack an application payload."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, queue.Empty):
            msg = f"{name}: MQTT queue is empty."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, UnregisteredSensorError):
            msg = f"{name}: sensor is not registered."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, KeyError):
            msg = f"{name}: sensor model has no ingest components configured."
            _log((f"{self.app_name} " + msg), debug_context)
            return 0
        elif isinstance(e, FrostUploadFailure):
            msg = f"{name}: failure to upload to FROST."
            _log((f"{self.app_name} " + msg), debug_context)
            return 1
        else:
            msg = f"{e}"
            msg += traceback.format_exc()
            _log((f"{self.app_name} " + msg), debug_context)
            return 1

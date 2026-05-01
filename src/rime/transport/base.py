"""Abstract base for sensor transports.

A `SensorTransport` is a managed engagement with an upstream data source. It
owns the threading model, the payload-processing pipeline, and the exception
policy. Concrete subclasses specialise on the interaction model (poll vs.
subscription) and ultimately on the provider (Netatmo, TTS, ...).

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
from typing import Any, ClassVar, Literal

from rime.exceptions import FrostUploadFailure, UnregisteredSensorError
from rime.frost.post import frost_observation_upload

from ..monitor import netmon
from ..transformers.application_unpackers import ApplicationUnpacker, UnpackError
from ..transformers.registry import TRANSFORMER_MAP
from ..transformers.types import SensorUUID, SupportedSensors

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")


class SensorTransport(ABC):
    """Abstract base for any managed link to an upstream sensor data source."""

    application_unpacker: ClassVar[ApplicationUnpacker]

    def __init__(self, app_name: str, *, max_retries: int = 1):
        self.app_name = app_name
        self.max_retries = max_retries
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

    # abstract #################################################################
    @abstractmethod
    def _run(self) -> None:
        """Long-running loop that drives data acquisition and processing."""
        ...

    # lifecycle ################################################################
    def _preflight(self) -> bool:
        """Optional pre-start checks. Return False to abort startup."""
        return True

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

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
    def _process_payload(self, app_payload: dict[str, Any]) -> None:
        """Unpack, transform, and push a single application payload."""
        # TODO: successful unpack is a bit of a contrived obj.
        successful_unpack = self.application_unpacker.unpack(app_payload)
        for sensor_id, observations in successful_unpack.data.items():
            sensor_model = self.sensor_registry.get(sensor_id, None)
            if not sensor_model:
                raise UnregisteredSensorError
            transformer = TRANSFORMER_MAP[sensor_model]
            payload = transformer.from_unpack(
                observations, successful_unpack.application_timestamp
            )
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
        elif isinstance(e, FrostUploadFailure):
            msg = f"{name}: failure to upload to FROST."
            _log((f"{self.app_name} " + msg), debug_context)
            return 1
        else:
            msg = f"{e}"
            msg += traceback.format_exc()
            _log((f"{self.app_name} " + msg), debug_context)
            return 1

"""Abstract base for sensor transports.

A `SensorTransport` is a managed engagement with an upstream data source. It
owns the threading model, the wire-message-processing pipeline, and the
exception policy. Concrete subclasses specialise on the interaction model
(poll vs. subscription) and ultimately on the provider (Netatmo, TTS, ...).

## Ingest pipeline

`_process_wire_message` drives a two-stage pipeline for every wire message received:

Provider tier (transport / provider level):

    _decode_wire          raw wire data  →  decoded form   (identity by default)
    _deserialize_wire     decoded form   →  Python object  (identity by default)
    _decapsulate_wire        →  DecapsulatedMessage

The decapsulated message carries a list of IdentifiedPayload entries — one per
logical sensor present in the wire message — together with optional
EnvelopeMetadata (timestamps and channel hints from the provider envelope).

Model tier (per IdentifiedPayload, keyed by sensor model from INGEST_COMPONENT_MAP):

    parser.parse          →  ObservationRecord (sensor_uuid + observations + timestamps)
    normalizer.from_record  →  vendor fields → SensorThings observations
    frost_observation_upload →  push to FROST

Time-series carriers (:class:`~rime.transformers.messages.IdentifiedTimeSeriesPayload`)
are expanded in ``_process_wire_message`` into one :class:`~rime.transformers.messages.IdentifiedPayload`
per sample before the model tier runs.

The application-tier hooks default to identity so transports whose libraries
already handle wire decoding (ObsPy for SeedLink, lnetatmo for Netatmo) need
not override them. MQTT overrides `_deserialize_wire` with `json.loads`.

Authentication is intentionally *not* a base-class concern — credential
storage and resolution differ enough between providers (OAuth tokens, API
keys, TLS certs, no auth at all) that pinning a shape here would force every
provider to adapt to the lowest common denominator. Providers handle their
own auth in whatever method they need.
"""
#stdlib
import inspect
import logging
import queue
import threading
import traceback
from abc import ABC, abstractmethod
from typing import Any, Literal
#internal

from .buffers import ObservationBuffer, BufferRegistryKey, resolve_buffer
from ..frost.post import frost_observation_upload
from ..monitor import netmon
from ..transformers.ingest_registry import resolve_identified_payload
from ..transformers.messages import (
    DecapsulatedMessage,
    EnvelopeMetadata,
    IdentifiedPayload,
    IdentifiedTimeSeriesPayload,
)
from ..exceptions import (
        FrostUploadFailure, 
        UnexpectedProviderMessage,
        UnpackError,
        UnregisteredSensorError
        )

from ..transformers.types import SensorUUID, SupportedSensors

main_logger = logging.getLogger("main")
event_logger = logging.getLogger("events")
debug_logger = logging.getLogger("debug")

# RUNTIME OBJECTS
RUNTIME_BUFFER_REGISTRY: dict[BufferRegistryKey, ObservationBuffer] = {}
RUNTIME_BUFFER_REGISTRY_LOCK = threading.Lock()

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
        Implemented in a direct descendant of `SensorTransport`.
        This method must receive a wire message and pass it to 
        the implemented _process_wire_message(). 

        Long-running loop that drives data acquisition and processing.

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
        self._flush_sensor_buffers()

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
    def _decapsulate_wire(self, wire_message: Any) -> DecapsulatedMessage:
        """
        Implement in a concrete providers.

        Strip the provider envelope; return a :class:`~rime.transformers.messages.DecapsulatedMessage`.

        Receives the output of ``_deserialize_wire`` — always a Python object,
        never raw bytes.  The returned message's ``identified_payloads`` list
        carries one :class:`~rime.transformers.messages.IdentifiedPayload` per
        logical sensor present in the wire message.

        """

    def _process_wire_message(self, wire_message: Any) -> None:
        """Run the full two-stage ingest pipeline for a single wire message.

        Provider tier:
            _decode_wire → _deserialize_wire → _decapsulate_wire

        Model tier (per sample after any time-series fan-out):
            parser.parse → normalizer.from_record → frost_observation_upload
        """
        decoded_wire = self._decode_wire(wire_message)
        deserialized_wire = self._deserialize_wire(decoded_wire)
        decapsulated = self._decapsulate_wire(deserialized_wire)

        for identified in decapsulated.identified_payloads:
            sensor_uuid = identified.sensor_uuid
            try:
                envelope = decapsulated.envelope_metadata
                self.run_payload_ingest(
                    resolve_identified_payload(identified, self.sensor_registry),
                    envelope,
                )
            except (UnregisteredSensorError, UnpackError, KeyError) as e:
                self._exception_handler(e, sensor_id=sensor_uuid, stage="model_ingest")
                continue

    def run_payload_ingest(
        self,
        identified: IdentifiedPayload | IdentifiedTimeSeriesPayload,
        envelope: EnvelopeMetadata | None,
    ) -> None:
        components = identified.components
        sensor_model = identified.sensor_model
        sensor_uuid = identified.sensor_uuid
        if components is None or sensor_model is None:
            raise UnpackError(
                RuntimeError("IdentifiedPayload must be resolved before model ingest.")
            )
        if components.deserializer:
            identified = components.deserializer.deserialize(identified, envelope) #type: ignore
        if components.decoder:
            identified = components.decoder.decode(identified, envelope) #type: ignore
        if isinstance(identified, IdentifiedTimeSeriesPayload):
            point_in_time_inputs = identified.expand_to_point_in_time(envelope)
        else:
            point_in_time_inputs = iter([(identified, envelope)])

        for sample_identified, sample_envelope in point_in_time_inputs:
            record = components.parser.parse(sample_identified, sample_envelope)
            normalizer = components.normalizer.from_record(record)
            st_observations = normalizer.to_stObservations()
            for st_obs in st_observations:
                try:
                    debug_logger.debug(f"{st_obs=} {sensor_uuid=}")
                    RUNTIME_BUFFER_REGISTRY, buffer = resolve_buffer(
                            sensor_uuid,
                            sensor_model,
                            st_obs, 
                            RUNTIME_BUFFER_REGISTRY
                            ) # defaults to NullBuffer, which is always pending_flush
                    if buffer.pending_flush:
                        frost_observation_upload(sensor_uuid, buffer.dump())
                        buffer.commit()
                    else:
                        buffer.add_observation(st_obs[0])
                        continue

                    event_logger.info(
                        f"Received and processed a wire message from {self.app_name} "
                        f"from a {sensor_model.value} sensor."
                    )
                    netmon.add_named_count("push_success", f"{sensor_uuid}", 1)
                except FrostUploadFailure as e:
                    self._exception_handler(e, sensor_id=sensor_uuid)

    def _flush_sensor_buffers(self) -> None:
        """Upload any in-flight or partial buffer contents for this transport's sensors."""
        for key, buffer in list(RUNTIME_BUFFER_REGISTRY.items()):
            sensor_uuid, sensor_model, _ = key
            if sensor_uuid not in self.sensor_registry:
                continue
            try:
                st_obs = buffer.flush_pending()
                if st_obs is None:
                    continue
                frost_observation_upload(sensor_uuid, st_obs)
                buffer.commit()
                event_logger.info(
                    f"Flushed buffered observations from {self.app_name} "
                    f"for a {sensor_model.value} sensor on shutdown."
                )
            except FrostUploadFailure as e:
                self._exception_handler(e, sensor_id=sensor_uuid)

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
            msg = f"{name}: failed to unpack a wire message."
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
        elif isinstance(e, UnexpectedProviderMessage):
            msg = f"{name}: unexpected provider message."
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

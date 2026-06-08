"""Ingress pipeline carrier types.

All dataclasses that flow between pipeline stages live here.  ABCs for each
stage live in their respective ``core.py`` modules and import from this file.

Vocabulary
----------
wire_message
    The raw provider artifact received from the network before any rime
    processing (MQTT packet, HTTP webhook body, API response).  Untyped
    (``Any``); no rime contract applies until decapsulation.

Payload
    The sensor-native reading as emitted by the sensor firmware.  Provider-
    independent: the same sensor model connected via a different upstream
    provider produces the same payload shape.

IdentifiedPayload
    A ``Payload`` enriched with rime routing metadata — specifically
    ``sensor_uuid``, the registry key used to look up model components.
    Compositionally: ``IdentifiedPayload = Payload + identity``.  After
    registry resolution, ``sensor_model`` and ``components`` are populated
    (see :func:`~rime.transformers.ingest_registry.resolve_identified_payload`).

IdentifiedTimeSeriesPayload
    Time-series analogue of ``IdentifiedPayload`` for providers that
    homogeneously deliver readings as evenly- or unevenly-sampled series
    (e.g. SeedLink mini-SEED). ``payloads`` is a sequence of per-sample
    elements, each the same shape as one ``IdentifiedPayload.payload`` would
    be for that sensor model; ``time_axis`` carries the shared timeline.
    Datastream hints not embedded in the payload live on
    ``DecapsulatedMessage.envelope_metadata``.  A decapsulator emits either
    ``IdentifiedPayload`` *or* ``IdentifiedTimeSeriesPayload`` per message —
    never both.

DecapsulatedMessage  ("Message")
    The ingest unit produced by a :class:`~rime.transformers.decapsulators.core.Decapsulator`.
    One wire message may fan out into 0–N ``IdentifiedPayload`` entries
    (e.g. a Netatmo response covering multiple stations).  Provider-level
    context that is *not* embedded in any sensor payload (gateway receive
    timestamps, datastream hints) is carried on ``envelope_metadata``.

ObservationRecord
    Per-sensor record produced by a
    :class:`~rime.transformers.parsers.core.Parser`.  The ``observations``
    field contains only observation-ready key/value pairs — timestamps and
    non-observation metadata have been extracted or dropped by the parser.
    Distinct from :class:`IdentifiedPayload` (sensor-native blob) and
    :class:`DecapsulatedMessage` (provider-level carrier): this is a
    rime-constructed record, no longer sensor-native.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from numpy import ndarray
from obspy.core import Trace

from rime_ingest.exceptions import UnpackError

from .types import SensorUUID, SupportedSensors

if TYPE_CHECKING:
    from .ingest_registry import IngestModelComponents


# ---------------------------------------------------------------------------
# Decapsulation tier
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IdentifiedPayload:
    """A native sensor payload paired with its rime registry identity.

    ``payload`` is provider-independent: the same sensor model connected to a
    different upstream provider produces the same ``payload`` shape.  Identity
    extraction is provider-dependent and happens inside the decapsulator.
    ``sensor_model`` and ``components`` are filled by
    :func:`~rime.transformers.ingest_registry.resolve_identified_payload`.
    """

    sensor_uuid: SensorUUID
    payload: Any
    sensor_model: SupportedSensors | None = None
    components: IngestModelComponents | None = None

@dataclass(frozen=True, slots=True)
class RegularTimeAxis:
    """Compact time axis for evenly-sampled series.

    Mirrors ObsPy's ``Trace.stats`` time model: a start instant, a fixed
    inter-sample interval, and a sample count. ``endtime`` is derived; the
    per-sample timeline is materialised on demand via :meth:`iter_timestamps`.
    """

    starttime: datetime
    delta: float
    npts: int

    @property
    def endtime(self) -> datetime:
        return self.starttime + timedelta(seconds=(self.npts - 1) * self.delta)

    def iter_timestamps(self) -> Iterator[datetime]:
        delta_us = self.delta * 1_000_000
        for i in range(self.npts):
            yield self.starttime + timedelta(microseconds=int(round(i * delta_us)))


@dataclass(frozen=True, slots=True)
class IrregularTimeAxis:
    """Explicit per-sample timestamps for non-uniformly-sampled series."""

    timestamps: list[datetime]

    def iter_timestamps(self) -> Iterator[datetime]:
        yield from self.timestamps


TimeAxis = RegularTimeAxis | IrregularTimeAxis


@dataclass(slots=True)
class IdentifiedTimeSeriesPayload:
    """A native sensor time-series paired with its rime registry identity.

    Used instead of :class:`IdentifiedPayload` when the provider chooses to
    homogeneously deliver readings as time series rather than point-in-time
    samples (common for high-rate digitisers — e.g. SeedLink / mini-SEED).

    ``payloads`` is a sequence of per-sample elements — each the same shape as
    one :attr:`IdentifiedPayload.payload` for that sensor model (e.g. a scalar
    ``ndarray`` for one channel, or a ``dict`` for one multi-field snapshot).
    All elements share a single :attr:`time_axis`. Provider-independent: the
    same sensor model carried by a different upstream produces the same shape.
    ``sensor_model`` and ``components`` are filled by
    :func:`~rime.transformers.ingest_registry.resolve_time_series_payload`.
    """

    sensor_uuid: SensorUUID
    payload: list[Any] | ndarray | Trace
    time_axis: TimeAxis
    sensor_model: SupportedSensors | None = None
    components: IngestModelComponents | None = None
    _decoded: bool = False
    _deserialized: bool = False

    def iter_samples(self) -> Iterator[tuple[Any, datetime]]:
        """Yield ``(payload_element, phenomenon_timestamp)`` pairs."""
        timestamps = list(self.time_axis.iter_timestamps())
        payloads = self.payload
        if not isinstance(payloads, (list, ndarray)):
            raise TypeError(f"Expected list or ndarray, got: {type(payloads)}")
        n = len(payloads) if isinstance(payloads, list) else int(payloads.shape[0])
        if n != len(timestamps):
            raise UnpackError(
                ValueError(
                    f"time axis length {len(timestamps)} != payload length {n}"
                )
            )
        if isinstance(payloads, ndarray):
            for i, timestamp in enumerate(timestamps):
                yield payloads[i], timestamp
        else:
            yield from zip(payloads, timestamps)

    def expand_to_point_in_time(
        self,
        envelope: EnvelopeMetadata | None,
    ) -> Iterator[tuple[IdentifiedPayload, EnvelopeMetadata]]:
        """Fan out into per-sample :class:`IdentifiedPayload` + envelope pairs."""
        # the Trace object is often retained as a Trace until the parsing step
        # where we now only wanted the decoded data in Trace.data. This is due to
        # the decoding step needing to call Trace.remove_response(...)
        if isinstance(self.payload, Trace):
            self.payload = self.payload.data
        for element, timestamp in self.iter_samples():
            yield (
                IdentifiedPayload(
                    sensor_uuid=self.sensor_uuid,
                    payload=element,
                    sensor_model=self.sensor_model,
                    components=self.components,
                ),
                envelope_at_phenomenon_time(envelope, timestamp),
            )


@dataclass(frozen=True, slots=True)
class EnvelopeMetadata:
    """Residual metadata from the provider envelope.

    Carries only information that is *not* embedded in the native sensor
    payload — e.g. gateway receive timestamps, channel/datastream hints.
    ``sensor_uuid`` is intentionally absent: identity lives on
    :class:`IdentifiedPayload`.
    """

    app_name: Optional[str] = None
    datastream_name: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    phenomenon_timestamp: Optional[datetime] = None
    other: Optional[Any] = None

    def with_phenomenon_time(self, phenomenon_timestamp: datetime) -> EnvelopeMetadata:
        return replace(self, phenomenon_timestamp=phenomenon_timestamp)


def envelope_at_phenomenon_time(
    envelope: EnvelopeMetadata | None,
    phenomenon_timestamp: datetime,
) -> EnvelopeMetadata:
    """Return *envelope* with ``phenomenon_timestamp`` set for one sample."""
    if envelope is None:
        return EnvelopeMetadata(phenomenon_timestamp=phenomenon_timestamp)
    return envelope.with_phenomenon_time(phenomenon_timestamp)


@dataclass(slots=True)
class DecapsulatedMessage:
    """One wire message stripped of provider-specific framing.

    Fields
        ``identified_payloads`` is a list of :class:`IdentifiedPayload` — one
        entry per logical sensor present in the original wire message (e.g.
        multiple Netatmo stations, or a single TTN device).

        ``envelope_metadata`` carries leftover provider-level context that may be
        needed downstream (timestamps, datastream hints) but is *not* part of any
        sensor-native payload.

        `_decoded`: true if in a decoder has been applied to identified_payloads,
            for debugging

        `_deserialized`: true if a deserialized has been applied to identified_paylods,
            for debugging
    """

    identified_payloads: list[IdentifiedPayload] | list[IdentifiedTimeSeriesPayload]
    envelope_metadata: Optional[EnvelopeMetadata] = None
    _decoded: bool = False
    _deserialized: bool = False


# ---------------------------------------------------------------------------
# Parse tier
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ObservationRecord:
    """Fully-resolved per-sensor record produced by a parser.

    `observations` contains only observation-ready key/value pairs.
    Timestamps and non-observation metadata are extracted or dropped by the
    parser before this point; `VendorObservationNormalizer` receives a clean
    dict of physical quantities.

    `observations` keys must match the field names declared on the concrete
    `transformers.normalizers.core.Normalizer` subclass that will
    consume this record.  Parsers are responsible for producing the correct key
    names and stripping everything that is not an observation field.
    """

    sensor_uuid: SensorUUID
    observations: dict[str, Any]
    provider_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None
    time_axis: TimeAxis | None = None

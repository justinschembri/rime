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
    Compositionally: ``IdentifiedPayload = Payload + identity``.

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

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .types import SensorUUID


# ---------------------------------------------------------------------------
# Decapsulation tier
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class IdentifiedPayload:
    """A native sensor payload paired with its rime registry identity.

    ``payload`` is provider-independent: the same sensor model connected to a
    different upstream provider produces the same ``payload`` shape.  Identity
    extraction is provider-dependent and happens inside the decapsulator.
    """

    sensor_uuid: SensorUUID
    payload: Any


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


@dataclass(frozen=True, slots=True)
class DecapsulatedMessage:
    """One wire message stripped of provider-specific framing.

    ``identified_payloads`` is a list of :class:`IdentifiedPayload` — one
    entry per logical sensor present in the original wire message (e.g.
    multiple Netatmo stations, or a single TTN device).

    ``envelope_metadata`` carries leftover provider-level context that may be
    needed downstream (timestamps, datastream hints) but is *not* part of any
    sensor-native payload.
    """

    identified_payloads: list[IdentifiedPayload]
    envelope_metadata: Optional[EnvelopeMetadata] = None


# ---------------------------------------------------------------------------
# Parse tier
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ObservationRecord:
    """Fully-resolved per-sensor record produced by a parser.

    ``observations`` contains only observation-ready key/value pairs.
    Timestamps and non-observation metadata are extracted or dropped by the
    parser before this point; ``VendorObservationNormalizer`` receives a clean
    dict of physical quantities.

    ``observations`` keys must match the field names declared on the concrete
    :class:`~rime.transformers.normalizers.core.Normalizer` subclass that will
    consume this record.  Parsers are responsible for producing the correct key
    names and stripping everything that is not an observation field.
    """

    sensor_uuid: SensorUUID
    observations: dict[str, Any]
    provider_timestamp: datetime | None = None
    phenomenon_timestamp: datetime | None = None

"""Parser base class: identified payload + envelope -> ObservationRecord."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..messages import EnvelopeMetadata, IdentifiedPayload, ObservationRecord


class Parser(ABC):
    """Convert one :class:`~rime.transformers.messages.IdentifiedPayload` into an
    :class:`~rime.transformers.messages.ObservationRecord`.

    A parser is model-specific: it knows the native field layout of a
    particular sensor model and assembles a fully-routed record ready for the
    normalizer.  It does *not* know which upstream provider produced the data —
    that information arrives via ``envelope`` if needed (e.g. timestamps the
    sensor payload does not carry itself).

    Time-series carriers (:class:`~rime.transformers.messages.IdentifiedTimeSeriesPayload`)
    must be expanded into point-in-time :class:`~rime.transformers.messages.IdentifiedPayload`
    samples before parsing (see ``SensorTransport.run_payload_ingest``).

    Contract: ``ObservationRecord.observations`` must contain *only*
    observation-ready fields.  Timestamps and non-observation metadata must be
    extracted or dropped before returning.
    """

    @staticmethod
    @abstractmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ObservationRecord:
        """Return an :class:`~rime.transformers.messages.ObservationRecord` for *identified*.

        Raise :class:`~rime.exceptions.UnpackError` on malformed payloads.
        """
        ...

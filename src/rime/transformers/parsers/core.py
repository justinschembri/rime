"""Parser base class: identified payload + envelope -> ParsedMessage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..decapsulators.types import EnvelopeMetadata, IdentifiedPayload
from ..messages import ParsedMessage


class Parser(ABC):
    """Convert one :class:`IdentifiedPayload` into a :class:`ParsedMessage`.

    A parser is model-specific: it knows the native field layout of a
    particular sensor model and assembles a fully-routed, normalised record
    ready for the transformer.  It does *not* know which upstream provider
    produced the data — that information arrives via ``envelope`` if needed
    (e.g. timestamps the sensor payload does not carry itself).
    """

    @staticmethod
    @abstractmethod
    def parse(
        identified: IdentifiedPayload,
        envelope: EnvelopeMetadata | None,
    ) -> ParsedMessage:
        """Return a :class:`ParsedMessage` for *identified*.

        Raise :class:`~rime.exceptions.UnpackError` on malformed payloads.
        """
        ...

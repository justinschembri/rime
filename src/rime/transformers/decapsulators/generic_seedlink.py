"""Decapsulator for a generic SeedLink message.

A SeedLink mini-SEED record arrives via ObsPy as a single :class:`obspy.Trace`
covering one channel of one station over a contiguous time window. Identity is
extracted at station granularity (``NET.STA``); the SEED channel code is
carried on :attr:`~rime.transformers.messages.EnvelopeMetadata.datastream_name`.
"""

from __future__ import annotations

from datetime import timezone

from obspy.core import Trace

from ...exceptions import MissingPayloadKeysError, UnpackError
from ..messages import (
    DecapsulatedMessage,
    EnvelopeMetadata,
    IdentifiedTimeSeriesPayload,
    RegularTimeAxis,
)
from .core import Decapsulator


class GenericSeedLinkDecapsulator(Decapsulator):
    """Strip a SeedLink :class:`obspy.Trace` into an :class:`IdentifiedTimeSeriesPayload`.

    - ``sensor_uuid``: ``"NET.STA"`` derived from ``trace.stats``.
    - ``payloads``: ``trace.data`` — one sample array for this channel.
    - ``time_axis``: :class:`RegularTimeAxis` from ``trace.stats``.
    - ``envelope_metadata.datastream_name``: SEED channel code (``BHZ``, etc.).
    """

    @staticmethod
    def decapsulate(wire_message: Trace) -> DecapsulatedMessage:
        try:
            stats = wire_message.stats
            sensor_uuid = f"{stats.network}.{stats.station}"
            time_axis = RegularTimeAxis(
                starttime=stats.starttime.datetime.replace(tzinfo=timezone.utc),
                delta=float(stats.delta),
                npts=int(stats.npts),
            )
            identified = IdentifiedTimeSeriesPayload(
                sensor_uuid=sensor_uuid,
                payloads=wire_message.data,
                time_axis=time_axis,
            )
            envelope = EnvelopeMetadata(datastream_name=stats.channel)
        except AttributeError as e:
            raise MissingPayloadKeysError(e)
        except Exception as e:
            raise UnpackError(e)

        return DecapsulatedMessage(
            identified_payloads=[identified],
            envelope_metadata=envelope,
        )

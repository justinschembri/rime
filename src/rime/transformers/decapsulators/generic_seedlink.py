"""Decapsulator for a Generic seedlink message."""

# stdlib
from __future__ import annotations
# external
from obspy.core import Trace
from rime.transformers.decapsulators.core import Decapsulator
# internal
from ..messages import DecapsulatedMessage, IdentifiedPayload


class GenericSeedLinkDecapsulator(Decapsulator):
    """Decapsulate a generic seed link message - essentially a no-op."""

    @staticmethod
    def decapsulate(wire_message: Trace) -> DecapsulatedMessage:
        trace_stats = wire_message.stats
        #TODO: high-risk name clash plausible:
        # trace_stats.channel is the datastream, no need to put into the 
        # envelope metadata since the wire_payload is the full trace obj.
        sensor_uuid = trace_stats.network + trace_stats.station
        identified_payload = IdentifiedPayload(sensor_uuid, wire_message)
        return DecapsulatedMessage([identified_payload])

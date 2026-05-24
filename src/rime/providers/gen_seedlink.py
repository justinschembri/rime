"""Generic SeedLink Provider"""
#external
from obspy.core import Trace
from rime.transformers.decapsulators.generic_seedlink import GenericSeedLinkDecapsulator
from rime.transformers.messages import DecapsulatedMessage
#internal
from ..transport import SeedLinkTransport

class GenericSeedLinkProvider(SeedLinkTransport):

    def _decapsulate_wire(self, wire_message: Trace) -> DecapsulatedMessage:
        return GenericSeedLinkDecapsulator.decapsulate(wire_message)

"""Generic SeedLink Provider"""
#external
from obspy.core import Trace
#internal
from rime.transformers.decapsulators.types import DecapsulatedMessage
from ..transport import SeedLinkTransport

class GenericSeedLinkProvider(SeedLinkTransport):

    def _decapsulate_wire(self, wire_payload: Trace) -> list[DecapsulatedMessage]:
        stats = wire_payload.stats
        sensor_id = f"{stats.network}.{stats.station}"
        decapped = [DecapsulatedMessage(sensor_id, wire_payload)]
        return decapped

"""Model-level decoder for the Kinemetrics ETNA2 triaxial accelerometer."""
# external
from obspy import Trace, read_inventory
# internal
from rime.transformers.messages import EnvelopeMetadata, IdentifiedPayload, IdentifiedTimeSeriesPayload
from rime.paths import DECODERS_DIR
from .core import Decoder

KINEMETRICS_ETNA2_DECODER_XML = DECODERS_DIR / "xml_decoders" / "kinemetrics_etna2_fsdn.xml"
inventory = read_inventory(KINEMETRICS_ETNA2_DECODER_XML)

class KinemetricsEtna2Decoder(Decoder):
    """Kinemetrics ETNA2 accelerometer payload decoder.

    Decoding is the process by which model-specific encoded data is decoded into
    some other representation, e.g., accelerometer data → physical units.

    Model-specific decoding occurs after a message is decapsulated and should
    modify the `payload` or `payloads` of an `IdentifiedPayload` or 
    `IdentifiedTimeSeriesPayload` respectively.

    Returns a new, IdentifiedPayload | IdentifiedTimeSeriesPayload with decoded
    payloads.
    """
    
    @staticmethod
    def decode(
        identified_payload: IdentifiedPayload | IdentifiedTimeSeriesPayload,
        envelope_metadata: EnvelopeMetadata 
    ) -> IdentifiedTimeSeriesPayload:
        """Return *identified* with its `payload` decoded."""
        if not isinstance(identified_payload, IdentifiedTimeSeriesPayload):
            raise TypeError(
                    "KinemetricsEtna2Decoder expects an IdentifiedTimeSeriesPayload, " 
                    f"but got: {type(identified_payload)}"
                    )
        payloads = identified_payload.payload
        if not isinstance(payloads, Trace):
            raise TypeError(f"Expected Trace object got {type(payloads)}")

        payloads.remove_response(inventory=inventory, output="ACC") 

        return identified_payload


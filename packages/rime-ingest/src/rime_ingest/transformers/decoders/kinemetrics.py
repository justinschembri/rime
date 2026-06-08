"""Model-level decoder for the Kinemetrics seismic sensors."""
# external
from copy import deepcopy
from obspy import Trace, read_inventory, Inventory
# internal
from rime_ingest.transformers.messages import EnvelopeMetadata, IdentifiedPayload, IdentifiedTimeSeriesPayload
from rime_ingest.paths import DECODERS_DIR
from rime_ingest.transformers.types import SensorUUID, SupportedSensors
from .core import Decoder

KINEMETRICS_ETNA2_DECODER_XML = DECODERS_DIR / "xml_decoders" / "kinemetrics_etna2_fsdn.xml"
ETNA2_INVENTORY: Inventory = read_inventory(KINEMETRICS_ETNA2_DECODER_XML)
INVENTORY_CACHE: dict[SensorUUID, Inventory] = {}

def make_inventory(
        trace:Trace,
        inventory_template: Inventory
        ) -> Inventory:
    """
    Make a sensor-specific inventory from a template FDSN station XML.

    Outside of `rime`, each instrument in the field is mapped to its own individual
    instrument file, or inventory: an XML file encoded in the FDSN standards.
    The `Inventory` class is ObsPy's representation of such an instrument file.

    An inventory file includes all the numeric information required to deconvolve
    the waveform. This numeric content is identical for instrument files belonging
    to the same sensor family. Thus, the use of a "template" instrument file
    specific to a sensor model is mathemtically acceptable. ObsPy deconvolves the
    waveform through the method `.remove_response(inventory)`, which is passed an
    inventory file. This method calls a look-up within the XML inventory file
    which uses network and station names as keys, as found in the `Trace` object.
    Thus, a template file would throw an exception, not having found the specific
    keys and break the process.

    This method creates a deepcopy of the template `Inventory` object and replaces 
    the `network` and `station` component to match those found in the trace.

    """
    stats = trace.stats
    network = stats.network
    station = stats.station
    inventory = inventory_template.copy()
    inventory.networks[0].code = network
    inventory.networks[0].stations[0].code = station
    return inventory


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
        envelope_metadata: EnvelopeMetadata | None
    ) -> IdentifiedTimeSeriesPayload:
        """Return *identified* with its `payload` decoded."""
        if not isinstance(identified_payload, IdentifiedTimeSeriesPayload):
            raise TypeError(
                    "KinemetricsEtna2Decoder expects an IdentifiedTimeSeriesPayload, " 
                    f"but got: {type(identified_payload)}"
                    )
        payload = identified_payload.payload
        if not isinstance(payload, Trace):
            raise TypeError(f"Expected Trace object got {type(payload)}")

        inventory = INVENTORY_CACHE.get(identified_payload.sensor_uuid)
        if not inventory:
            inventory = make_inventory(payload, ETNA2_INVENTORY)
            INVENTORY_CACHE[identified_payload.sensor_uuid] = inventory

        payload.remove_response(inventory=inventory, output="ACC") 
        return identified_payload


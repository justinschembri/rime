"""Constructed registries for various runtime components."""

# internal
from rime_ingest.transformers.types import SupportedSensors
from rime_ingest.transport.buffers import KinemetricsEtna2Buffer, ObservationBuffer

DEFAULT_BUFFER_REGISTRY: dict[SupportedSensors, type[ObservationBuffer]] = {}
DEFAULT_BUFFER_REGISTRY[SupportedSensors.KINEMETRICS_ETNA2] = KinemetricsEtna2Buffer

def generate_buffer_registry():
    """Read a buffer registry YAML and return a modified version of the default buffer registry."""
    return DEFAULT_BUFFER_REGISTRY

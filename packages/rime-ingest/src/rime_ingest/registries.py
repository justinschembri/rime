"""Constructed registries for various runtime components."""

# internal
from rime_ingest.transformers.types import SupportedSensors
from rime_ingest.transport.buffers import KinemetricsEtna2Buffer, ObservationBuffer

DEFAULT_BUFFER_REGISTRY: dict[SupportedSensors, type[ObservationBuffer]] = {}
DEFAULT_BUFFER_REGISTRY[SupportedSensors.KINEMETRICS_ETNA2] = KinemetricsEtna2Buffer

def generate_buffer_registry(
    overrides: dict[SupportedSensors, type[ObservationBuffer]] | None = None,
) -> dict[SupportedSensors, type[ObservationBuffer]]:
    """Return a copy of the default buffer registry, optionally merged with overrides."""
    registry = DEFAULT_BUFFER_REGISTRY.copy()
    if overrides:
        registry.update(overrides)
    return registry

"""STA transformer for Netatmo NWS03.

Receives an :class:`~rime.transformers.messages.ObservationRecord` whose ``observations``
have already been prepared by :class:`~rime.transformers.parsers.netatmo.NetatmoNWS03Parser`:

- keys are lowercase
- ``time_utc`` has been extracted as ``phenomenon_timestamp`` on the message
- trend fields have been dropped

The normalizer therefore only performs field → ObservedProperties mapping.
No key normalisation or timestamp extraction happens here.

Example ``observations`` shape received::

    {"temperature": 23.3, "co2": 871, "humidity": 46, "noise": 33, "pressure": 1014.8}
"""

from .core import Normalizer
from ..types import ObservedProperties


class NetatmoNWS03(Normalizer):
    temperature: float
    co2: int
    humidity: int
    noise: int
    pressure: float

    NAME_TRANSFORM: dict[str, ObservedProperties] = {
        "temperature": ObservedProperties.TEMP_IN,
        "co2": ObservedProperties.CO2_INDOOR,
        "humidity": ObservedProperties.HUMIDITY_INDOOR,
        "noise": ObservedProperties.NOISE_IN,
        "pressure": ObservedProperties.G_PRESSURE_IN,
    }

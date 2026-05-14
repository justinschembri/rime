"""Wire-format parsing (e.g. JSON text, CBOR) and model-level deserializers.

``JsonWireDeserializer`` — wire-format step (bytes → Python object, before
    decapsulation). Used by ``MQTTTransport._deserialize_wire``.

``Deserializer`` / ``NullDeserializer`` — model-level step (DecapsulatedMessage
    → DecapsulatedMessage, after decapsulation, keyed by sensor model in
    ``INGEST_COMPONENT_MAP``).
"""

from .core import Deserializer
from .json_wire import JsonWireDeserializer
from .null import NullDeserializer

__all__ = ["Deserializer", "JsonWireDeserializer", "NullDeserializer"]

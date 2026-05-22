"""Model-level deserializers and wire-format parsing utilities.

``JsonWireDeserializer`` — wire-format step (bytes → Python object, *before*
    decapsulation). Used by ``MQTTTransport._deserialize_wire``.

``Deserializer`` — optional model-level step (IdentifiedPayload →
    IdentifiedPayload, *after* decapsulation).  Register via
    ``deserializer=`` in ``INGEST_COMPONENT_MAP``; leave as ``None`` to skip
    when the payload is already structured.
"""

from .core import Deserializer
from .json_wire import JsonWireDeserializer

__all__ = ["Deserializer", "JsonWireDeserializer"]

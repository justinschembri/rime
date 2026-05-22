"""Wire-format deserializer: JSON bytes/str → Python object."""

from __future__ import annotations

import json
from typing import Any


class JsonWireDeserializer:
    """Deserialize a raw JSON wire payload (bytes or str) to a Python object.

    This is a wire-format utility operating *before* application decapsulation.
    It is not a subclass of :class:`Deserializer`, which operates on
    :class:`~rime.transformers.messages.IdentifiedPayload` at the later
    model-level stage of the pipeline.

    ``MQTTTransport._deserialize_wire`` delegates to this class, so MQTT
    providers inherit JSON deserialization without referencing it directly.
    """

    __slots__ = ()

    @staticmethod
    def deserialize(payload: bytes | str) -> Any:
        return json.loads(payload)

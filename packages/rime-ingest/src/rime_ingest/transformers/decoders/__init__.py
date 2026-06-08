"""Model-level payload decoders (structured form → semantic values).

``Decoder`` — optional model-level step (IdentifiedPayload →
    IdentifiedPayload, after any deserializer and before the parser).
    Register via ``decoder=`` in ``INGEST_COMPONENT_MAP``; leave as ``None``
    to skip when the payload values are already observation-ready.
"""

from .core import Decoder

__all__ = ["Decoder"]

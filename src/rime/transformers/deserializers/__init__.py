"""Reserved: wire-format parsing (e.g. JSON text, CBOR) into Python values."""

from .core import Deserializer
from .null import NullDeserializer

__all__ = ["Deserializer", "NullDeserializer"]

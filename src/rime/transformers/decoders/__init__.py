"""Semantic / codec decoding toward ``DecodedMessage`` (post-envelope body)."""

from .core import Decoder
from .null import NullDecoder

__all__ = ["Decoder", "NullDecoder"]

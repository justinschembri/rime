"""Poll-style transports: caller drives the request rhythm."""

from .http import HTTPTransport

__all__ = ["HTTPTransport"]

"""FROST server interaction errors."""
#standard
#exteranl
#internal

class FrostConnectionError(ConnectionError):
    def __init__(self, message, url=None):
        super().__init__(message)
        self.url = url

class FrostRequestError(FrostConnectionError):
    def __init__(self, message, url=None):
        super().__init__(message)
        self.url = url

class FrostWriterError(ValueError):
    """Raised when a FROST response cannot be serialized cleanly."""


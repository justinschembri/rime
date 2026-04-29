"""FROST server interaction errors."""

class FrostConnectionError(ConnectionError):
    def __init__(self, message: str | None = None, url: str | None = None):
        super().__init__(message)
        self.url = url

class FrostRequestError(FrostConnectionError):
    def __init__(self, message: str | Exception, url: str | None = None):
        super().__init__(message)
        self.url = url

class FrostNoResultsError(Exception):
    pass

class FrostWriterError(ValueError):
    """Raised when a FROST response cannot be serialized cleanly."""


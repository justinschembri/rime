"""FROST server interaction errors."""

class FrostConnectionError(ConnectionError):
    """Base error for FROST server connection failures.

    Attributes:
        url: The URL that was being accessed when the error occurred.
    """

    def __init__(self, message: str | None = None, url: str | None = None):
        super().__init__(message)
        self.url = url

class FrostRequestError(FrostConnectionError):
    """Raised when a FROST HTTP request fails.

    Wraps both connection-level failures and non-2xx HTTP responses. The
    original exception or response body is included in the message.

    Attributes:
        url: The URL of the failed request.
    """

    def __init__(self, message: str | Exception, url: str | None = None):
        super().__init__(message)
        self.url = url

class FrostNoResultsError(Exception):
    """Raised when a FROST query returns no results and a result is required."""

class FrostWriterError(ValueError):
    """Raised when a FROST response cannot be serialised to the target format.

    Typically indicates a schema inconsistency across result rows or a missing
    ``value`` key in the response.
    """


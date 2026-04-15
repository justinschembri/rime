"""FROST server interaction errors."""
#standard
#exteranl
#internal

class FrostConnectionError(ConnectionError):
    def __init__(self, message, url=None):
        super().__init__(message)
        self.url = url

"""Domain exceptions for the live monitoring feature."""


class LiveDataError(Exception):
    """Raised when live portfolio data cannot be built."""


class QuoteFetchError(LiveDataError):
    """Raised when intraday quote retrieval fails for a ticker."""

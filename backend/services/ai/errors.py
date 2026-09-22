"""AI provider errors. Failures must not silently fabricate results."""


class AIProviderError(Exception):
    """Raised when a real AI provider call fails or returns invalid data."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        retryable: bool = False,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.retryable = retryable
        self.cause = cause

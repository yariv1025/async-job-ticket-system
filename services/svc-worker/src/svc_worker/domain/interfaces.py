"""Domain interfaces (Protocols)."""

from typing import Protocol, Any


class Logger(Protocol):
    """Logger interface."""

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        ...

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        ...

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        ...


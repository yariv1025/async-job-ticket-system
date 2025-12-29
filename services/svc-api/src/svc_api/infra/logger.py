"""Structured logging setup."""

import os
import sys
import structlog
from typing import Any, Dict

from ..domain.interfaces import Logger


def setup_logging(level: str = "INFO") -> None:
    """Set up structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class StructLogger(Logger):
    """Structured logger implementation."""

    def __init__(self, component: str = "svc-api"):
        """Initialize logger."""
        self.logger = structlog.get_logger(component=component)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)


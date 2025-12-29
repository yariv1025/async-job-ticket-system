"""Domain interfaces (Protocols)."""

from typing import Protocol, Optional, Dict, Any
from .job import Job


class DynamoDBRepository(Protocol):
    """DynamoDB repository interface."""

    def put_job(self, job: Job) -> None:
        """Store a job in DynamoDB."""
        ...

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        ...

    def get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[Job]:
        """Retrieve a job by idempotency key."""
        ...

    def update_job_status(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        """Update job status."""
        ...


class SQSClient(Protocol):
    """SQS client interface."""

    def send_message(self, queue_url: str, message_body: str, message_attributes: Dict[str, Any]) -> str:
        """Send a message to SQS."""
        ...


class ParameterStoreClient(Protocol):
    """Parameter Store client interface."""

    def get_parameter(self, name: str) -> str:
        """Get a parameter value."""
        ...


class MetricsClient(Protocol):
    """CloudWatch Metrics client interface."""

    def put_metric(self, metric_name: str, value: float, unit: str = "Count") -> None:
        """Put a custom metric."""
        ...


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


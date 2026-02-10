"""Domain interfaces (Protocols)."""

from typing import Any, Dict, List, Optional, Protocol

from .job import Job, JobStatus


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


class DynamoDBRepository(Protocol):
    """DynamoDB repository interface (worker: get_job, update_job)."""

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        ...

    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> None:
        """Update job status and optional fields."""
        ...


class SQSClient(Protocol):
    """SQS client interface (worker: receive, delete, visibility, attributes)."""

    def receive_messages(
        self,
        queue_url: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> List[Dict[str, Any]]:
        """Receive messages with long polling."""
        ...

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        """Delete a message from the queue."""
        ...

    def change_message_visibility(
        self, queue_url: str, receipt_handle: str, visibility_timeout: int
    ) -> None:
        """Change message visibility timeout."""
        ...

    def get_queue_attributes(self, queue_url: str) -> Dict[str, Any]:
        """Get queue attributes (e.g. approximate message count)."""
        ...


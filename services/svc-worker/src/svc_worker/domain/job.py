"""Job domain model (shared with API service)."""

from enum import Enum
from datetime import datetime, UTC
from typing import Optional, Dict, Any


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    FAILED_FINAL = "FAILED_FINAL"


class Job:
    """Job entity."""

    def __init__(
        self,
        job_id: str,
        status: JobStatus,
        job_type: str,
        priority: str,
        params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None,
        payload_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        attempts: int = 0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        expires_at: Optional[int] = None,
    ):
        self.job_id = job_id
        self.status = status
        self.job_type = job_type
        self.priority = priority
        self.params = params
        self.metadata = metadata or {}
        self.idempotency_key = idempotency_key
        self.trace_id = trace_id
        self.payload_hash = payload_hash
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)
        self.attempts = attempts
        self.result = result
        self.error = error
        self.expires_at = expires_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from DynamoDB dictionary."""
        from datetime import datetime

        return cls(
            job_id=data["jobId"],
            status=JobStatus(data["status"]),
            job_type=data.get("jobType", ""),
            priority=data.get("priority", "normal"),
            params=data.get("params", {}),
            metadata=data.get("metadata", {}),
            idempotency_key=data.get("idempotencyKey"),
            trace_id=data.get("traceId"),
            payload_hash=data.get("payloadHash"),
            created_at=datetime.fromisoformat(data["createdAt"]) if data.get("createdAt") else None,
            updated_at=datetime.fromisoformat(data["updatedAt"]) if data.get("updatedAt") else None,
            attempts=data.get("attempts", 0),
            result=data.get("result"),
            error=data.get("error"),
            expires_at=data.get("expiresAt"),
        )


"""Job domain model."""

from enum import Enum
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from uuid import uuid4


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
    def create(
        cls,
        job_type: str,
        priority: str,
        params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> "Job":
        """Create a new job."""
        import hashlib
        import json

        job_id = str(uuid4())
        payload = json.dumps({"type": job_type, "priority": priority, "params": params}, sort_keys=True)
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()

        # TTL: 24 hours from now
        expires_at = int((datetime.now(UTC).timestamp() + 86400))

        return cls(
            job_id=job_id,
            status=JobStatus.PENDING,
            job_type=job_type,
            priority=priority,
            params=params,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            payload_hash=payload_hash,
            expires_at=expires_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for DynamoDB."""
        item = {
            "jobId": self.job_id,
            "status": self.status.value,
            "jobType": self.job_type,
            "priority": self.priority,
            "params": self.params if self.params else {},
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "attempts": self.attempts,
            "expiresAt": self.expires_at,
        }
        
        # Only include metadata if it's not empty (DynamoDB doesn't accept empty maps)
        if self.metadata:
            item["metadata"] = self.metadata
        
        # Only include optional fields if they are not None
        if self.idempotency_key is not None:
            item["idempotencyKey"] = self.idempotency_key
        if self.trace_id is not None:
            item["traceId"] = self.trace_id
        if self.payload_hash is not None:
            item["payloadHash"] = self.payload_hash
        if self.result is not None:
            item["result"] = self.result
        if self.error is not None:
            item["error"] = self.error
            
        return item

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


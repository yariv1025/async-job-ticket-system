"""Pydantic schemas for API requests and responses."""

from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


class JobRequest(BaseModel):
    """Job creation request schema."""

    type: str = Field(..., description="Job type (e.g., process_document, generate_report)")
    priority: Literal["low", "normal", "high"] = Field(default="normal", description="Job priority")
    params: Dict[str, Any] = Field(..., description="Job parameters")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate job type."""
        allowed_types = ["process_document", "generate_report", "transform_data"]
        if v not in allowed_types:
            raise ValueError(f"Job type must be one of: {', '.join(allowed_types)}")
        return v


class JobResponse(BaseModel):
    """Job response schema."""

    job_id: str = Field(..., alias="jobId", description="Unique job identifier")
    status: str = Field(..., description="Job status")
    job_type: str = Field(..., alias="jobType", description="Job type")
    priority: str = Field(..., description="Job priority")
    created_at: str = Field(..., alias="createdAt", description="Job creation timestamp")
    updated_at: str = Field(..., alias="updatedAt", description="Job last update timestamp")
    trace_id: Optional[str] = Field(None, alias="traceId", description="Trace ID for correlation")

    class Config:
        """Pydantic config."""

        populate_by_name = True


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")


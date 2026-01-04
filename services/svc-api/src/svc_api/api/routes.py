"""FastAPI routes."""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, status, Request
from fastapi.responses import JSONResponse

from ..service.job_service import JobService
from ..domain.job import Job
from .schemas import JobRequest, JobResponse, ErrorResponse

router = APIRouter()


def get_job_service_from_request(request: Request) -> JobService:
    """Get job service from request state."""
    if not hasattr(request.state, "job_service") or request.state.job_service is None:
        raise HTTPException(status_code=500, detail="Job service not initialized")
    return request.state.job_service


def get_trace_id(x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id")) -> Optional[str]:
    """Extract trace ID from header."""
    return x_trace_id


def get_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> Optional[str]:
    """Extract idempotency key from header."""
    return idempotency_key


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_job(
    request: JobRequest,
    http_request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id"),
) -> JobResponse:
    """Create a new job."""
    job_service = get_job_service_from_request(http_request)

    try:
        job = job_service.create_job(
            job_type=request.type,
            priority=request.priority,
            params=request.params,
            metadata=request.metadata,
            idempotency_key=idempotency_key,
            trace_id=x_trace_id,
        )

        return JobResponse(
            jobId=job.job_id,
            status=job.status.value,
            jobType=job.job_type,
            priority=job.priority,
            createdAt=job.created_at.isoformat(),
            updatedAt=job.updated_at.isoformat(),
            traceId=job.trace_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_job(
    job_id: str,
    http_request: Request,
) -> JobResponse:
    """Get a job by ID."""
    job_service = get_job_service_from_request(http_request)

    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    return JobResponse(
        jobId=job.job_id,
        status=job.status.value,
        jobType=job.job_type,
        priority=job.priority,
        createdAt=job.created_at.isoformat(),
        updatedAt=job.updated_at.isoformat(),
        traceId=job.trace_id,
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def retry_job(
    job_id: str,
    http_request: Request,
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id"),
) -> JobResponse:
    """Retry publishing a job to SQS if it's stuck in PENDING."""
    job_service = get_job_service_from_request(http_request)

    try:
        job = job_service.retry_job(job_id, trace_id=x_trace_id)
        return JobResponse(
            jobId=job.job_id,
            status=job.status.value,
            jobType=job.job_type,
            priority=job.priority,
            createdAt=job.created_at.isoformat(),
            updatedAt=job.updated_at.isoformat(),
            traceId=job.trace_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


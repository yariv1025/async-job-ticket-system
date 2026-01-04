"""Job service implementation."""

import json
import time
from typing import Optional, Dict, Any
from uuid import uuid4

from ..domain.job import Job, JobStatus
from ..domain.interfaces import (
    DynamoDBRepository,
    SQSClient,
    ParameterStoreClient,
    MetricsClient,
    Logger,
)


class JobService:
    """Job service for creating and managing jobs."""

    def __init__(
        self,
        dynamodb_repo: DynamoDBRepository,
        sqs_client: SQSClient,
        parameter_store: ParameterStoreClient,
        metrics_client: MetricsClient,
        logger: Logger,
    ):
        """Initialize job service."""
        self.dynamodb_repo = dynamodb_repo
        self.sqs_client = sqs_client
        self.parameter_store = parameter_store
        self.metrics_client = metrics_client
        self.logger = logger
        self._queue_url: Optional[str] = None

    def _get_queue_url(self) -> str:
        """Get SQS queue URL (cached)."""
        if self._queue_url is None:
            self._queue_url = self.parameter_store.get_parameter("sqs/queue-url")
        return self._queue_url

    def create_job(
        self,
        job_type: str,
        priority: str,
        params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Job:
        """Create a new job with idempotency check and SQS publishing."""
        start_time = time.time()

        # Generate trace ID if not provided
        if trace_id is None:
            trace_id = str(uuid4())

        # Validate params is not empty (DynamoDB/LocalStack requirement)
        if not params:
            raise ValueError("params cannot be empty - at least one parameter is required")

        # Check idempotency if key provided
        if idempotency_key:
            existing_job = self.dynamodb_repo.get_job_by_idempotency_key(idempotency_key)
            if existing_job:
                self.logger.info(
                    "Job already exists with idempotency key",
                    idempotency_key=idempotency_key,
                    job_id=existing_job.job_id,
                    trace_id=trace_id,
                )
                return existing_job

        # Create job
        job = Job.create(
            job_type=job_type,
            priority=priority,
            params=params,
            metadata=metadata,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )

        try:
            # Write to DynamoDB first
            self.dynamodb_repo.put_job(job)
            self.logger.info(
                "Job created in DynamoDB",
                job_id=job.job_id,
                status=job.status.value,
                trace_id=trace_id,
            )

            # Publish to SQS
            queue_url = self._get_queue_url()
            message_body = json.dumps(
                {
                    "jobId": job.job_id,
                    "payloadHash": job.payload_hash,
                    "traceId": trace_id,
                }
            )
            message_attributes = {
                "jobId": job.job_id,
                "traceId": trace_id,
                "jobType": job.job_type,
            }

            sqs_start = time.time()
            self.sqs_client.send_message(queue_url, message_body, message_attributes)
            sqs_latency = (time.time() - sqs_start) * 1000  # Convert to milliseconds

            self.logger.info(
                "Job published to SQS",
                job_id=job.job_id,
                trace_id=trace_id,
                sqs_latency_ms=sqs_latency,
            )

            # Emit metrics
            self.metrics_client.put_metric("JobsCreated", 1.0)
            self.metrics_client.put_metric("SQSPublishLatency", sqs_latency, "Milliseconds")

            return job

        except Exception as e:
            # Compensation: If SQS publish fails, mark job as FAILED
            self.logger.error(
                "Failed to publish job to SQS, marking as FAILED",
                job_id=job.job_id,
                trace_id=trace_id,
                error=str(e),
            )

            try:
                self.dynamodb_repo.update_job_status(job.job_id, JobStatus.FAILED.value, str(e))
            except Exception as update_error:
                self.logger.error(
                    "Failed to update job status after SQS failure",
                    job_id=job.job_id,
                    error=str(update_error),
                )

            self.metrics_client.put_metric("JobsCreatedFailed", 1.0)
            raise RuntimeError(f"Failed to create job: {e}") from e

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.dynamodb_repo.get_job(job_id)

    def retry_job(self, job_id: str, trace_id: Optional[str] = None) -> Job:
        """Retry publishing a job to SQS if it's stuck in PENDING."""
        if trace_id is None:
            trace_id = str(uuid4())

        job = self.dynamodb_repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status != JobStatus.PENDING:
            raise ValueError(f"Job {job_id} is not in PENDING status (current: {job.status.value})")

        # Re-publish to SQS
        queue_url = self._get_queue_url()
        message_body = json.dumps(
            {
                "jobId": job.job_id,
                "payloadHash": job.payload_hash,
                "traceId": trace_id,
            }
        )
        message_attributes = {
            "jobId": job.job_id,
            "traceId": trace_id,
            "jobType": job.job_type,
        }

        try:
            self.sqs_client.send_message(queue_url, message_body, message_attributes)
            self.logger.info(
                "Job re-published to SQS",
                job_id=job.job_id,
                trace_id=trace_id,
            )
            return job
        except Exception as e:
            self.logger.error(
                "Failed to re-publish job to SQS",
                job_id=job.job_id,
                trace_id=trace_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to retry job: {e}") from e


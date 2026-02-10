"""Job processor implementation with exponential backoff."""

import time
import json
from typing import Optional
from ..infra.xray import xray_capture

from ..domain.job import Job, JobStatus
from ..domain.interfaces import DynamoDBRepository, Logger, SQSClient
from ..infra.metrics import CloudWatchMetricsClient


class JobProcessor:
    """Job processor with idempotency and exponential backoff."""

    def __init__(
        self,
        dynamodb_repo: DynamoDBRepository,
        sqs_client: SQSClient,
        metrics_client: CloudWatchMetricsClient,
        logger: Logger,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        backoff_multiplier: float = 2.0,
    ):
        """Initialize job processor."""
        self.dynamodb_repo = dynamodb_repo
        self.sqs_client = sqs_client
        self.metrics_client = metrics_client
        self.logger = logger
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable (transient)."""
        error_str = str(error).lower()
        # Retry on 5xx errors, throttling, network errors
        retryable_indicators = [
            "500",
            "503",
            "504",
            "throttl",
            "timeout",
            "connection",
            "network",
        ]
        return any(indicator in error_str for indicator in retryable_indicators)

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        backoff = self.initial_backoff * (self.backoff_multiplier ** attempt)
        return min(backoff, self.max_backoff)

    @xray_capture("process_job")
    def process_job(self, job: Job, receipt_handle: str, queue_url: str) -> bool:
        """Process a job with idempotency check and retry logic."""
        start_time = time.time()
        trace_id = job.trace_id or "unknown"

        self.logger.info(
            "Processing job",
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status.value,
            trace_id=trace_id,
        )

        # Idempotency check: if already SUCCEEDED or FAILED_FINAL, skip
        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED_FINAL):
            self.logger.info(
                "Job already processed, skipping",
                job_id=job.job_id,
                status=job.status.value,
                trace_id=trace_id,
            )
            # Delete message since it's already processed
            try:
                self.sqs_client.delete_message(queue_url, receipt_handle)
            except Exception as e:
                self.logger.warning(
                    "Failed to delete already-processed message",
                    job_id=job.job_id,
                    error=str(e),
                )
            return True

        # Update status to PROCESSING
        try:
            self.dynamodb_repo.update_job(
                job.job_id,
                JobStatus.PROCESSING,
                attempts=job.attempts + 1,
            )
        except Exception as e:
            self.logger.error(
                "Failed to update job to PROCESSING",
                job_id=job.job_id,
                error=str(e),
            )
            return False

        # Process job with retry logic
        for attempt in range(self.max_retries):
            try:
                # Simulate work (in real implementation, this would do actual work)
                result = self._execute_job(job)

                # Update to SUCCEEDED
                self.dynamodb_repo.update_job(
                    job.job_id,
                    JobStatus.SUCCEEDED,
                    result=result,
                    attempts=job.attempts + 1 + attempt,
                )

                # Delete message from queue
                self.sqs_client.delete_message(queue_url, receipt_handle)

                # Emit metrics
                duration = (time.time() - start_time) * 1000  # Convert to milliseconds
                self.metrics_client.put_metric("JobsProcessed", 1.0)
                self.metrics_client.put_metric("JobProcessingDuration", duration, "Milliseconds")

                self.logger.info(
                    "Job processed successfully",
                    job_id=job.job_id,
                    duration_ms=duration,
                    attempts=job.attempts + 1 + attempt,
                    trace_id=trace_id,
                )

                return True

            except Exception as e:
                error_str = str(e)
                self.logger.warning(
                    "Job processing attempt failed",
                    job_id=job.job_id,
                    attempt=attempt + 1,
                    error=error_str,
                    trace_id=trace_id,
                )

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    # Permanent failure - let SQS redrive handle it
                    self.logger.error(
                        "Permanent failure, returning message to queue",
                        job_id=job.job_id,
                        error=error_str,
                        trace_id=trace_id,
                    )
                    self.metrics_client.put_metric("JobsProcessedFailed", 1.0)
                    return False

                # Retryable error - exponential backoff
                if attempt < self.max_retries - 1:
                    backoff = self._calculate_backoff(attempt)
                    self.logger.info(
                        "Retrying with exponential backoff",
                        job_id=job.job_id,
                        attempt=attempt + 1,
                        backoff_seconds=backoff,
                        trace_id=trace_id,
                    )
                    time.sleep(backoff)
                else:
                    # Max retries exceeded
                    self.logger.error(
                        "Max retries exceeded, returning message to queue",
                        job_id=job.job_id,
                        error=error_str,
                        trace_id=trace_id,
                    )
                    self.metrics_client.put_metric("JobsProcessedFailed", 1.0)
                    return False

        return False

    def _execute_job(self, job: Job) -> dict:
        """Execute the actual job work (simulated)."""
        # Simulate work based on job type
        if job.job_type == "process_document":
            time.sleep(0.5)  # Simulate processing time
            return {
                "status": "processed",
                "output": f"Processed document from {job.params.get('source', 'unknown')}",
            }
        elif job.job_type == "generate_report":
            time.sleep(1.0)
            return {
                "status": "generated",
                "report_url": f"s3://bucket/reports/{job.job_id}.pdf",
            }
        elif job.job_type == "transform_data":
            time.sleep(0.3)
            return {
                "status": "transformed",
                "records_processed": 100,
            }
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")


"""Unit tests for JobProcessor."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from svc_worker.service.job_processor import JobProcessor
from svc_worker.domain.job import Job, JobStatus


@pytest.fixture
def mock_dynamodb_repo():
    """Mock DynamoDB repository."""
    repo = Mock()
    repo.get_job.return_value = None
    repo.update_job.return_value = None
    return repo


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client."""
    client = Mock()
    client.delete_message.return_value = None
    return client


@pytest.fixture
def mock_metrics_client():
    """Mock Metrics client."""
    client = Mock()
    client.put_metric.return_value = None
    return client


@pytest.fixture
def mock_logger():
    """Mock logger."""
    logger = Mock()
    logger.info.return_value = None
    logger.error.return_value = None
    logger.warning.return_value = None
    return logger


@pytest.fixture
def job_processor(
    mock_dynamodb_repo,
    mock_sqs_client,
    mock_metrics_client,
    mock_logger,
):
    """Create JobProcessor instance."""
    return JobProcessor(
        dynamodb_repo=mock_dynamodb_repo,
        sqs_client=mock_sqs_client,
        metrics_client=mock_metrics_client,
        logger=mock_logger,
    )


@pytest.fixture
def sample_job():
    """Create a sample job."""
    return Job(
        job_id="test-job-123",
        status=JobStatus.PENDING,
        job_type="process_document",
        priority="normal",
        params={"source": "s3://bucket/test.pdf"},
        trace_id="trace-123",
    )


def test_process_job_success(job_processor, sample_job, mock_dynamodb_repo, mock_sqs_client):
    """Test successful job processing."""
    # Mock the _execute_job method to return success
    with patch.object(job_processor, '_execute_job', return_value={"status": "processed"}):
        result = job_processor.process_job(
            job=sample_job,
            receipt_handle="receipt-123",
            queue_url="http://localhost:4566/queue",
        )
    
    assert result is True
    mock_dynamodb_repo.update_job.assert_called()
    mock_sqs_client.delete_message.assert_called_once()


def test_process_job_idempotency_already_succeeded(job_processor, mock_sqs_client):
    """Test that already succeeded jobs are skipped."""
    succeeded_job = Job(
        job_id="test-job-123",
        status=JobStatus.SUCCEEDED,
        job_type="process_document",
        priority="normal",
        params={},
    )
    
    result = job_processor.process_job(
        job=succeeded_job,
        receipt_handle="receipt-123",
        queue_url="http://localhost:4566/queue",
    )
    
    assert result is True
    # Message should be deleted since job is already processed
    mock_sqs_client.delete_message.assert_called_once()


def test_process_job_idempotency_already_failed_final(job_processor, mock_sqs_client):
    """Test that already failed_final jobs are skipped."""
    failed_job = Job(
        job_id="test-job-123",
        status=JobStatus.FAILED_FINAL,
        job_type="process_document",
        priority="normal",
        params={},
    )
    
    result = job_processor.process_job(
        job=failed_job,
        receipt_handle="receipt-123",
        queue_url="http://localhost:4566/queue",
    )
    
    assert result is True
    # Message should be deleted since job is already processed
    mock_sqs_client.delete_message.assert_called_once()


def test_process_job_retryable_error(job_processor, sample_job, mock_dynamodb_repo):
    """Test that retryable errors trigger retry logic."""
    # Mock _execute_job to raise a retryable error
    with patch.object(
        job_processor, 
        '_execute_job', 
        side_effect=Exception("500 Internal Server Error")
    ):
        result = job_processor.process_job(
            job=sample_job,
            receipt_handle="receipt-123",
            queue_url="http://localhost:4566/queue",
        )
    
    # Should return False (message will be retried by SQS)
    assert result is False
    # Should have tried to update job status
    assert mock_dynamodb_repo.update_job.called


def test_is_retryable_error(job_processor):
    """Test retryable error detection."""
    # Retryable errors
    assert job_processor._is_retryable_error(Exception("500 Internal Server Error"))
    assert job_processor._is_retryable_error(Exception("503 Service Unavailable"))
    assert job_processor._is_retryable_error(Exception("ThrottlingException"))
    assert job_processor._is_retryable_error(Exception("Connection timeout"))
    
    # Non-retryable errors
    assert not job_processor._is_retryable_error(Exception("400 Bad Request"))
    assert not job_processor._is_retryable_error(Exception("404 Not Found"))
    assert not job_processor._is_retryable_error(Exception("Invalid input"))


def test_calculate_backoff(job_processor):
    """Test exponential backoff calculation."""
    assert job_processor._calculate_backoff(0) == 1.0  # Initial
    assert job_processor._calculate_backoff(1) == 2.0  # 1 * 2^1
    assert job_processor._calculate_backoff(2) == 4.0  # 1 * 2^2
    assert job_processor._calculate_backoff(3) == 8.0  # 1 * 2^3
    
    # Should cap at max_backoff (30.0)
    assert job_processor._calculate_backoff(10) <= 30.0


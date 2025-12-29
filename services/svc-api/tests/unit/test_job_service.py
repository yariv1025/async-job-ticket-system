"""Unit tests for JobService."""

import pytest
from unittest.mock import Mock, MagicMock
from svc_api.service.job_service import JobService
from svc_api.domain.job import Job, JobStatus


@pytest.fixture
def mock_dynamodb_repo():
    """Mock DynamoDB repository."""
    repo = Mock()
    repo.get_job_by_idempotency_key.return_value = None
    repo.put_job.return_value = None
    repo.get_job.return_value = None
    return repo


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client."""
    client = Mock()
    client.send_message.return_value = "message-id-123"
    return client


@pytest.fixture
def mock_parameter_store():
    """Mock Parameter Store client."""
    store = Mock()
    store.get_parameter.return_value = "http://localhost:4566/000000000000/jobs-queue"
    return store


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
def job_service(
    mock_dynamodb_repo,
    mock_sqs_client,
    mock_parameter_store,
    mock_metrics_client,
    mock_logger,
):
    """Create JobService instance."""
    return JobService(
        dynamodb_repo=mock_dynamodb_repo,
        sqs_client=mock_sqs_client,
        parameter_store=mock_parameter_store,
        metrics_client=mock_metrics_client,
        logger=mock_logger,
    )


def test_create_job_success(job_service, mock_dynamodb_repo, mock_sqs_client):
    """Test successful job creation."""
    job = job_service.create_job(
        job_type="process_document",
        priority="normal",
        params={"source": "s3://bucket/key"},
    )

    assert job.status == JobStatus.PENDING
    assert job.job_type == "process_document"
    mock_dynamodb_repo.put_job.assert_called_once()
    mock_sqs_client.send_message.assert_called_once()


def test_create_job_idempotency(job_service, mock_dynamodb_repo, mock_sqs_client):
    """Test idempotency key handling."""
    existing_job = Job.create(
        job_type="process_document",
        priority="normal",
        params={"source": "s3://bucket/key"},
        idempotency_key="test-key-123",
    )
    mock_dynamodb_repo.get_job_by_idempotency_key.return_value = existing_job

    job = job_service.create_job(
        job_type="process_document",
        priority="normal",
        params={"source": "s3://bucket/key"},
        idempotency_key="test-key-123",
    )

    assert job.job_id == existing_job.job_id
    mock_dynamodb_repo.put_job.assert_not_called()
    mock_sqs_client.send_message.assert_not_called()


def test_create_job_sqs_failure_compensation(
    job_service, mock_dynamodb_repo, mock_sqs_client
):
    """Test compensation when SQS publish fails."""
    mock_sqs_client.send_message.side_effect = Exception("SQS error")

    with pytest.raises(RuntimeError):
        job_service.create_job(
            job_type="process_document",
            priority="normal",
            params={"source": "s3://bucket/key"},
        )

    # Verify job was created in DynamoDB
    mock_dynamodb_repo.put_job.assert_called_once()
    # Verify status was updated to FAILED
    from unittest.mock import ANY
    mock_dynamodb_repo.update_job_status.assert_called_once_with(
        ANY, JobStatus.FAILED.value, ANY
    )


def test_get_job(job_service, mock_dynamodb_repo):
    """Test getting a job."""
    test_job = Job.create(
        job_type="process_document",
        priority="normal",
        params={"source": "s3://bucket/key"},
    )
    mock_dynamodb_repo.get_job.return_value = test_job

    job = job_service.get_job(test_job.job_id)

    assert job is not None
    assert job.job_id == test_job.job_id
    mock_dynamodb_repo.get_job.assert_called_once_with(test_job.job_id)


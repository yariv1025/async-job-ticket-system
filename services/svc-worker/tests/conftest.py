"""Pytest configuration and fixtures."""

import os
import pytest
from moto import mock_dynamodb, mock_sqs
import boto3

# Set test environment variables
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["DDB_TABLE"] = "Jobs"
os.environ["SQS_QUEUE_URL"] = "http://localhost:4566/000000000000/jobs-queue"
os.environ["ENV"] = "test"


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="Jobs",
            KeySchema=[{"AttributeName": "jobId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "jobId", "AttributeType": "S"},
                {"AttributeName": "idempotencyKey", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "idempotencyKey-index",
                    "KeySchema": [{"AttributeName": "idempotencyKey", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                }
            ],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        yield table


@pytest.fixture
def sqs_queue():
    """Create a mock SQS queue."""
    with mock_sqs():
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jobs-queue")["QueueUrl"]
        yield queue_url


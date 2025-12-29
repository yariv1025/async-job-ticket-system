"""DynamoDB client implementation."""

import os
import boto3
from typing import Optional
from botocore.exceptions import ClientError
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch as xray_patch

from ..domain.job import Job
from ..domain.interfaces import DynamoDBRepository

# Patch boto3 for X-Ray
xray_patch(["boto3"])


class DynamoDBRepositoryImpl(DynamoDBRepository):
    """DynamoDB repository implementation."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        """Initialize DynamoDB client."""
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint_url,
        )
        self.table = self.dynamodb.Table(table_name)

    @xray_recorder.capture("dynamodb_put_job")
    def put_job(self, job: Job) -> None:
        """Store a job in DynamoDB."""
        try:
            item = job.to_dict()
            self.table.put_item(Item=item)
        except ClientError as e:
            raise RuntimeError(f"Failed to put job: {e}") from e

    @xray_recorder.capture("dynamodb_get_job")
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        try:
            response = self.table.get_item(Key={"jobId": job_id})
            if "Item" not in response:
                return None
            return Job.from_dict(response["Item"])
        except ClientError as e:
            raise RuntimeError(f"Failed to get job: {e}") from e

    @xray_recorder.capture("dynamodb_get_job_by_idempotency_key")
    def get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[Job]:
        """Retrieve a job by idempotency key using GSI."""
        try:
            response = self.table.query(
                IndexName="idempotencyKey-index",
                KeyConditionExpression="idempotencyKey = :key",
                ExpressionAttributeValues={":key": idempotency_key},
                Limit=1,
            )
            if not response.get("Items"):
                return None
            return Job.from_dict(response["Items"][0])
        except ClientError as e:
            raise RuntimeError(f"Failed to get job by idempotency key: {e}") from e

    @xray_recorder.capture("dynamodb_update_job_status")
    def update_job_status(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        """Update job status."""
        from datetime import datetime, UTC

        try:
            update_expression = "SET #status = :status, updatedAt = :updated_at"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": status,
                ":updated_at": datetime.now(UTC).isoformat(),
            }

            if error:
                update_expression += ", #error = :error"
                expression_attribute_names["#error"] = "error"
                expression_attribute_values[":error"] = error

            self.table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to update job status: {e}") from e


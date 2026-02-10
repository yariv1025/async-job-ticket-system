"""DynamoDB client implementation."""

import os
import boto3
from typing import Optional
from botocore.exceptions import ClientError
from .xray import should_patch_xray, xray_capture

from ..domain.interfaces import DynamoDBRepository
from ..domain.job import Job, JobStatus

# Patch boto3 for X-Ray only if not in local dev
if should_patch_xray():
    from aws_xray_sdk.core import patch as xray_patch
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

    @xray_capture("dynamodb_get_job")
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        try:
            response = self.table.get_item(Key={"jobId": job_id})
            if "Item" not in response:
                return None
            return Job.from_dict(response["Item"])
        except ClientError as e:
            raise RuntimeError(f"Failed to get job: {e}") from e

    @xray_capture("dynamodb_update_job")
    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
    ) -> None:
        """Update job status and other fields."""
        from datetime import datetime, UTC

        try:
            update_expression = "SET #status = :status, updatedAt = :updated_at"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": status.value,
                ":updated_at": datetime.now(UTC).isoformat(),
            }

            if result is not None:
                update_expression += ", #result = :result"
                expression_attribute_names["#result"] = "result"
                expression_attribute_values[":result"] = result

            if error is not None:
                update_expression += ", #error = :error"
                expression_attribute_names["#error"] = "error"
                expression_attribute_values[":error"] = error

            if attempts is not None:
                update_expression += ", attempts = :attempts"
                expression_attribute_values[":attempts"] = attempts

            self.table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to update job: {e}") from e


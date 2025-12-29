"""SQS client implementation."""

import os
import json
import boto3
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
from ..infra.xray import should_patch_xray, xray_capture

# Patch boto3 for X-Ray only if not in local dev
if should_patch_xray():
    from aws_xray_sdk.core import patch as xray_patch
    xray_patch(["boto3"])


class SQSClient:
    """SQS client implementation."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize SQS client."""
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.sqs = boto3.client(
            "sqs",
            region_name=region,
            endpoint_url=endpoint_url,
        )

    @xray_capture("sqs_receive_messages")
    def receive_messages(
        self,
        queue_url: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> List[Dict[str, Any]]:
        """Receive messages from SQS with long polling."""
        try:
            response = self.sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=["All"],
            )
            return response.get("Messages", [])
        except ClientError as e:
            raise RuntimeError(f"Failed to receive messages from SQS: {e}") from e

    @xray_capture("sqs_delete_message")
    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        """Delete a message from SQS."""
        try:
            self.sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to delete message from SQS: {e}") from e

    @xray_capture("sqs_change_message_visibility")
    def change_message_visibility(
        self, queue_url: str, receipt_handle: str, visibility_timeout: int
    ) -> None:
        """Change message visibility timeout."""
        try:
            self.sqs.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=visibility_timeout,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to change message visibility: {e}") from e

    @xray_capture("sqs_get_queue_attributes")
    def get_queue_attributes(self, queue_url: str) -> Dict[str, Any]:
        """Get queue attributes (for approximate queue depth)."""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
            )
            return response.get("Attributes", {})
        except ClientError as e:
            raise RuntimeError(f"Failed to get queue attributes: {e}") from e


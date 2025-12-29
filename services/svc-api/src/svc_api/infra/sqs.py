"""SQS client implementation."""

import os
import json
import boto3
from typing import Dict, Any
from botocore.exceptions import ClientError
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch as xray_patch

from ..domain.interfaces import SQSClient

# Patch boto3 for X-Ray
xray_patch(["boto3"])


class SQSClientImpl(SQSClient):
    """SQS client implementation."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize SQS client."""
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.sqs = boto3.client(
            "sqs",
            region_name=region,
            endpoint_url=endpoint_url,
        )

    @xray_recorder.capture("sqs_send_message")
    def send_message(
        self, queue_url: str, message_body: str, message_attributes: Dict[str, Any]
    ) -> str:
        """Send a message to SQS."""
        try:
            # Convert message attributes to SQS format
            sqs_attributes = {}
            for key, value in message_attributes.items():
                if isinstance(value, str):
                    sqs_attributes[key] = {"StringValue": value, "DataType": "String"}
                elif isinstance(value, (int, float)):
                    sqs_attributes[key] = {"StringValue": str(value), "DataType": "Number"}

            response = self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=message_body,
                MessageAttributes=sqs_attributes,
            )
            return response["MessageId"]
        except ClientError as e:
            raise RuntimeError(f"Failed to send message to SQS: {e}") from e


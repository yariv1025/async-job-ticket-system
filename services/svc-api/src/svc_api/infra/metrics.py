"""CloudWatch Metrics client implementation."""

import os
import boto3
from typing import Optional
from botocore.exceptions import ClientError
from aws_xray_sdk.core import xray_recorder

from ..domain.interfaces import MetricsClient


class CloudWatchMetricsClient(MetricsClient):
    """CloudWatch Metrics client implementation."""

    def __init__(self, namespace: str = "JobsSystem", region: str = "us-east-1"):
        """Initialize CloudWatch client."""
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.cloudwatch = boto3.client(
            "cloudwatch",
            region_name=region,
            endpoint_url=endpoint_url,
        )
        self.namespace = namespace

    @xray_recorder.capture("cloudwatch_put_metric")
    def put_metric(self, metric_name: str, value: float, unit: str = "Count") -> None:
        """Put a custom metric."""
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                    }
                ],
            )
        except ClientError as e:
            # Don't fail the request if metrics fail
            print(f"Failed to put metric {metric_name}: {e}")


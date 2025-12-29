"""Parameter Store client implementation."""

import os
import boto3
from typing import Optional
from botocore.exceptions import ClientError

from ..domain.interfaces import ParameterStoreClient


class ParameterStoreClientImpl(ParameterStoreClient):
    """Parameter Store client implementation."""

    def __init__(self, region: str = "us-east-1", env: str = "dev"):
        """Initialize SSM client."""
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.ssm = boto3.client(
            "ssm",
            region_name=region,
            endpoint_url=endpoint_url,
        )
        self.env = env
        self._cache: dict[str, str] = {}

    def get_parameter(self, name: str) -> str:
        """Get a parameter value (with caching)."""
        # Check cache first
        if name in self._cache:
            return self._cache[name]

        # Build full parameter name
        full_name = f"/jobsys/{self.env}/{name}"

        try:
            response = self.ssm.get_parameter(Name=full_name, WithDecryption=False)
            value = response["Parameter"]["Value"]
            # Cache it
            self._cache[name] = value
            return value
        except ClientError as e:
            raise RuntimeError(f"Failed to get parameter {full_name}: {e}") from e


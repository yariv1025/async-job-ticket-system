"""X-Ray instrumentation setup."""

import os
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch as xray_patch


def setup_xray(service_name: str = "svc-api"):
    """Set up X-Ray tracing."""
    # Only enable X-Ray if not in local development
    if os.getenv("AWS_ENDPOINT_URL"):
        # Local development - disable X-Ray
        return

    xray_recorder.configure(
        service=service_name,
        sampling_rules={"version": 1, "default": {"fixed_target": 1, "rate": 0.1}},
    )

    # Patch boto3 for X-Ray tracing
    xray_patch(["boto3"])


def get_xray_middleware_class():
    """Get X-Ray middleware class for FastAPI.
    
    Note: X-Ray SDK doesn't have built-in FastAPI middleware.
    For local development, X-Ray is disabled anyway.
    In production, X-Ray will trace boto3 calls automatically.
    """
    # Always return None - we'll rely on boto3 patching for X-Ray
    # FastAPI middleware would require custom implementation
    return None


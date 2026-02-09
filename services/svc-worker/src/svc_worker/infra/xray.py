"""X-Ray instrumentation setup."""

import os
from functools import wraps
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch as xray_patch

# Check if we're in local development
_IS_LOCAL = bool(os.getenv("AWS_ENDPOINT_URL"))


def setup_xray(service_name: str = "svc-worker"):
    """Set up X-Ray tracing."""
    # Only enable X-Ray if not in local development
    if _IS_LOCAL:
        # Local development - disable X-Ray completely (don't configure it)
        return

    xray_recorder.configure(
        service=service_name,
        sampling_rules={"version": 1, "default": {"fixed_target": 1, "rate": 0.1}},
    )

    # Patch boto3 for X-Ray tracing
    xray_patch(["boto3"])


def should_patch_xray():
    """Check if X-Ray patching should be enabled."""
    return not _IS_LOCAL


def xray_capture(name):
    """Conditional X-Ray capture decorator - no-op in local dev."""
    def decorator(func):
        if _IS_LOCAL:
            # In local dev, just return the function unchanged
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        # In production, use X-Ray capture
        return xray_recorder.capture(name)(func)
    return decorator


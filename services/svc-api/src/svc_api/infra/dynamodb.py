"""DynamoDB client implementation."""

import os
import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer

from ..domain.job import Job
from ..domain.interfaces import DynamoDBRepository

# Check if we're in local development
_IS_LOCAL = bool(os.getenv("AWS_ENDPOINT_URL"))

# Conditionally patch boto3 for X-Ray (only in production)
if not _IS_LOCAL:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch as xray_patch
    xray_patch(["boto3"])
else:
    # Create a no-op xray_recorder for local dev
    class NoOpXRayRecorder:
        def capture(self, name):
            def decorator(func):
                return func
            return decorator
    
    xray_recorder = NoOpXRayRecorder()

# Type serializers for LocalStack compatibility
_type_serializer = TypeSerializer()
_type_deserializer = TypeDeserializer()


class DynamoDBRepositoryImpl(DynamoDBRepository):
    """DynamoDB repository implementation."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        """Initialize DynamoDB client."""
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.table_name = table_name
        self.endpoint_url = endpoint_url
        self.region = region
        
        # Log initialization to confirm local mode detection
        from ..infra.logger import StructLogger
        logger = StructLogger("svc-api")
        logger.info(
            "Initializing DynamoDB repository",
            table_name=table_name,
            region=region,
            endpoint_url=endpoint_url,
            is_local=_IS_LOCAL,
            aws_endpoint_url_env=os.getenv("AWS_ENDPOINT_URL"),
        )
        
        # Use low-level client for better LocalStack compatibility
        self.dynamodb_client = boto3.client(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint_url,
        )
        
        # Also keep resource for queries (it works fine for reads)
        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint_url,
        )
        self.table = self.dynamodb.Table(table_name)

    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize Python types to DynamoDB format using TypeSerializer.
        
        This ensures LocalStack compatibility by explicitly converting
        all types to DynamoDB's expected format.
        """
        import json
        from ..infra.logger import StructLogger
        
        logger = StructLogger("svc-api")
        serialized = {}
        for key, value in item.items():
            if value is None:
                continue  # Skip None values
            # Log the value before serialization for debugging
            if key == "params":
                logger.info(
                    "Serializing params",
                    params_value=value,
                    params_type=type(value).__name__,
                    params_is_empty=value == {},
                )
            # Use TypeSerializer to convert Python types to DynamoDB types
            try:
                serialized_value = _type_serializer.serialize(value)
                serialized[key] = serialized_value
                # Log serialized structure for params
                if key == "params":
                    logger.info(
                        "Serialized params",
                        serialized_structure=json.dumps(serialized_value, default=str)[:200],
                    )
            except Exception as e:
                logger.error(
                    "Failed to serialize value",
                    key=key,
                    value_type=type(value).__name__,
                    value_preview=str(value)[:100],
                    error=str(e),
                )
                raise
        return serialized

    @xray_recorder.capture("dynamodb_put_job")
    def put_job(self, job: Job) -> None:
        """Store a job in DynamoDB."""
        import json
        from ..infra.logger import StructLogger
        
        logger = StructLogger("svc-api")
        
        try:
            item = job.to_dict()
            # Log the item before processing
            logger.info(
                "Preparing item for DynamoDB",
                item_keys=list(item.keys()),
                params_type=type(item.get("params")).__name__,
                params_value=item.get("params"),
                attempts_type=type(item.get("attempts")).__name__,
                expiresAt_type=type(item.get("expiresAt")).__name__,
            )
            
            # Ensure params is always a dict (required field)
            if "params" not in item or not isinstance(item.get("params"), dict):
                item["params"] = {}
            
            # For LocalStack, use explicit type serialization with low-level client
            if _IS_LOCAL:
                # Serialize the item explicitly for LocalStack compatibility
                serialized_item = self._serialize_item(item)
                # Log the serialized item structure
                logger.info(
                    "Sending serialized item to DynamoDB",
                    serialized_keys=list(serialized_item.keys()),
                    serialized_item_preview=json.dumps(
                        {k: str(v)[:50] for k, v in serialized_item.items()},
                        default=str
                    )[:500],
                )
                self.dynamodb_client.put_item(
                    TableName=self.table_name,
                    Item=serialized_item
                )
            else:
                # For real AWS, boto3.resource handles conversion automatically
                self.table.put_item(Item=item)
        except ClientError as e:
            # Log more details about the error for debugging
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            # Include item structure in error for debugging
            item_keys = list(item.keys()) if 'item' in locals() else []
            item_params_type = type(item.get("params")).__name__ if 'item' in locals() else "N/A"
            # Log the actual item structure (sanitized)
            item_preview = {k: type(v).__name__ for k, v in item.items()} if 'item' in locals() else {}
            
            logger.error(
                "DynamoDB PutItem failed",
                error_code=error_code,
                error_message=error_message,
                item_keys=item_keys,
                params_type=item_params_type,
                item_types=item_preview,
            )
            
            raise RuntimeError(
                f"Failed to put job: {error_code} - {error_message}. "
                f"Item keys: {item_keys}, params type: {item_params_type}, "
                f"item types: {item_preview}"
            ) from e

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


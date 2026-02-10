"""Lambda handler for DLQ messages."""

import json
import logging
import os
import boto3
from typing import Any, Dict
from botocore.exceptions import ClientError
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch as xray_patch

# Patch boto3 for X-Ray
xray_patch(["boto3"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
table_name = os.getenv("DDB_TABLE", "Jobs")
table = dynamodb.Table(table_name)


@xray_recorder.capture("dlq_handler")
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process DLQ messages and mark jobs as FAILED_FINAL."""
    from datetime import datetime, UTC

    processed_count = 0
    failed_count = 0

    # Process each record in the SQS event
    for record in event.get("Records", []):
        try:
            # Parse SQS message body
            body = json.loads(record["body"])
            job_id = body.get("jobId")

            if not job_id:
                logger.warning(
                    "Message missing jobId",
                    extra={"message_id": record.get("messageId")},
                )
                failed_count += 1
                continue

            # Get original error from message attributes or body
            error_message = body.get("error", "Job failed after max retries")

            # Update job status to FAILED_FINAL
            try:
                table.update_item(
                    Key={"jobId": job_id},
                    UpdateExpression="SET #status = :status, updatedAt = :updated_at, #error = :error",
                    ExpressionAttributeNames={
                        "#status": "status",
                        "#error": "error",
                    },
                    ExpressionAttributeValues={
                        ":status": "FAILED_FINAL",
                        ":updated_at": datetime.now(UTC).isoformat(),
                        ":error": error_message,
                    },
                )

                logger.info(
                    "Marked job as FAILED_FINAL",
                    extra={"job_id": job_id},
                )
                processed_count += 1

            except ClientError as e:
                logger.error(
                    "Failed to update job",
                    extra={"job_id": job_id, "error": str(e)},
                )
                failed_count += 1

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse message", extra={"error": str(e)})
            failed_count += 1
        except Exception as e:
            logger.error("Error processing record", extra={"error": str(e)})
            failed_count += 1

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": processed_count,
            "failed": failed_count,
        }),
    }


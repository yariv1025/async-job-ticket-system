"""Lambda handler for DLQ messages."""

import os
import json
import boto3
from typing import Dict, Any
from botocore.exceptions import ClientError
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch as xray_patch

# Patch boto3 for X-Ray
xray_patch(["boto3"])

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
                print(f"Message missing jobId: {record.get('messageId')}")
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

                print(f"Marked job {job_id} as FAILED_FINAL")
                processed_count += 1

            except ClientError as e:
                print(f"Failed to update job {job_id}: {e}")
                failed_count += 1

        except json.JSONDecodeError as e:
            print(f"Failed to parse message: {e}")
            failed_count += 1
        except Exception as e:
            print(f"Error processing record: {e}")
            failed_count += 1

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": processed_count,
            "failed": failed_count,
        }),
    }


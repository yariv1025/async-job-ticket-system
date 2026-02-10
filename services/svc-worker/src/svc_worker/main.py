"""Worker service main entry point."""

import os
import json
import signal
import sys
import time
from typing import Optional

from .infra.dynamodb import DynamoDBRepositoryImpl
from .infra.sqs import SQSClientImpl
from .infra.parameter_store import ParameterStoreClient
from .infra.metrics import CloudWatchMetricsClient
from .infra.logger import setup_logging, StructLogger
from .infra.xray import setup_xray
from .service.job_processor import JobProcessor
from .domain.job import Job

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level)
logger = StructLogger("svc-worker")

# Setup X-Ray
setup_xray("svc-worker")

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    global shutdown_flag
    logger.info("Received shutdown signal, shutting down gracefully...")
    shutdown_flag = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main worker loop."""
    logger.info("Starting svc-worker...")

    # Get configuration
    env = os.getenv("ENV", "dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    # Get table name and queue URL from environment or Parameter Store
    table_name = os.getenv("DDB_TABLE", "Jobs")
    queue_url = os.getenv("SQS_QUEUE_URL", "")
    
    # Only try Parameter Store if not using LocalStack
    if not os.getenv("AWS_ENDPOINT_URL"):
        # Only try Parameter Store in real AWS (not LocalStack)
        try:
            parameter_store = ParameterStoreClient(region=region, env=env)
            table_name = os.getenv("DDB_TABLE", parameter_store.get_parameter("dynamodb/table-name"))
            queue_url = os.getenv("SQS_QUEUE_URL", parameter_store.get_parameter("sqs/queue-url"))
        except Exception as e:
            logger.warning(f"Failed to get parameters from Parameter Store, using env vars: {e}")
            table_name = os.getenv("DDB_TABLE", "Jobs")
            queue_url = os.getenv("SQS_QUEUE_URL", "")
    else:
        logger.info("Using LocalStack - using environment variables only")

    if not queue_url:
        logger.error("SQS_QUEUE_URL not configured")
        sys.exit(1)

    # Initialize infrastructure clients
    dynamodb_repo = DynamoDBRepositoryImpl(table_name=table_name, region=region)
    sqs_client = SQSClientImpl(region=region)
    metrics_client = CloudWatchMetricsClient(namespace="JobsSystem", region=region)

    # Initialize job processor
    processor = JobProcessor(
        dynamodb_repo=dynamodb_repo,
        sqs_client=sqs_client,
        metrics_client=metrics_client,
        logger=logger,
    )

    logger.info(
        "svc-worker started successfully; polling SQS",
        table_name=table_name,
        queue_url=queue_url,
    )

    # Main processing loop
    max_messages = int(os.getenv("MAX_MESSAGES", "10"))
    wait_time_seconds = int(os.getenv("WAIT_TIME_SECONDS", "20"))

    while not shutdown_flag:
        try:
            # Long poll for messages
            messages = sqs_client.receive_messages(
                queue_url=queue_url,
                max_messages=max_messages,
                wait_time_seconds=wait_time_seconds,
            )

            if not messages:
                # Log that we're still polling (but not too frequently)
                continue

            logger.info("Received messages", count=len(messages))

            # Process each message
            for message in messages:
                if shutdown_flag:
                    break

                try:
                    # Parse message body
                    body = json.loads(message["Body"])
                    job_id = body.get("jobId")

                    if not job_id:
                        logger.warning("Message missing jobId, skipping", message_id=message.get("MessageId"))
                        continue

                    # Get job from DynamoDB
                    job = dynamodb_repo.get_job(job_id)
                    if not job:
                        logger.warning("Job not found in DynamoDB, skipping", job_id=job_id)
                        # Delete message since job doesn't exist
                        sqs_client.delete_message(queue_url, message["ReceiptHandle"])
                        continue

                    # Process job
                    success = processor.process_job(
                        job=job,
                        receipt_handle=message["ReceiptHandle"],
                        queue_url=queue_url,
                    )

                    if not success:
                        logger.warning(
                            "Job processing failed, message will be retried",
                            job_id=job_id,
                        )

                except json.JSONDecodeError as e:
                    logger.error("Failed to parse message body", error=str(e), message_id=message.get("MessageId"))
                    # Delete malformed message
                    try:
                        sqs_client.delete_message(queue_url, message["ReceiptHandle"])
                    except Exception:
                        pass
                except Exception as e:
                    logger.error("Error processing message", error=str(e), message_id=message.get("MessageId"))

            # Update queue depth metric
            try:
                attributes = sqs_client.get_queue_attributes(queue_url)
                approximate_messages = int(attributes.get("ApproximateNumberOfMessages", 0))
                metrics_client.put_metric("SQSQueueDepth", float(approximate_messages), "Count")
            except Exception as e:
                logger.warning("Failed to get queue attributes", error=str(e))

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("Error in main loop", error=str(e))
            time.sleep(5)  # Back off on errors

    logger.info("svc-worker stopped")


if __name__ == "__main__":
    main()


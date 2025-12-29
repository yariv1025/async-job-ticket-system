#!/bin/bash
# Create SQS queues (main queue and DLQ) with redrive policy

set -e

QUEUE_NAME="${QUEUE_NAME:-jobs-queue}"
DLQ_NAME="${DLQ_NAME:-jobs-dlq}"
REGION="${AWS_REGION:-us-east-1}"
MAX_RECEIVE_COUNT="${MAX_RECEIVE_COUNT:-3}"

echo "Creating SQS queues in region: $REGION"

# Create DLQ first
echo "Creating DLQ: $DLQ_NAME"
DLQ_URL=$(aws sqs create-queue \
    --queue-name "$DLQ_NAME" \
    --attributes '{
        "MessageRetentionPeriod": "1209600"
    }' \
    --region "$REGION" \
    --query 'QueueUrl' \
    --output text)

echo "DLQ URL: $DLQ_URL"

# Get DLQ ARN
DLQ_ARN=$(aws sqs get-queue-attributes \
    --queue-url "$DLQ_URL" \
    --attribute-names QueueArn \
    --region "$REGION" \
    --query 'Attributes.QueueArn' \
    --output text)

echo "DLQ ARN: $DLQ_ARN"

# Create main queue with redrive policy
echo "Creating main queue: $QUEUE_NAME"
QUEUE_URL=$(aws sqs create-queue \
    --queue-name "$QUEUE_NAME" \
    --attributes "{
        \"ReceiveMessageWaitTimeSeconds\": \"20\",
        \"MessageRetentionPeriod\": \"1209600\",
        \"VisibilityTimeout\": \"30\",
        \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":$MAX_RECEIVE_COUNT}\"
    }" \
    --region "$REGION" \
    --query 'QueueUrl' \
    --output text)

echo "Queue URL: $QUEUE_URL"

echo "✅ SQS queues created successfully!"
echo "   Main Queue: $QUEUE_URL"
echo "   DLQ: $DLQ_URL"


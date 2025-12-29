#!/bin/bash
# Set up Parameter Store entries for configuration

set -e

ENV="${ENV:-dev}"
REGION="${AWS_REGION:-us-east-1}"
TABLE_NAME="${TABLE_NAME:-Jobs}"
QUEUE_NAME="${QUEUE_NAME:-jobs-queue}"
DLQ_NAME="${DLQ_NAME:-jobs-dlq}"

echo "Setting up Parameter Store entries for environment: $ENV in region: $REGION"

# Get queue URLs
QUEUE_URL=$(aws sqs get-queue-url \
    --queue-name "$QUEUE_NAME" \
    --region "$REGION" \
    --query 'QueueUrl' \
    --output text)

DLQ_URL=$(aws sqs get-queue-url \
    --queue-name "$DLQ_NAME" \
    --region "$REGION" \
    --query 'QueueUrl' \
    --output text)

# Create parameters
echo "Creating Parameter Store entries..."

aws ssm put-parameter \
    --name "/jobsys/$ENV/dynamodb/table-name" \
    --value "$TABLE_NAME" \
    --type "String" \
    --region "$REGION" \
    --overwrite \
    >/dev/null 2>&1 || echo "Parameter may already exist"

aws ssm put-parameter \
    --name "/jobsys/$ENV/sqs/queue-url" \
    --value "$QUEUE_URL" \
    --type "String" \
    --region "$REGION" \
    --overwrite \
    >/dev/null 2>&1 || echo "Parameter may already exist"

aws ssm put-parameter \
    --name "/jobsys/$ENV/sqs/dlq-url" \
    --value "$DLQ_URL" \
    --type "String" \
    --region "$REGION" \
    --overwrite \
    >/dev/null 2>&1 || echo "Parameter may already exist"

aws ssm put-parameter \
    --name "/jobsys/$ENV/aws/region" \
    --value "$REGION" \
    --type "String" \
    --region "$REGION" \
    --overwrite \
    >/dev/null 2>&1 || echo "Parameter may already exist"

echo "✅ Parameter Store entries created:"
echo "   /jobsys/$ENV/dynamodb/table-name = $TABLE_NAME"
echo "   /jobsys/$ENV/sqs/queue-url = $QUEUE_URL"
echo "   /jobsys/$ENV/sqs/dlq-url = $DLQ_URL"
echo "   /jobsys/$ENV/aws/region = $REGION"


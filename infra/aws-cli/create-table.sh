#!/bin/bash
# Create DynamoDB table for jobs

set -e

TABLE_NAME="${TABLE_NAME:-Jobs}"
REGION="${AWS_REGION:-us-east-1}"

echo "Creating DynamoDB table: $TABLE_NAME in region: $REGION"

aws dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions \
        AttributeName=jobId,AttributeType=S \
        AttributeName=idempotencyKey,AttributeType=S \
    --key-schema \
        AttributeName=jobId,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=idempotencyKey-index,KeySchema=[{AttributeName=idempotencyKey,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}' \
    --billing-mode PROVISIONED \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region "$REGION" \
    --time-to-live-specification Enabled=true,AttributeName=expiresAt

echo "Waiting for table to be active..."
aws dynamodb wait table-exists \
    --table-name "$TABLE_NAME" \
    --region "$REGION"

echo "✅ DynamoDB table created successfully!"


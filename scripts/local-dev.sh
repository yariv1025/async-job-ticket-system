#!/bin/bash
# Local development setup script

set -e

echo "🚀 Setting up local development environment..."

# Start LocalStack
echo "📦 Starting LocalStack..."
docker compose up -d localstack

# Wait for LocalStack to be ready
echo "⏳ Waiting for LocalStack to be ready..."
timeout=60
counter=0
until curl -s http://localhost:4566/_localstack/health | grep -q '"sqs": "available"'; do
    if [ $counter -ge $timeout ]; then
        echo "❌ LocalStack failed to start"
        exit 1
    fi
    sleep 2
    counter=$((counter + 2))
done

echo "✅ LocalStack is ready!"

# Create DynamoDB table
echo "📊 Creating DynamoDB table..."
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name Jobs \
    --attribute-definitions \
        AttributeName=jobId,AttributeType=S \
        AttributeName=idempotencyKey,AttributeType=S \
    --key-schema \
        AttributeName=jobId,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=idempotencyKey-index,KeySchema=[{AttributeName=idempotencyKey,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}' \
    --billing-mode PROVISIONED \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --time-to-live-specification Enabled=true,AttributeName=expiresAt \
    > /dev/null 2>&1 || echo "Table may already exist"

# Create SQS queue
echo "📨 Creating SQS queue..."
QUEUE_URL=$(aws --endpoint-url=http://localhost:4566 sqs create-queue \
    --queue-name jobs-queue \
    --attributes '{
        "ReceiveMessageWaitTimeSeconds": "20",
        "MessageRetentionPeriod": "1209600",
        "VisibilityTimeout": "30"
    }' \
    --query 'QueueUrl' \
    --output text 2>/dev/null || echo "")

if [ -z "$QUEUE_URL" ]; then
    echo "Queue may already exist, getting URL..."
    QUEUE_URL=$(aws --endpoint-url=http://localhost:4566 sqs get-queue-url \
        --queue-name jobs-queue \
        --query 'QueueUrl' \
        --output text)
fi

# Create DLQ
echo "📬 Creating DLQ..."
DLQ_URL=$(aws --endpoint-url=http://localhost:4566 sqs create-queue \
    --queue-name jobs-dlq \
    --attributes '{
        "MessageRetentionPeriod": "1209600"
    }' \
    --query 'QueueUrl' \
    --output text 2>/dev/null || echo "")

if [ -z "$DLQ_URL" ]; then
    echo "DLQ may already exist, getting URL..."
    DLQ_URL=$(aws --endpoint-url=http://localhost:4566 sqs get-queue-url \
        --queue-name jobs-dlq \
        --query 'QueueUrl' \
        --output text)
fi

# Get DLQ ARN
DLQ_ARN=$(aws --endpoint-url=http://localhost:4566 sqs get-queue-attributes \
    --queue-url "$DLQ_URL" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' \
    --output text)

# Attach redrive policy
echo "🔗 Attaching redrive policy..."
aws --endpoint-url=http://localhost:4566 sqs set-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attributes "{
        \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"
    }" \
    > /dev/null 2>&1

echo "✅ Local development environment is ready!"
echo ""
echo "📋 Configuration:"
echo "   DynamoDB Table: Jobs"
echo "   SQS Queue: $QUEUE_URL"
echo "   DLQ: $DLQ_URL"
echo ""
echo "💡 To use with services, set:"
echo "   AWS_ENDPOINT_URL=http://localhost:4566"
echo "   AWS_ACCESS_KEY_ID=test"
echo "   AWS_SECRET_ACCESS_KEY=test"
echo "   AWS_DEFAULT_REGION=us-east-1"


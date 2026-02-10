#!/bin/bash
# Local development setup script

set -e

echo "🚀 Setting up local development environment..."

# Start LocalStack
echo "📦 Starting LocalStack..."
docker compose up -d localstack

# Wait for LocalStack to be ready (both DynamoDB and SQS)
echo "⏳ Waiting for LocalStack to be ready (DynamoDB and SQS)..."
timeout=60
counter=0
while [ $counter -lt $timeout ]; do
    health=$(curl -s http://localhost:4566/_localstack/health 2>/dev/null || true)
    if echo "$health" | grep -q '"dynamodb": "available"' && echo "$health" | grep -q '"sqs": "available"'; then
        break
    fi
    sleep 2
    counter=$((counter + 2))
done
if [ $counter -ge $timeout ]; then
    echo "❌ LocalStack failed to start (DynamoDB and SQS must be available)"
    exit 1
fi

echo "✅ LocalStack is ready!"

# Create DynamoDB table (with retries and verification)
echo "📊 Creating DynamoDB table..."
table_created=false
for attempt in 1 2 3 4 5; do
    if aws --endpoint-url=http://localhost:4566 dynamodb create-table \
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
        2>/dev/null; then
        table_created=true
        break
    fi
    # Table may already exist; verify it's there
    if aws --endpoint-url=http://localhost:4566 dynamodb describe-table --table-name Jobs >/dev/null 2>&1; then
        table_created=true
        echo "   Table 'Jobs' already exists."
        break
    fi
    echo "   Attempt $attempt: table not ready yet, retrying in 3s..."
    sleep 3
done

if [ "$table_created" = false ]; then
    echo "❌ Failed to create or find DynamoDB table 'Jobs'. Check LocalStack logs: docker compose logs localstack"
    exit 1
fi
echo "   DynamoDB table 'Jobs' verified."

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

# Final verification: table must appear in list-tables
if ! aws --endpoint-url=http://localhost:4566 dynamodb list-tables --query 'TableNames' --output text | grep -qw Jobs; then
    echo "❌ Verification failed: table 'Jobs' not found in list-tables. Re-run this script or check LocalStack."
    exit 1
fi

echo "✅ Local development environment is ready!"
echo ""
echo "📋 Configuration:"
echo "   DynamoDB Table: Jobs"
echo "   SQS Queue: $QUEUE_URL"
echo "   DLQ: $DLQ_URL"
echo ""
echo "💡 To use with services, set:"
echo "   export AWS_ENDPOINT_URL=http://localhost:4566"
echo "   export AWS_ACCESS_KEY_ID=test"
echo "   export AWS_SECRET_ACCESS_KEY=test"
echo "   export AWS_DEFAULT_REGION=us-east-1"
echo "   export DDB_TABLE=Jobs"
echo "   export SQS_QUEUE_URL=$QUEUE_URL"
echo ""
echo "   If the API reports 'non-existent table', re-run: ./scripts/local-dev.sh"


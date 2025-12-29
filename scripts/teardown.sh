#!/bin/bash
# Teardown script for cleaning up all resources

set -e

NAMESPACE="jobsys"
REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"

echo "⚠️  This will delete all resources. Are you sure? (yes/no)"
read -r confirmation

if [ "$confirmation" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo "Starting teardown..."

# Delete Kubernetes resources
echo "Deleting Kubernetes resources..."
kubectl delete namespace "$NAMESPACE" --ignore-not-found=true || true

# Delete Lambda function and event source mapping
echo "Deleting Lambda function..."
aws lambda delete-function --function-name "${ENV}-dlq-handler" --region "$REGION" 2>/dev/null || echo "Lambda function not found"

# Delete SQS queues
echo "Deleting SQS queues..."
QUEUE_URL=$(aws sqs get-queue-url --queue-name "jobs-queue" --region "$REGION" --query 'QueueUrl' --output text 2>/dev/null || echo "")
if [ -n "$QUEUE_URL" ]; then
    aws sqs delete-queue --queue-url "$QUEUE_URL" --region "$REGION" || true
fi

DLQ_URL=$(aws sqs get-queue-url --queue-name "jobs-dlq" --region "$REGION" --query 'QueueUrl' --output text 2>/dev/null || echo "")
if [ -n "$DLQ_URL" ]; then
    aws sqs delete-queue --queue-url "$DLQ_URL" --region "$REGION" || true
fi

# Delete DynamoDB table (optional - uncomment if you want to delete)
# echo "Deleting DynamoDB table..."
# aws dynamodb delete-table --table-name "Jobs" --region "$REGION" || true

# Delete Parameter Store entries
echo "Deleting Parameter Store entries..."
aws ssm delete-parameter --name "/jobsys/$ENV/dynamodb/table-name" --region "$REGION" 2>/dev/null || true
aws ssm delete-parameter --name "/jobsys/$ENV/sqs/queue-url" --region "$REGION" 2>/dev/null || true
aws ssm delete-parameter --name "/jobsys/$ENV/sqs/dlq-url" --region "$REGION" 2>/dev/null || true
aws ssm delete-parameter --name "/jobsys/$ENV/aws/region" --region "$REGION" 2>/dev/null || true

# Delete ECR images (optional - uncomment if you want to delete)
# echo "Deleting ECR images..."
# aws ecr batch-delete-image --repository-name svc-api --image-ids imageTag=latest --region "$REGION" 2>/dev/null || true
# aws ecr batch-delete-image --repository-name svc-worker --image-ids imageTag=latest --region "$REGION" 2>/dev/null || true

echo "✅ Teardown complete!"
echo ""
echo "Note: DynamoDB table and ECR repositories were NOT deleted."
echo "      Uncomment the relevant sections in this script if you want to delete them."


#!/bin/bash
# Create ECS Fargate cluster

set -e

CLUSTER_NAME="${CLUSTER_NAME:-jobsys-cluster}"
REGION="${AWS_REGION:-us-east-1}"

echo "Creating ECS Fargate cluster: $CLUSTER_NAME in region: $REGION"

# Create cluster
if aws ecs describe-clusters --clusters "$CLUSTER_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Cluster $CLUSTER_NAME already exists"
else
    aws ecs create-cluster \
        --cluster-name "$CLUSTER_NAME" \
        --capacity-providers FARGATE FARGATE_SPOT \
        --default-capacity-provider-strategy \
            capacityProvider=FARGATE,weight=1 \
        --region "$REGION"

    echo "✅ Cluster created successfully!"
fi

# Create CloudWatch log groups
echo "Creating CloudWatch log groups..."

aws logs create-log-group \
    --log-group-name "/ecs/jobsys/svc-api" \
    --region "$REGION" \
    2>/dev/null || echo "Log group /ecs/jobsys/svc-api already exists"

aws logs create-log-group \
    --log-group-name "/ecs/jobsys/svc-worker" \
    --region "$REGION" \
    2>/dev/null || echo "Log group /ecs/jobsys/svc-worker already exists"

echo "✅ CloudWatch log groups created"

echo ""
echo "Cluster ARN: $(aws ecs describe-clusters --clusters $CLUSTER_NAME --region $REGION --query 'clusters[0].clusterArn' --output text)"


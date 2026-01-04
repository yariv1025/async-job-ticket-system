#!/bin/bash
# Deploy services to ECS Fargate

set -e

CLUSTER_NAME="${CLUSTER_NAME:-jobsys-cluster}"
REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
ECR_ACCOUNT="${ECR_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"
ACCOUNT_ID="$ECR_ACCOUNT"

# Get VPC and subnet information
echo "Getting VPC and subnet information..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --region "$REGION" --query 'Vpcs[0].VpcId' --output text)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" --region "$REGION" --query 'SecurityGroups[0].GroupId' --output text)

if [ -z "$VPC_ID" ] || [ "$VPC_ID" == "None" ]; then
    echo "❌ Error: Could not find default VPC. Please specify VPC_ID, SUBNET_IDS, and SECURITY_GROUP_ID"
    exit 1
fi

echo "Using VPC: $VPC_ID"
echo "Using Subnets: $SUBNET_IDS"
echo "Using Security Group: $SECURITY_GROUP_ID"

# Replace placeholders in task definitions
echo "Preparing task definitions..."

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Process API task definition
sed -e "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" \
    -e "s/<ECR_ACCOUNT>/$ECR_ACCOUNT/g" \
    -e "s/<REGION>/$REGION/g" \
    -e "s/<ENV>/$ENV/g" \
    "$(dirname "$0")/task-definition-api.json" > "$TEMP_DIR/task-definition-api.json"

# Process Worker task definition
sed -e "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" \
    -e "s/<ECR_ACCOUNT>/$ECR_ACCOUNT/g" \
    -e "s/<REGION>/$REGION/g" \
    -e "s/<ENV>/$ENV/g" \
    "$(dirname "$0")/task-definition-worker.json" > "$TEMP_DIR/task-definition-worker.json"

# Register task definitions
echo "Registering task definitions..."
API_TASK_DEF=$(aws ecs register-task-definition \
    --cli-input-json file://"$TEMP_DIR/task-definition-api.json" \
    --region "$REGION" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

WORKER_TASK_DEF=$(aws ecs register-task-definition \
    --cli-input-json file://"$TEMP_DIR/task-definition-worker.json" \
    --region "$REGION" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "✅ Task definitions registered:"
echo "   API: $API_TASK_DEF"
echo "   Worker: $WORKER_TASK_DEF"

# Create or update API service
API_SERVICE_NAME="svc-api"
echo "Creating/updating API service: $API_SERVICE_NAME"

if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$API_SERVICE_NAME" --region "$REGION" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "Updating existing API service..."
    aws ecs update-service \
        --cluster "$CLUSTER_NAME" \
        --service "$API_SERVICE_NAME" \
        --task-definition "$API_TASK_DEF" \
        --force-new-deployment \
        --region "$REGION" >/dev/null
else
    echo "Creating new API service..."
    aws ecs create-service \
        --cluster "$CLUSTER_NAME" \
        --service-name "$API_SERVICE_NAME" \
        --task-definition "$API_TASK_DEF" \
        --desired-count 2 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SECURITY_GROUP_ID],assignPublicIp=ENABLED}" \
        --region "$REGION" >/dev/null
fi

# Create or update Worker service
WORKER_SERVICE_NAME="svc-worker"
echo "Creating/updating Worker service: $WORKER_SERVICE_NAME"

if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$WORKER_SERVICE_NAME" --region "$REGION" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "Updating existing Worker service..."
    aws ecs update-service \
        --cluster "$CLUSTER_NAME" \
        --service "$WORKER_SERVICE_NAME" \
        --task-definition "$WORKER_TASK_DEF" \
        --force-new-deployment \
        --region "$REGION" >/dev/null
else
    echo "Creating new Worker service..."
    aws ecs create-service \
        --cluster "$CLUSTER_NAME" \
        --service-name "$WORKER_SERVICE_NAME" \
        --task-definition "$WORKER_TASK_DEF" \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SECURITY_GROUP_ID],assignPublicIp=ENABLED}" \
        --region "$REGION" >/dev/null
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Services are starting up. Check status with:"
echo "  aws ecs describe-services --cluster $CLUSTER_NAME --services $API_SERVICE_NAME $WORKER_SERVICE_NAME --region $REGION"
echo ""
echo "View logs:"
echo "  aws logs tail /ecs/jobsys/svc-api --follow --region $REGION"
echo "  aws logs tail /ecs/jobsys/svc-worker --follow --region $REGION"


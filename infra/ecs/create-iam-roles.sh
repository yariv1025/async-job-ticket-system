#!/bin/bash
# Create IAM roles for ECS tasks

set -e

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ENV="${ENV:-dev}"

echo "Creating IAM roles for ECS tasks..."

# Create ECS Task Execution Role (for pulling images, writing logs, reading secrets)
EXECUTION_ROLE_NAME="ecsTaskExecutionRole"
echo "Creating execution role: $EXECUTION_ROLE_NAME"

if aws iam get-role --role-name "$EXECUTION_ROLE_NAME" >/dev/null 2>&1; then
    echo "Execution role already exists"
else
    # Create trust policy for ECS tasks
    cat > /tmp/ecs-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "$EXECUTION_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/ecs-trust-policy.json \
        --region "$REGION"

    # Attach AWS managed policy for ECS task execution
    aws iam attach-role-policy \
        --role-name "$EXECUTION_ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
        --region "$REGION"

    # Attach custom policy for Parameter Store access
    aws iam put-role-policy \
        --role-name "$EXECUTION_ROLE_NAME" \
        --policy-name "ecs-task-execution-policy" \
        --policy-document file://$(dirname "$0")/../iam/ecs-task-execution-role-policy.json \
        --region "$REGION"

    echo "✅ Execution role created"
fi

# Create Task Role for svc-api
API_TASK_ROLE_NAME="svc-api-task-role"
echo "Creating task role: $API_TASK_ROLE_NAME"

if aws iam get-role --role-name "$API_TASK_ROLE_NAME" >/dev/null 2>&1; then
    echo "API task role already exists"
else
    aws iam create-role \
        --role-name "$API_TASK_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/ecs-trust-policy.json \
        --region "$REGION"

    aws iam put-role-policy \
        --role-name "$API_TASK_ROLE_NAME" \
        --policy-name "svc-api-policy" \
        --policy-document file://$(dirname "$0")/../iam/svc-api-policy.json \
        --region "$REGION"

    echo "✅ API task role created"
fi

# Create Task Role for svc-worker
WORKER_TASK_ROLE_NAME="svc-worker-task-role"
echo "Creating task role: $WORKER_TASK_ROLE_NAME"

if aws iam get-role --role-name "$WORKER_TASK_ROLE_NAME" >/dev/null 2>&1; then
    echo "Worker task role already exists"
else
    aws iam create-role \
        --role-name "$WORKER_TASK_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/ecs-trust-policy.json \
        --region "$REGION"

    aws iam put-role-policy \
        --role-name "$WORKER_TASK_ROLE_NAME" \
        --policy-name "svc-worker-policy" \
        --policy-document file://$(dirname "$0")/../iam/svc-worker-policy.json \
        --region "$REGION"

    echo "✅ Worker task role created"
fi

echo ""
echo "✅ All IAM roles created successfully!"
echo "   Execution Role: arn:aws:iam::$ACCOUNT_ID:role/$EXECUTION_ROLE_NAME"
echo "   API Task Role: arn:aws:iam::$ACCOUNT_ID:role/$API_TASK_ROLE_NAME"
echo "   Worker Task Role: arn:aws:iam::$ACCOUNT_ID:role/$WORKER_TASK_ROLE_NAME"


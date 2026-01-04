#!/bin/bash
# Main deployment script - supports ECS Fargate and EC2 + Docker Compose

set -e

REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"

# Display usage
usage() {
    cat <<EOF
Usage: $0 [OPTION]

Deploy the async job ticket system to AWS.

Options:
  --ecs          Deploy to ECS Fargate (recommended for production)
  --ec2          Deploy to EC2 with Docker Compose (simplest infrastructure)
  --help         Show this help message

Examples:
  $0 --ecs       # Deploy to ECS Fargate
  $0 --ec2       # Deploy to EC2 instance

For local Kubernetes deployment (learning/development):
  ./scripts/deploy-k8s-local.sh

EOF
    exit 1
}

# Check prerequisites
check_prerequisites() {
    if ! command -v aws &> /dev/null; then
        echo "❌ Error: AWS CLI is not installed"
        exit 1
    fi

    if ! aws sts get-caller-identity &>/dev/null; then
        echo "❌ Error: AWS credentials not configured"
        echo "   Run: aws configure"
        exit 1
    fi
}

# Deploy to ECS
deploy_ecs() {
    echo "🚀 Deploying to ECS Fargate..."
    echo ""

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    # Phase 1: Create IAM roles
    echo "Phase 1: Creating IAM roles..."
    "$SCRIPT_DIR/infra/ecs/create-iam-roles.sh"

    # Phase 2: Create cluster
    echo ""
    echo "Phase 2: Creating ECS cluster..."
    "$SCRIPT_DIR/infra/ecs/create-cluster.sh"

    # Phase 3: Deploy services
    echo ""
    echo "Phase 3: Deploying services..."
    "$SCRIPT_DIR/infra/ecs/deploy-ecs.sh"

    echo ""
    echo "✅ ECS deployment complete!"
}

# Deploy to EC2
deploy_ec2() {
    echo "🚀 Deploying to EC2 with Docker Compose..."
    echo ""

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    # Phase 1: Create EC2 instance
    echo "Phase 1: Creating EC2 instance..."
    INSTANCE_OUTPUT=$("$SCRIPT_DIR/infra/ec2/create-ec2-instance.sh")
    INSTANCE_ID=$(echo "$INSTANCE_OUTPUT" | grep "Instance ID:" | awk '{print $3}')

    if [ -z "$INSTANCE_ID" ]; then
        echo "❌ Error: Could not get instance ID from output:"
        echo "$INSTANCE_OUTPUT"
        exit 1
    fi
    
    echo "$INSTANCE_OUTPUT"

    echo ""
    echo "Waiting for instance to be ready (2 minutes)..."
    sleep 120

    # Phase 2: Deploy application
    echo ""
    echo "Phase 2: Deploying application..."
    "$SCRIPT_DIR/infra/ec2/deploy-to-ec2.sh" "$INSTANCE_ID"

    echo ""
    echo "✅ EC2 deployment complete!"
}

# Main script
if [ $# -eq 0 ]; then
    echo "Please choose a deployment option:"
    echo ""
    echo "1) ECS Fargate (recommended - serverless containers)"
    echo "2) EC2 + Docker Compose (simplest infrastructure)"
    echo ""
    read -p "Enter choice [1-2]: " choice

    case $choice in
        1) DEPLOY_OPTION="ecs" ;;
        2) DEPLOY_OPTION="ec2" ;;
        *) echo "Invalid choice"; exit 1 ;;
    esac
else
    case "$1" in
        --ecs) DEPLOY_OPTION="ecs" ;;
        --ec2) DEPLOY_OPTION="ec2" ;;
        --help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
fi

check_prerequisites

case $DEPLOY_OPTION in
    ecs)
        deploy_ecs
        ;;
    ec2)
        deploy_ec2
        ;;
    *)
        echo "Invalid deployment option"
        exit 1
        ;;
esac


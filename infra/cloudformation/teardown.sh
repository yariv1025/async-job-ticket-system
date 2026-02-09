#!/bin/bash
# CloudFormation Teardown Script
# Deletes all stacks in the correct order (dependencies first)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-dev}"
REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="jobsys"

echo -e "${YELLOW}⚠️  WARNING: This will delete ALL CloudFormation stacks for $PROJECT_NAME${NC}"
echo -e "${YELLOW}This action cannot be undone!${NC}"
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation

if [[ "$confirmation" != "yes" ]]; then
    echo -e "${GREEN}Cancelled. No stacks were deleted.${NC}"
    exit 0
fi

echo ""
echo -e "${RED}🗑️  Starting teardown for environment: $ENVIRONMENT${NC}"
echo -e "${YELLOW}Region: $REGION${NC}"
echo ""

# Function to delete a stack
delete_stack() {
    local stack_name=$1
    
    if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" &>/dev/null; then
        echo -e "${YELLOW}Deleting stack: $stack_name${NC}"
        aws cloudformation delete-stack --stack-name "$stack_name" --region "$REGION"
        
        # Wait for deletion (with timeout)
        echo "  Waiting for deletion to complete..."
        if aws cloudformation wait stack-delete-complete \
            --stack-name "$stack_name" \
            --region "$REGION" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Stack $stack_name deleted${NC}"
        else
            echo -e "${YELLOW}  ⚠ Stack $stack_name deletion in progress (may take time)${NC}"
        fi
        echo ""
    else
        echo -e "${YELLOW}  ⏭ Stack $stack_name does not exist, skipping${NC}"
        echo ""
    fi
}

# Delete stacks in reverse order (dependencies first)
echo -e "${RED}Phase 1: Deleting EC2 stack${NC}"
delete_stack "${PROJECT_NAME}-ec2"

echo -e "${RED}Phase 2: Deleting Lambda stack${NC}"
delete_stack "${PROJECT_NAME}-lambda"

echo -e "${RED}Phase 3: Deleting CloudWatch stack${NC}"
delete_stack "${PROJECT_NAME}-cloudwatch"

echo -e "${RED}Phase 4: Deleting Parameter Store stack${NC}"
delete_stack "${PROJECT_NAME}-parameter-store"

echo -e "${RED}Phase 5: Deleting ECR stack${NC}"
delete_stack "${PROJECT_NAME}-ecr"

echo -e "${RED}Phase 6: Deleting SQS stack${NC}"
delete_stack "${PROJECT_NAME}-sqs"

echo -e "${RED}Phase 7: Deleting DynamoDB stack${NC}"
delete_stack "${PROJECT_NAME}-dynamodb"

echo -e "${RED}Phase 8: Deleting IAM stack${NC}"
delete_stack "${PROJECT_NAME}-iam"

echo ""
echo -e "${GREEN}✅ Teardown initiated for all stacks!${NC}"
echo ""
echo -e "${YELLOW}Note: Some stacks may still be deleting. Check status with:${NC}"
echo "  aws cloudformation list-stacks --region $REGION"
echo ""
echo -e "${YELLOW}To check a specific stack:${NC}"
echo "  aws cloudformation describe-stacks --stack-name <stack-name> --region $REGION"


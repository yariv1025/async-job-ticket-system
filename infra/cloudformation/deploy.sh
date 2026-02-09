#!/bin/bash
# Production-Grade CloudFormation Deployment Script
# This script deploys infrastructure in the correct order with proper error handling

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-dev}"
REGION="${AWS_REGION:-us-east-1}"
TEMPLATES_DIR="$(dirname "$0")/templates"
PARAMS_DIR="$(dirname "$0")/parameters"
PROJECT_NAME="jobsys"

# Validate environment
if [[ ! -f "$PARAMS_DIR/$ENVIRONMENT.json" ]]; then
    echo -e "${RED}Error: Parameter file not found: $PARAMS_DIR/$ENVIRONMENT.json${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 Starting CloudFormation deployment for environment: $ENVIRONMENT${NC}"
echo -e "${YELLOW}Region: $REGION${NC}"
echo ""

# Function to deploy a stack
deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local capabilities=${3:-""}
    
    echo -e "${YELLOW}📦 Deploying stack: $stack_name${NC}"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" &>/dev/null; then
        echo "  Stack exists, updating..."
        aws cloudformation update-stack \
            --stack-name "$stack_name" \
            --template-body "file://$TEMPLATES_DIR/$template_file" \
            --parameters "file://$PARAMS_DIR/$ENVIRONMENT.json" \
            ${capabilities:+--capabilities $capabilities} \
            --region "$REGION" || {
            # If update failed because no changes, that's okay
            if [[ $? -eq 254 ]]; then
                echo -e "${GREEN}  ✓ No changes to apply${NC}"
                return 0
            else
                echo -e "${RED}  ✗ Update failed${NC}"
                return 1
            fi
        }
        echo "  Waiting for update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$stack_name" \
            --region "$REGION"
    else
        echo "  Creating new stack..."
        aws cloudformation create-stack \
            --stack-name "$stack_name" \
            --template-body "file://$TEMPLATES_DIR/$template_file" \
            --parameters "file://$PARAMS_DIR/$ENVIRONMENT.json" \
            ${capabilities:+--capabilities $capabilities} \
            --region "$REGION"
        echo "  Waiting for creation to complete..."
        aws cloudformation wait stack-create-complete \
            --stack-name "$stack_name" \
            --region "$REGION"
    fi
    
    echo -e "${GREEN}  ✓ Stack $stack_name deployed successfully${NC}"
    echo ""
}

# Function to get stack output
get_output() {
    local stack_name=$1
    local output_key=$2
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text
}

# Deploy stacks in order
echo -e "${GREEN}Phase 1: IAM Roles${NC}"
deploy_stack "${PROJECT_NAME}-iam" "01-iam.yaml" "CAPABILITY_NAMED_IAM"

echo -e "${GREEN}Phase 2: DynamoDB${NC}"
deploy_stack "${PROJECT_NAME}-dynamodb" "02-dynamodb.yaml"

echo -e "${GREEN}Phase 3: SQS Queues${NC}"
deploy_stack "${PROJECT_NAME}-sqs" "03-sqs.yaml"

echo -e "${GREEN}Phase 4: ECR Repositories${NC}"
deploy_stack "${PROJECT_NAME}-ecr" "04-ecr.yaml"

echo -e "${GREEN}Phase 5: Parameter Store${NC}"
# Get outputs from previous stacks for Parameter Store
TABLE_NAME=$(get_output "${PROJECT_NAME}-dynamodb" "TableName")
QUEUE_URL=$(get_output "${PROJECT_NAME}-sqs" "JobsQueueUrl")
DLQ_URL=$(get_output "${PROJECT_NAME}-sqs" "DeadLetterQueueUrl")

# Create temporary parameter file with stack outputs
TEMP_PARAMS=$(mktemp)
jq --arg table "$TABLE_NAME" \
   --arg queue "$QUEUE_URL" \
   --arg dlq "$DLQ_URL" \
   '. + [
     {"ParameterKey": "TableName", "ParameterValue": $table},
     {"ParameterKey": "JobsQueueUrl", "ParameterValue": $queue},
     {"ParameterKey": "DLQUrl", "ParameterValue": $dlq}
   ]' "$PARAMS_DIR/$ENVIRONMENT.json" > "$TEMP_PARAMS"

aws cloudformation deploy \
    --template-file "$TEMPLATES_DIR/05-parameter-store.yaml" \
    --stack-name "${PROJECT_NAME}-parameter-store" \
    --parameter-overrides file://"$TEMP_PARAMS" \
    --region "$REGION" || {
    # If stack doesn't exist, create it
    aws cloudformation create-stack \
        --stack-name "${PROJECT_NAME}-parameter-store" \
        --template-body "file://$TEMPLATES_DIR/05-parameter-store.yaml" \
        --parameters file://"$TEMP_PARAMS" \
        --region "$REGION"
    aws cloudformation wait stack-create-complete \
        --stack-name "${PROJECT_NAME}-parameter-store" \
        --region "$REGION"
}
rm "$TEMP_PARAMS"
echo -e "${GREEN}  ✓ Parameter Store stack deployed${NC}"
echo ""

echo -e "${GREEN}Phase 6: CloudWatch Log Groups${NC}"
deploy_stack "${PROJECT_NAME}-cloudwatch" "08-cloudwatch.yaml"

echo -e "${GREEN}Phase 7: Lambda Function${NC}"
# Get outputs for Lambda
LAMBDA_ROLE_ARN=$(get_output "${PROJECT_NAME}-iam" "LambdaExecutionRoleArn")
DLQ_ARN=$(get_output "${PROJECT_NAME}-sqs" "DeadLetterQueueArn")

TEMP_PARAMS=$(mktemp)
jq --arg role "$LAMBDA_ROLE_ARN" \
   --arg dlq "$DLQ_ARN" \
   --arg table "$TABLE_NAME" \
   '. + [
     {"ParameterKey": "LambdaExecutionRoleArn", "ParameterValue": $role},
     {"ParameterKey": "DLQArn", "ParameterValue": $dlq},
     {"ParameterKey": "TableName", "ParameterValue": $table}
   ]' "$PARAMS_DIR/$ENVIRONMENT.json" > "$TEMP_PARAMS"

aws cloudformation deploy \
    --template-file "$TEMPLATES_DIR/06-lambda.yaml" \
    --stack-name "${PROJECT_NAME}-lambda" \
    --parameter-overrides file://"$TEMP_PARAMS" \
    --region "$REGION" || {
    aws cloudformation create-stack \
        --stack-name "${PROJECT_NAME}-lambda" \
        --template-body "file://$TEMPLATES_DIR/06-lambda.yaml" \
        --parameters file://"$TEMP_PARAMS" \
        --region "$REGION"
    aws cloudformation wait stack-create-complete \
        --stack-name "${PROJECT_NAME}-lambda" \
        --region "$REGION"
}
rm "$TEMP_PARAMS"
echo -e "${GREEN}  ✓ Lambda stack deployed${NC}"
echo ""

echo -e "${GREEN}Phase 8: EC2 Instance (Optional)${NC}"
read -p "Deploy EC2 instance? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Get outputs for EC2
    EC2_PROFILE=$(get_output "${PROJECT_NAME}-iam" "EC2InstanceProfileName")
    API_REPO=$(get_output "${PROJECT_NAME}-ecr" "APIRepositoryURI")
    WORKER_REPO=$(get_output "${PROJECT_NAME}-ecr" "WorkerRepositoryURI")
    
    # Prompt for key pair
    read -p "Enter EC2 Key Pair name: " KEY_PAIR
    
    TEMP_PARAMS=$(mktemp)
    jq --arg profile "$EC2_PROFILE" \
       --arg api "$API_REPO" \
       --arg worker "$WORKER_REPO" \
       --arg table "$TABLE_NAME" \
       --arg queue "$QUEUE_URL" \
       --arg key "$KEY_PAIR" \
       '. + [
         {"ParameterKey": "EC2InstanceProfileName", "ParameterValue": $profile},
         {"ParameterKey": "APIRepositoryURI", "ParameterValue": $api},
         {"ParameterKey": "WorkerRepositoryURI", "ParameterValue": $worker},
         {"ParameterKey": "TableName", "ParameterValue": $table},
         {"ParameterKey": "JobsQueueUrl", "ParameterValue": $queue},
         {"ParameterKey": "KeyPairName", "ParameterValue": $key}
       ]' "$PARAMS_DIR/$ENVIRONMENT.json" > "$TEMP_PARAMS"
    
    aws cloudformation deploy \
        --template-file "$TEMPLATES_DIR/07-ec2.yaml" \
        --stack-name "${PROJECT_NAME}-ec2" \
        --parameter-overrides file://"$TEMP_PARAMS" \
        --region "$REGION" || {
        aws cloudformation create-stack \
            --stack-name "${PROJECT_NAME}-ec2" \
            --template-body "file://$TEMPLATES_DIR/07-ec2.yaml" \
            --parameters file://"$TEMP_PARAMS" \
            --region "$REGION"
        aws cloudformation wait stack-create-complete \
            --stack-name "${PROJECT_NAME}-ec2" \
            --region "$REGION"
    }
    rm "$TEMP_PARAMS"
    echo -e "${GREEN}  ✓ EC2 stack deployed${NC}"
else
    echo -e "${YELLOW}  ⏭ Skipping EC2 deployment${NC}"
fi

echo ""
echo -e "${GREEN}✅ All stacks deployed successfully!${NC}"
echo ""
echo -e "${YELLOW}📊 Stack Summary:${NC}"
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --region "$REGION" \
    --query "StackSummaries[?contains(StackName, '$PROJECT_NAME-$ENVIRONMENT') || contains(StackName, '$PROJECT_NAME')].[StackName,StackStatus]" \
    --output table


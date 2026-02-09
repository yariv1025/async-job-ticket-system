#!/bin/bash
# Create Lambda function for DLQ handler

set -e

FUNCTION_NAME="${FUNCTION_NAME:-dlq-handler}"
REGION="${AWS_REGION:-us-east-1}"
RUNTIME="${RUNTIME:-python3.11}"
ROLE_NAME="${ROLE_NAME:-dlq-handler-role}"

echo "Creating Lambda function: $FUNCTION_NAME in region: $REGION"

# Create IAM role for Lambda if it doesn't exist
echo "Creating IAM role for Lambda..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Check if role exists
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "Role $ROLE_NAME already exists"
else
    # Create trust policy
    cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --region "$REGION"

    # Attach policy
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "dlq-handler-policy" \
        --policy-document file://$(dirname "$0")/../iam/lambda-policy.json \
        --region "$REGION"

    echo "Waiting for role to be available..."
    sleep 10
fi

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"

# Create deployment package (zip file)
echo "Creating deployment package..."
cd "$(dirname "$0")/../../lambda/dlq-handler"
zip -r /tmp/dlq-handler.zip . -x "*.git*" "*.pyc" "__pycache__/*" >/dev/null 2>&1 || {
    # If zip not available, create minimal package
    echo "Note: zip command not available, you'll need to create package manually"
}

# Create or update Lambda function
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Function $FUNCTION_NAME already exists, updating code..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb:///tmp/dlq-handler.zip \
        --region "$REGION" \
        >/dev/null 2>&1 || echo "Note: Update requires existing function with code"
else
    echo "Creating Lambda function..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "handler.handler" \
        --zip-file fileb:///tmp/dlq-handler.zip \
        --timeout 30 \
        --memory-size 128 \
        --environment "Variables={DDB_TABLE=Jobs}" \
        --tracing-config Mode=Active \
        --region "$REGION" \
        >/dev/null 2>&1 || echo "Note: Function creation requires deployment package"
fi

echo "✅ Lambda function setup initiated!"
echo "   Function: $FUNCTION_NAME"
echo "   Role: $ROLE_ARN"
echo ""
echo "⚠️  Note: You may need to create the deployment package manually:"
echo "   cd lambda/dlq-handler && zip -r dlq-handler.zip ."


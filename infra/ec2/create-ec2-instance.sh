#!/bin/bash
# Create EC2 instance for Docker Compose deployment

set -e

REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.small}"
KEY_NAME="${KEY_NAME:-}"  # Optional: specify your EC2 key pair name
SECURITY_GROUP_NAME="${SECURITY_GROUP_NAME:-jobsys-ec2-sg}"

echo "Creating EC2 instance for Docker Compose deployment..."

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --region "$REGION" --query 'Vpcs[0].VpcId' --output text)

if [ -z "$VPC_ID" ] || [ "$VPC_ID" == "None" ]; then
    echo "❌ Error: Could not find default VPC"
    exit 1
fi

# Create security group if it doesn't exist
echo "Setting up security group..."
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "")

if [ -z "$SG_ID" ] || [ "$SG_ID" == "None" ]; then
    echo "Creating security group: $SECURITY_GROUP_NAME"
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for jobsys EC2 instance" \
        --vpc-id "$VPC_ID" \
        --region "$REGION" \
        --query 'GroupId' \
        --output text)

    # Allow SSH (port 22) - optional, remove if not needed
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --region "$REGION" 2>/dev/null || echo "SSH rule may already exist"

    # Allow HTTP (port 8080) for API
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 8080 \
        --cidr 0.0.0.0/0 \
        --region "$REGION" 2>/dev/null || echo "HTTP rule may already exist"
fi

echo "Using Security Group: $SG_ID"

# Create IAM role for EC2 instance
ROLE_NAME="jobsys-ec2-role"
echo "Creating IAM role: $ROLE_NAME"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "IAM role already exists"
else
    # Create trust policy
    cat > /tmp/ec2-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/ec2-trust-policy.json \
        --region "$REGION"

    # Attach policy
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "jobsys-ec2-policy" \
        --policy-document file://$(dirname "$0")/../iam/ec2-instance-policy.json \
        --region "$REGION"

    # Create instance profile
    aws iam create-instance-profile \
        --instance-profile-name "$ROLE_NAME" \
        --region "$REGION" 2>/dev/null || echo "Instance profile may already exist"

    aws iam add-role-to-instance-profile \
        --instance-profile-name "$ROLE_NAME" \
        --role-name "$ROLE_NAME" \
        --region "$REGION" 2>/dev/null || echo "Role may already be attached"

    echo "Waiting for IAM role to propagate..."
    sleep 10
fi

# Get latest Amazon Linux 2 AMI
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
    --output text \
    --region "$REGION")

echo "Using AMI: $AMI_ID"

# Read user data script
USER_DATA=$(cat "$(dirname "$0")/user-data.sh" | base64 -w 0 2>/dev/null || cat "$(dirname "$0")/user-data.sh" | base64)

# Create EC2 instance
echo "Launching EC2 instance..."

INSTANCE_LAUNCH_CMD="aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --security-group-ids $SG_ID \
    --iam-instance-profile Name=$ROLE_NAME \
    --user-data $USER_DATA \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=jobsys-ec2},{Key=Environment,Value=$ENV}]' \
    --region $REGION"

if [ -n "$KEY_NAME" ]; then
    INSTANCE_LAUNCH_CMD="$INSTANCE_LAUNCH_CMD --key-name $KEY_NAME"
fi

INSTANCE_OUTPUT=$(eval $INSTANCE_LAUNCH_CMD)
INSTANCE_ID=$(echo "$INSTANCE_OUTPUT" | grep -oP '"InstanceId":\s*"\K[^"]+' | head -1)

if [ -z "$INSTANCE_ID" ]; then
    # Try with jq if available
    if command -v jq &> /dev/null; then
        INSTANCE_ID=$(echo "$INSTANCE_OUTPUT" | jq -r '.Instances[0].InstanceId')
    else
        echo "❌ Error: Could not extract instance ID. Install jq or check AWS CLI output"
        echo "$INSTANCE_OUTPUT"
        exit 1
    fi
fi

echo "✅ EC2 instance created: $INSTANCE_ID"
echo ""
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo ""
echo "✅ Instance is running!"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"
echo ""
echo "Next steps:"
echo "1. Wait 2-3 minutes for instance initialization"
echo "2. Run: ./infra/ec2/deploy-to-ec2.sh $INSTANCE_ID"
echo ""
echo "To SSH (if key pair specified):"
echo "   ssh ec2-user@$PUBLIC_IP"


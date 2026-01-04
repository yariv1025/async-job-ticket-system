#!/bin/bash
# Deploy application to EC2 instance

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <instance-id>"
    echo "Example: $0 i-0123456789abcdef0"
    exit 1
fi

INSTANCE_ID="$1"
REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
ECR_ACCOUNT="${ECR_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"

echo "Deploying to EC2 instance: $INSTANCE_ID"

# Get instance public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" == "None" ]; then
    echo "❌ Error: Could not get public IP for instance"
    exit 1
fi

echo "Instance IP: $PUBLIC_IP"

# Get SQS queue URL from Parameter Store
SQS_QUEUE_URL=$(aws ssm get-parameter \
    --name "/jobsys/$ENV/sqs/queue-url" \
    --region "$REGION" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || echo "")

if [ -z "$SQS_QUEUE_URL" ]; then
    echo "⚠️  Warning: Could not get SQS queue URL from Parameter Store"
    echo "   You may need to set SQS_QUEUE_URL manually in docker-compose.prod.yml"
    SQS_QUEUE_URL="<SQS_QUEUE_URL>"
fi

# Prepare docker-compose file
echo "Preparing docker-compose.prod.yml..."

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

sed -e "s/<ECR_ACCOUNT>/$ECR_ACCOUNT/g" \
    -e "s/<REGION>/$REGION/g" \
    -e "s/<ENV>/$ENV/g" \
    -e "s|<SQS_QUEUE_URL>|$SQS_QUEUE_URL|g" \
    "$(dirname "$0")/docker-compose.prod.yml" > "$TEMP_DIR/docker-compose.prod.yml"

# Login to ECR on the instance
echo "Setting up ECR login on instance..."
ECR_LOGIN_CMD="aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

# Copy docker-compose file to instance
echo "Copying docker-compose file to instance..."
scp -o StrictHostKeyChecking=no "$TEMP_DIR/docker-compose.prod.yml" "ec2-user@$PUBLIC_IP:/opt/jobsys/docker-compose.prod.yml" 2>/dev/null || {
    echo "⚠️  Could not copy via SCP. Using AWS Systems Manager instead..."
    
    # Alternative: Use AWS Systems Manager Session Manager or SSM
    # For now, we'll create a script that the user can run manually
    cat > "$TEMP_DIR/setup-docker-compose.sh" <<SCRIPT_EOF
#!/bin/bash
# Login to ECR
$ECR_LOGIN_CMD

# Create docker-compose file
cat > /opt/jobsys/docker-compose.prod.yml <<'COMPOSE_EOF'
$(cat "$TEMP_DIR/docker-compose.prod.yml")
COMPOSE_EOF

# Start services
cd /opt/jobsys
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

echo "✅ Deployment complete!"
docker-compose -f docker-compose.prod.yml ps
SCRIPT_EOF

    echo ""
    echo "⚠️  Manual deployment required. Run this on the EC2 instance:"
    echo ""
    cat "$TEMP_DIR/setup-docker-compose.sh"
    echo ""
    echo "Or copy docker-compose.prod.yml manually and run:"
    echo "  cd /opt/jobsys"
    echo "  $ECR_LOGIN_CMD"
    echo "  docker-compose -f docker-compose.prod.yml pull"
    echo "  docker-compose -f docker-compose.prod.yml up -d"
    exit 0
}

# Execute deployment commands on instance
echo "Deploying application..."

ssh -o StrictHostKeyChecking=no "ec2-user@$PUBLIC_IP" <<EOF
set -e

# Login to ECR
$ECR_LOGIN_CMD

# Pull latest images and start services
cd /opt/jobsys
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml down || true
docker-compose -f docker-compose.prod.yml up -d

# Show status
echo ""
echo "✅ Deployment complete!"
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "API should be available at: http://$PUBLIC_IP:8080"
echo "Check logs with: docker-compose -f docker-compose.prod.yml logs -f"
EOF

echo ""
echo "✅ Deployment complete!"
echo ""
echo "API endpoint: http://$PUBLIC_IP:8080"
echo ""
echo "To check logs:"
echo "  ssh ec2-user@$PUBLIC_IP 'cd /opt/jobsys && docker-compose -f docker-compose.prod.yml logs -f'"


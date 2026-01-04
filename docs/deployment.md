# Deployment Guide

## Prerequisites

- AWS CLI configured with appropriate credentials (`aws configure`)
- Docker installed (for building images)
- Python 3.11+ installed (for local development)

## Local Development Setup

### 1. Start LocalStack

```bash
docker-compose up -d localstack
```

### 2. Initialize Local Infrastructure

```bash
./scripts/local-dev.sh
```

This creates:
- DynamoDB table `Jobs`
- SQS queue `jobs-queue`
- DLQ `jobs-dlq`
- Redrive policy

### 3. Run Services Locally

**svc-api:**
```bash
cd services/svc-api
python3 -m venv venv
source venv/bin/activate
pip install poetry
poetry install
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export DDB_TABLE=Jobs
export SQS_QUEUE_URL=http://localhost:4566/000000000000/jobs-queue
python3 -m uvicorn svc_api.main:app --port 8080
```

**svc-worker:**
```bash
cd services/svc-worker
python3 -m venv venv
source venv/bin/activate
pip install poetry
poetry install
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export DDB_TABLE=Jobs
export SQS_QUEUE_URL=http://localhost:4566/000000000000/jobs-queue
python3 -m svc_worker.main
```

## Kubernetes Deployment (LOCAL ONLY)

**⚠️ Note:** Kubernetes deployment is for **local learning/development only**. For AWS cloud deployment, use ECS Fargate or EC2 options below.

### Prerequisites for Local K8s

- `kubectl` installed
- Local Kubernetes cluster running (minikube, kind, k3d, etc.)

### Deploy to Local Kubernetes

```bash
# Make sure your local cluster is running
# For minikube: minikube start
# For kind: kind create cluster
# For k3d: k3d cluster create

./scripts/deploy-k8s-local.sh
```

This will:
- Create namespace `jobsys`
- Deploy ConfigMaps, Deployments, and Services
- Use local Docker images or ECR images if configured

### Access Local K8s Services

```bash
# Port forward to access API
kubectl port-forward svc/svc-api 8080:8080 -n jobsys

# Check status
kubectl get pods -n jobsys
kubectl logs -f deployment/svc-api -n jobsys
```

## AWS Cloud Deployment

The system supports two deployment options for AWS:

1. **ECS Fargate** (Recommended) - Serverless containers, no EC2 management
2. **EC2 + Docker Compose** (Simplest) - Single EC2 instance with Docker Compose

### Phase 1: Create AWS Infrastructure

This phase is the same for both deployment options:

```bash
# Create DynamoDB table
./infra/aws-cli/create-table.sh

# Create SQS queues
./infra/aws-cli/create-queues.sh

# Create ECR repositories
./infra/aws-cli/create-ecr-repos.sh

# Setup Parameter Store
./infra/aws-cli/setup-parameter-store.sh
```

### Phase 2: Build and Push Docker Images

This phase is the same for both deployment options:

```bash
# Get ECR login
ECR_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# Build and push svc-api
cd services/svc-api
docker build -t svc-api:latest .
docker tag svc-api:latest $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-api:latest
docker push $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-api:latest

# Build and push svc-worker
cd ../svc-worker
docker build -t svc-worker:latest .
docker tag svc-worker:latest $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-worker:latest
docker push $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-worker:latest
```

### Phase 3: Choose Deployment Option

#### Option A: Deploy to ECS Fargate (Recommended)

**Why ECS Fargate?**
- Serverless containers (no EC2 to manage)
- Auto-scaling built-in
- Pay only for running tasks
- Production-ready

**Deploy:**

```bash
# Interactive mode (choose option 1)
./scripts/deploy.sh

# Or directly
./scripts/deploy.sh --ecs
```

This will:
1. Create IAM roles for ECS tasks
2. Create ECS Fargate cluster
3. Register task definitions
4. Create and start ECS services

**What gets created:**
- ECS cluster: `jobsys-cluster`
- ECS service: `svc-api` (2 tasks)
- ECS service: `svc-worker` (1 task)
- CloudWatch log groups: `/ecs/jobsys/svc-api`, `/ecs/jobsys/svc-worker`

**Access your services:**

```bash
# Get task public IPs
aws ecs list-tasks --cluster jobsys-cluster --service-name svc-api --region us-east-1
TASK_ARN=$(aws ecs list-tasks --cluster jobsys-cluster --service-name svc-api --region us-east-1 --query 'taskArns[0]' --output text)
ENI_ID=$(aws ecs describe-tasks --cluster jobsys-cluster --tasks $TASK_ARN --region us-east-1 --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region us-east-1 --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
echo "API available at: http://$PUBLIC_IP:8080"
```

**View logs:**

```bash
aws logs tail /ecs/jobsys/svc-api --follow --region us-east-1
aws logs tail /ecs/jobsys/svc-worker --follow --region us-east-1
```

**Check service status:**

```bash
aws ecs describe-services --cluster jobsys-cluster --services svc-api svc-worker --region us-east-1
```

#### Option B: Deploy to EC2 + Docker Compose (Simplest)

**Why EC2 + Docker Compose?**
- Simplest infrastructure (single EC2 instance)
- Full control over the environment
- Good for small applications
- Lower cost for always-on workloads

**Deploy:**

```bash
# Interactive mode (choose option 2)
./scripts/deploy.sh

# Or directly
./scripts/deploy.sh --ec2
```

This will:
1. Create EC2 instance with IAM role
2. Install Docker and Docker Compose
3. Deploy application using docker-compose

**What gets created:**
- EC2 instance (t3.small by default)
- Security group with ports 22 (SSH) and 8080 (API)
- IAM role with necessary permissions

**Access your services:**

The script will output the public IP. API is available at:
```
http://<EC2_PUBLIC_IP>:8080
```

**View logs:**

```bash
# SSH to instance (if key pair was specified)
ssh ec2-user@<EC2_PUBLIC_IP>

# On the instance
cd /opt/jobsys
docker-compose -f docker-compose.prod.yml logs -f
```

**Manual deployment (if automated script fails):**

```bash
# 1. Create instance
INSTANCE_ID=$(./infra/ec2/create-ec2-instance.sh | grep "Instance ID:" | awk '{print $3}')

# 2. Wait for initialization (2-3 minutes)

# 3. Deploy application
./infra/ec2/deploy-to-ec2.sh $INSTANCE_ID
```

### Phase 4: Deploy Lambda (DLQ Handler)

This phase is the same for both deployment options:

```bash
cd lambda/dlq-handler
zip -r dlq-handler.zip .

# Create Lambda function
./infra/aws-cli/create-lambda.sh

# Get DLQ URL and create event source mapping
ENV=dev
REGION=us-east-1
DLQ_URL=$(aws ssm get-parameter --name "/jobsys/$ENV/sqs/dlq-url" --region $REGION --query 'Parameter.Value' --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --region $REGION --query 'Attributes.QueueArn' --output text)

aws lambda create-event-source-mapping \
  --function-name dlq-handler \
  --event-source-arn "$DLQ_ARN" \
  --batch-size 1 \
  --region $REGION
```

## Verification

### Test API (ECS Fargate)

```bash
# Get API endpoint (see "Access your services" above)
curl -X POST http://<API_IP>:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "type": "process_document",
    "priority": "normal",
    "params": {
      "source": "s3://bucket/key"
    }
  }'
```

### Test API (EC2)

```bash
curl -X POST http://<EC2_IP>:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "type": "process_document",
    "priority": "normal",
    "params": {
      "source": "s3://bucket/key"
    }
  }'
```

## Teardown

### ECS Fargate Teardown

```bash
# Delete ECS services
aws ecs update-service --cluster jobsys-cluster --service svc-api --desired-count 0 --region us-east-1
aws ecs update-service --cluster jobsys-cluster --service svc-worker --desired-count 0 --region us-east-1

# Wait for tasks to stop, then delete services
aws ecs delete-service --cluster jobsys-cluster --service svc-api --region us-east-1
aws ecs delete-service --cluster jobsys-cluster --service svc-worker --region us-east-1

# Delete cluster (optional)
aws ecs delete-cluster --cluster jobsys-cluster --region us-east-1
```

### EC2 Teardown

```bash
# Get instance ID
INSTANCE_ID=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=jobsys-ec2" --query 'Reservations[0].Instances[0].InstanceId' --output text --region us-east-1)

# Terminate instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
```

### Common Teardown (AWS Infrastructure)

```bash
./scripts/teardown.sh
```

## Troubleshooting

### ECS Tasks Not Starting

- Check IAM roles: `aws iam get-role --role-name ecsTaskExecutionRole`
- Check task definition: `aws ecs describe-task-definition --task-definition svc-api --region us-east-1`
- Check service events: `aws ecs describe-services --cluster jobsys-cluster --services svc-api --region us-east-1`
- Verify ECR images are accessible
- Check CloudWatch logs: `aws logs tail /ecs/jobsys/svc-api --follow --region us-east-1`

### EC2 Instance Issues

- Check instance status: `aws ec2 describe-instance-status --instance-ids <INSTANCE_ID>`
- Check security group rules allow port 8080
- SSH to instance and check Docker: `docker ps`, `docker-compose ps`
- Check logs: `docker-compose -f docker-compose.prod.yml logs`

### Jobs Not Processing

- Check worker logs (ECS or EC2)
- Verify SQS queue URL is correct in Parameter Store
- Check DynamoDB table exists and is accessible
- Verify IAM permissions for SQS and DynamoDB

### Lambda Not Triggered

- Check event source mapping: `aws lambda list-event-source-mappings`
- Verify DLQ has messages: `aws sqs get-queue-attributes --queue-url <DLQ_URL>`
- Check Lambda logs: `aws logs tail /aws/lambda/dlq-handler --follow`

### Common Issues

**"Cannot pull image from ECR"**
- Verify ECR login: `aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com`
- Check IAM role has ECR permissions

**"Parameter Store access denied"**
- Verify IAM role has `ssm:GetParameter` permission
- Check parameter exists: `aws ssm get-parameter --name /jobsys/dev/sqs/queue-url`

**"SQS queue not found"**
- Run infrastructure setup: `./infra/aws-cli/create-queues.sh`
- Verify queue URL in Parameter Store

# Deployment Guide

## Prerequisites

- AWS CLI configured with appropriate credentials
- kubectl configured for your Kubernetes cluster
- Docker installed
- Python 3.11+ installed

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
python -m venv venv
source venv/bin/activate
pip install poetry
poetry install
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export DDB_TABLE=Jobs
export SQS_QUEUE_URL=http://localhost:4566/000000000000/jobs-queue
python -m uvicorn svc_api.main:app --port 8080
```

**svc-worker:**
```bash
cd services/svc-worker
python -m venv venv
source venv/bin/activate
pip install poetry
poetry install
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export DDB_TABLE=Jobs
export SQS_QUEUE_URL=http://localhost:4566/000000000000/jobs-queue
python -m svc_worker.main
```

## AWS Deployment

### Phase 1: Create AWS Infrastructure

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

### Phase 3: Deploy to Kubernetes

```bash
# Update ECR account in deployment files
export ECR_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# Deploy
./scripts/deploy.sh
```

### Phase 4: Deploy Lambda

```bash
cd lambda/dlq-handler
zip -r dlq-handler.zip .
aws lambda create-function \
  --function-name dlq-handler \
  --runtime python3.11 \
  --role <LAMBDA_ROLE_ARN> \
  --handler handler.handler \
  --zip-file fileb://dlq-handler.zip \
  --timeout 30 \
  --memory-size 128

# Create event source mapping
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url <DLQ_URL> --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
aws lambda create-event-source-mapping \
  --function-name dlq-handler \
  --event-source-arn $DLQ_ARN \
  --batch-size 1
```

## Verification

### Check Pods

```bash
kubectl get pods -n jobsys
```

### Check Logs

```bash
kubectl logs -f deployment/svc-api -n jobsys
kubectl logs -f deployment/svc-worker -n jobsys
```

### Test API

```bash
# Port forward
kubectl port-forward svc/svc-api 8080:8080 -n jobsys

# Create a job
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "type": "process_document",
    "priority": "normal",
    "params": {
      "source": "s3://bucket/key"
    }
  }'

# Check job status
curl http://localhost:8080/api/v1/jobs/{job_id}
```

## Teardown

```bash
./scripts/teardown.sh
```

## Troubleshooting

### Pods Not Starting

- Check ConfigMaps: `kubectl get configmap -n jobsys`
- Check logs: `kubectl describe pod <pod-name> -n jobsys`
- Verify ECR images are accessible

### Jobs Not Processing

- Check worker logs: `kubectl logs deployment/svc-worker -n jobsys`
- Verify SQS queue URL is correct
- Check DynamoDB table exists and is accessible

### Lambda Not Triggered

- Check event source mapping: `aws lambda list-event-source-mappings`
- Verify DLQ has messages: `aws sqs get-queue-attributes --queue-url <DLQ_URL>`
- Check Lambda logs: `aws logs tail /aws/lambda/dlq-handler --follow`


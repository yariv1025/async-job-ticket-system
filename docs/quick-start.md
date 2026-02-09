# Quick Start Guide

This guide will help you get the system running step by step, starting with local testing.

## Prerequisites Check

Before starting, make sure you have:

- [ ] Docker installed and running
- [ ] Python 3.11+ installed
- [ ] AWS CLI installed (for local testing with LocalStack)
- [ ] Basic terminal/command line knowledge

To check:
```bash
docker --version
python3 --version
aws --version
```

## Step 1: Local Testing (Recommended First Step)

This lets you test everything without AWS costs or credentials.

### 1.1 Start LocalStack

```bash
# Start LocalStack (emulates AWS services locally)
docker-compose up -d localstack

# Wait a few seconds for it to start, then verify:
curl http://localhost:4566/_localstack/health
```

### 1.2 Initialize Local Infrastructure

**IMPORTANT:** You MUST run this step before starting the API or worker!

```bash
# This creates DynamoDB table, SQS queues, and DLQ
./scripts/local-dev.sh
```

**Verify it worked:**
```bash
# Check table exists
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# Check queues exist
aws --endpoint-url=http://localhost:4566 sqs list-queues
```

You should see "Jobs" table and both queues listed.

### 1.3 Set Up Python Environment for API

```bash
cd services/svc-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (you may need to install poetry first)
pip install poetry
poetry install
```

### 1.4 Run the API Service

```bash
# Set environment variables for LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export DDB_TABLE=Jobs

# Get the actual queue URL from LocalStack (it may have a different format)
export SQS_QUEUE_URL=$(aws --endpoint-url=http://localhost:4566 sqs get-queue-url --queue-name jobs-queue --query 'QueueUrl' --output text)
echo "Using SQS Queue: $SQS_QUEUE_URL"

# Run the API
python3 -m uvicorn svc_api.main:app --port 8080 --reload
```

The API should now be running at `http://localhost:8080`

### 1.5 Test the API

Open a new terminal and test:

```bash
# Create a job
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-123" \
  -d '{
    "type": "process_document",
    "priority": "normal",
    "params": {
      "source": "s3://bucket/test.pdf"
    }
  }'

# You should get a response with a jobId. Copy it and check status:
curl http://localhost:8080/api/v1/jobs/{jobId}
```

### 1.6 Run the Worker Service

In another terminal:

```bash
cd services/svc-worker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install poetry
poetry install

# Set environment variables
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export DDB_TABLE=Jobs

# Get the actual queue URL from LocalStack
export SQS_QUEUE_URL=$(aws --endpoint-url=http://localhost:4566 sqs get-queue-url --queue-name jobs-queue --query 'QueueUrl' --output text)
echo "Using SQS Queue: $SQS_QUEUE_URL"

# Run the worker
python -m svc_worker.main
```

The worker will start polling SQS for messages. If you created a job in step 1.5, it should process it!

### 1.7 Verify Everything Works

1. Check API logs - you should see job creation logs
2. Check worker logs - you should see job processing logs
3. Query the job status again - it should show "SUCCEEDED"

## Step 2: Run Tests

Once local testing works, verify the code with tests:

```bash
# Test the API service
cd services/svc-api
pytest

# Test the worker service
cd ../svc-worker
pytest
```

## Step 3: AWS Deployment (When Ready)

Only proceed to AWS after local testing works!

### 3.1 Prerequisites

- [ ] AWS account created
- [ ] AWS CLI configured (`aws configure`)
- [ ] kubectl installed (if deploying to Kubernetes)
- [ ] Docker installed (for building images)

### 3.2 Create AWS Resources

```bash
# Set your AWS region (change if needed)
export AWS_REGION=us-east-1

# Create all infrastructure
./infra/aws-cli/create-table.sh
./infra/aws-cli/create-queues.sh
./infra/aws-cli/create-ecr-repos.sh
./infra/aws-cli/setup-parameter-store.sh
```

### 3.3 Build and Push Docker Images

```bash
# Get your AWS account ID
ECR_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

# Login to ECR
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin \
  $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# Build and push API
cd services/svc-api
docker build -t svc-api:latest .
docker tag svc-api:latest $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-api:latest
docker push $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-api:latest

# Build and push Worker
cd ../svc-worker
docker build -t svc-worker:latest .
docker tag svc-worker:latest $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-worker:latest
docker push $ECR_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/svc-worker:latest
```

### 3.4 Deploy to Kubernetes

```bash
# Update ECR account in deployment files
export ECR_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# Deploy
./scripts/deploy.sh
```

## Troubleshooting

### LocalStack not starting
- Check Docker is running: `docker ps`
- Check port 4566 is not in use
- Try: `docker-compose down` then `docker-compose up -d localstack`

### Python import errors
- Make sure virtual environment is activated
- Run `poetry install` again
- Check Python version: `python3 --version` (needs 3.11+)

### API not connecting to LocalStack
- Verify LocalStack is running: `curl http://localhost:4566/_localstack/health`
- Check environment variables are set correctly
- Make sure `AWS_ENDPOINT_URL` points to `http://localhost:4566`

### Worker not processing jobs
- Check worker logs for errors
- Verify SQS_QUEUE_URL is correct
- Make sure a job was created in the API
- Check DynamoDB table exists: `aws --endpoint-url=http://localhost:4566 dynamodb list-tables`

## Running unit tests

Run the test suites for the API and worker services:

```bash
# Test the API service
cd services/svc-api
pytest

# Test the worker service (from repo root)
cd services/svc-worker
pytest
```

## Next Steps After Getting It Running

1. **Explore the code**: Read through `services/svc-api/src/svc_api/` to understand the structure
2. **Modify a job type**: Add a new job type in the worker's `job_processor.py`
3. **Add logging**: Experiment with adding more log statements
4. **Test failure scenarios**: Try creating jobs that will fail to see retry logic
5. **Read the docs**: Check out `docs/architecture.md` for deeper understanding

## Getting Help

- Check the [Technology Guide](tech-guide.md) for explanations of each tool
- Review [Architecture Documentation](architecture.md) for system design
- See [Deployment Guide](deployment.md) for detailed deployment steps
- Check logs for error messages

## Cleanup

When done testing locally:

```bash
# Stop LocalStack
docker-compose down

# Remove local data
rm -rf localstack-data/
```

When done with AWS:

```bash
# Run teardown script (careful - this deletes everything!)
./scripts/teardown.sh
```

⚠️ **Warning:** The teardown script deletes all AWS resources created for this project. Use with caution.


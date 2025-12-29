# Architecture Documentation

## System Overview

The Async Job Ticket System is a production-ready job processing system built on AWS services and Kubernetes. It demonstrates real-world patterns for async job processing, idempotency, retries, observability, and error handling.

## Architecture Diagram

See the main plan document for the detailed Mermaid architecture diagram.

## Components

### svc-api (FastAPI Service)

**Responsibilities:**
- Accepts job submission requests via REST API
- Validates input and enforces idempotency
- Writes job records to DynamoDB (PENDING status)
- Publishes messages to SQS for processing
- Handles partial failures with compensation pattern

**Key Features:**
- Idempotency key validation (client-provided UUID)
- Compensation: If SQS publish fails, marks job as FAILED
- Retry endpoint: `/jobs/{id}/retry` for stuck jobs
- Health endpoints: `/healthz` (liveness), `/readyz` (readiness)

### svc-worker (Worker Service)

**Responsibilities:**
- Long-polls SQS for job messages
- Processes jobs with idempotency checks
- Updates job status in DynamoDB
- Implements exponential backoff for transient failures
- Deletes messages only on successful processing

**Key Features:**
- Long polling (20s wait time) to reduce empty receives
- Exponential backoff: 1s → 2s → 4s (max 30s)
- Idempotency: Skips already-processed jobs (SUCCEEDED/FAILED_FINAL)
- Dual retry strategy: Worker retries + SQS redrive

### Lambda DLQ Handler

**Responsibilities:**
- Triggered by SQS event source mapping from DLQ
- Marks jobs as FAILED_FINAL in DynamoDB
- Stores error information for debugging

**Key Features:**
- Batch size: 1 (process one message at a time)
- X-Ray tracing enabled
- Automatic retry on Lambda failures

## Data Flow

### Happy Path

1. Client sends `POST /jobs` with `Idempotency-Key` header
2. svc-api validates idempotency (checks DynamoDB GSI)
3. svc-api creates job record in DynamoDB (PENDING)
4. svc-api publishes message to SQS
5. svc-worker long-polls SQS, receives message
6. svc-worker checks idempotency, updates job (PROCESSING)
7. svc-worker processes job, updates job (SUCCEEDED)
8. svc-worker deletes message from SQS
9. Client polls `GET /jobs/{id}` to check status

### Failure Flow

1. Worker fails to process job (transient error)
2. Worker implements exponential backoff (up to 3 attempts)
3. If worker retries exhausted, message returns to SQS
4. SQS redrives message (up to 3 times via maxReceiveCount)
5. After 3 SQS retries, message moves to DLQ
6. Lambda triggered by DLQ event source mapping
7. Lambda marks job as FAILED_FINAL in DynamoDB

## Data Model

### DynamoDB Table: Jobs

**Partition Key:** `jobId` (String)

**Global Secondary Index:** `idempotencyKey-index`
- Key: `idempotencyKey` (String)

**Attributes:**
- `status`: PENDING | PROCESSING | SUCCEEDED | FAILED | FAILED_FINAL
- `jobType`: process_document | generate_report | transform_data
- `priority`: low | normal | high
- `params`: Job parameters (JSON)
- `metadata`: Optional metadata (JSON)
- `traceId`: Correlation ID for tracing
- `payloadHash`: SHA256 hash of payload
- `createdAt`: ISO timestamp
- `updatedAt`: ISO timestamp
- `attempts`: Number of processing attempts
- `result`: Job result (JSON, on success)
- `error`: Error message (on failure)
- `expiresAt`: TTL timestamp (24 hours)

## Observability

### CloudWatch Logs

All services emit structured JSON logs with:
- `traceId`: Correlation ID
- `jobId`: Job identifier
- `component`: Service name
- `level`: Log level
- `msg`: Log message
- Additional context fields

### CloudWatch Metrics

**Custom Metrics (Namespace: JobsSystem):**
- `JobsCreated`: Count of jobs created
- `JobsCreatedFailed`: Count of failed job creations
- `SQSPublishLatency`: Milliseconds to publish to SQS
- `JobsProcessed`: Count of successfully processed jobs
- `JobsProcessedFailed`: Count of failed job processing
- `JobProcessingDuration`: Milliseconds to process job
- `SQSQueueDepth`: Approximate number of messages in queue

### AWS X-Ray

Distributed tracing across:
- API → SQS → Worker → Lambda

Traces include:
- Service names
- Operation names
- Timing information
- Error details

## Security

### IAM Policies

**Least Privilege Principle:**
- Each service has minimal required permissions
- Separate policies for API, Worker, and Lambda
- No cross-service permissions

**Key Permissions:**
- DynamoDB: Specific table and index access
- SQS: Specific queue access (send/receive/delete)
- Parameter Store: Read-only access to configuration
- CloudWatch: Put metrics and logs
- X-Ray: Put trace segments

### Secrets Management

- AWS Systems Manager Parameter Store (free tier)
- Hierarchy: `/jobsys/{env}/{service}/{key}`
- No secrets in code or environment variables

## Failure Modes

### Partial Failures

**Scenario:** DynamoDB write succeeds, SQS publish fails
**Solution:** Compensation pattern - mark job as FAILED in DynamoDB

**Scenario:** Job stuck in PENDING
**Solution:** Retry endpoint `/jobs/{id}/retry` to re-publish to SQS

### Message Loss

**Protection:**
- SQS message retention: 14 days
- DLQ retention: 14 days
- DynamoDB job records persist

### Duplicate Processing

**Protection:**
- Idempotency key validation
- Status checks before processing
- SQS at-least-once delivery handled gracefully

## Cost Considerations

**Free Tier Eligible:**
- CloudWatch Logs: 5GB ingestion/month
- CloudWatch Metrics: 10 custom metrics
- X-Ray: 100k traces/month
- Parameter Store: 10k parameters (standard tier)
- DynamoDB: 25GB storage, 25 RCU, 25 WCU
- SQS: 1M requests/month
- Lambda: 1M requests, 400k GB-seconds

**Cost Hotspots:**
- EC2 instance (always running for k3s)
- DynamoDB on-demand pricing (after free tier)
- CloudWatch Logs storage (after free tier)
- ECR storage for images


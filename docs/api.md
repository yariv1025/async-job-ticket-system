# API Documentation

## Base URL

```
http://localhost:8080/api/v1
```

## Endpoints

### POST /jobs

Create a new job.

**Headers:**
- `Idempotency-Key` (optional): UUID for idempotency
- `X-Trace-Id` (optional): Trace ID for correlation

**Request Body:**
```json
{
  "type": "process_document",
  "priority": "normal",
  "params": {
    "source": "s3://bucket/key",
    "destination": "s3://bucket/output"
  },
  "metadata": {
    "userId": "user-123"
  }
}
```

**Response (201 Created):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "jobType": "process_document",
  "priority": "normal",
  "createdAt": "2024-01-01T12:00:00",
  "updatedAt": "2024-01-01T12:00:00",
  "traceId": "trace-123"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid input
- `500 Internal Server Error`: Service error

### GET /jobs/{job_id}

Get job status by ID.

**Response (200 OK):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCEEDED",
  "jobType": "process_document",
  "priority": "normal",
  "createdAt": "2024-01-01T12:00:00",
  "updatedAt": "2024-01-01T12:00:15",
  "traceId": "trace-123"
}
```

**Error Responses:**
- `404 Not Found`: Job not found

### POST /jobs/{job_id}/retry

Retry publishing a job to SQS if it's stuck in PENDING.

**Headers:**
- `X-Trace-Id` (optional): Trace ID for correlation

**Response (200 OK):**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "jobType": "process_document",
  "priority": "normal",
  "createdAt": "2024-01-01T12:00:00",
  "updatedAt": "2024-01-01T12:00:00",
  "traceId": "trace-123"
}
```

**Error Responses:**
- `400 Bad Request`: Job not in PENDING status
- `404 Not Found`: Job not found
- `500 Internal Server Error`: Service error

### GET /healthz

Liveness probe endpoint.

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

### GET /readyz

Readiness probe endpoint (checks DynamoDB connection).

**Response (200 OK):**
```json
{
  "status": "ready"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "not ready",
  "reason": "service not initialized"
}
```

## Job Types

- `process_document`: Process a document (e.g., PDF, image)
- `generate_report`: Generate a report
- `transform_data`: Transform data

## Job Priorities

- `low`: Low priority
- `normal`: Normal priority (default)
- `high`: High priority

## Job Statuses

- `PENDING`: Job created, waiting for processing
- `PROCESSING`: Job is being processed
- `SUCCEEDED`: Job completed successfully
- `FAILED`: Job failed (may be retried)
- `FAILED_FINAL`: Job failed after all retries

## Idempotency

When creating a job with an `Idempotency-Key` header:
- If a job with the same key exists, the existing job is returned
- No duplicate job is created
- No duplicate SQS message is published
- Idempotency keys expire after 24 hours


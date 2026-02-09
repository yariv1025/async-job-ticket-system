Project idea: “Async Job Ticket System” (small, simple, meaningful)

A minimal system that still teaches “real AWS” patterns:

API Service (svc-api): receives POST /jobs, validates input, writes a job record, and publishes an event to SQS.

Worker Service (svc-worker): long-polls SQS, processes jobs, updates status in DynamoDB, and on repeated failures routes to DLQ.

Lambda (serverless sidecar): triggered from the DLQ (or directly from SQS as a second consumer) to create an “incident” record / notification (simulates serverless automation).

Why it’s meaningful:

It’s the backbone pattern behind order processing, report generation, scanning pipelines, image/video processing, etc.

You'll practice idempotency, retries, DLQ, observability, IAM least privilege, container orchestration (local K8s), and AWS deployment (ECS/EC2).


##########
Architecture

**Deployment Options:**

1. **Local (Learning):** Kubernetes (minikube/kind/k3d) - for learning container orchestration
2. **AWS Option A (Free-tier):** EC2 + Docker Compose - simplest, free-tier eligible
3. **AWS Option B (Production):** ECS Fargate - serverless containers, auto-scaling

```mermaid
flowchart LR
  U[Client] -->|HTTP| API[svc-api (FastAPI)\nContainer Deployment]
  API -->|PutItem| DDB[(DynamoDB Jobs Table)]
  API -->|SendMessage| Q[SQS Queue]
  W[svc-worker\nContainer Deployment] -->|ReceiveMessage (long polling)| Q
  W -->|UpdateItem| DDB
  Q -->|MaxReceiveCount exceeded| DLQ[SQS DLQ]
  DLQ -->|Event source mapping| L[Lambda: dlq-handler]
  L -->|PutItem| DDB
  API --> CW[(CloudWatch Logs)]
  W --> CW
  L --> CW
```

**Note:** K8s shown for local learning. AWS uses EC2 + Docker Compose (manual guide) or ECS Fargate.


##########
Component responsibilities (clean boundaries)

svc-api
* Input validation, request IDs, idempotency key
* Write job = PENDING to DynamoDB
* Publish message {jobId, payloadHash, traceId} to SQS
* Never does heavy work

svc-worker
* Long-polls SQS (up to 20s wait) to reduce empty receives 
* Processes job; on success: update DynamoDB SUCCEEDED and delete message
* On failure: don’t delete message; let retries happen; after threshold it goes to DLQ 
* Must be idempotent (SQS can deliver duplicates)

Lambda dlq-handler
* Triggered by SQS event source mapping 
* Creates “incident” / marks job FAILED_FINAL
* Optional: send notification (email/Slack later)


##########
Data model (DynamoDB)
Single table: Jobs
* PK: JOB#{jobId}
* Attributes: status, createdAt, updatedAt, attempts, result, error, traceId, payloadHash

Start simple; don’t over-model. For basics: create table via CLI/Console
Partition key best-practices matter later when scaling


##########
Execution plan (ASAP) + checklist
Phase 0 — Guardrails
* Enable MFA (root), avoid root keys
* Create an IAM admin user/role for labs
* Set AWS Budget + billing alerts (do first)

Phase 1 — Bootstrap infra
AWS
* Create DynamoDB table Jobs
* Create SQS queue jobs + DLQ jobs-dlq and attach redrive policy 
* Create ECR repos: svc-api, svc-worker

Compute/AWS (Choose one deployment option)

**Option A - EC2 + Docker Compose (Simplest, Free-tier eligible):**
* Launch 1 EC2 instance (micro), security group allowing:
    - SSH from your IP
    - API port (e.g., 8080) from your IP
* Install Docker and Docker Compose on the instance
* Deploy using docker-compose.yml (see manual-deployment-guide.md)

**Option B - ECS Fargate (Production, Auto-scaling):**
* Create ECS cluster
* Create task definitions for svc-api and svc-worker
* Deploy services to Fargate (see deployment.md)

**Local Learning - Kubernetes (Optional):**
* Set up local K8s cluster (minikube/kind/k3d)
* Deploy using k8s manifests (for learning only, not AWS production)

Phase 2 — Build services
* svc-api FastAPI:
    - POST /jobs -> create jobId, write DynamoDB PENDING, send SQS message
    - GET /jobs/{id} -> fetch from DynamoDB
* svc-worker
    - Long poll SQS (WaitTimeSeconds up to 20s)
    - Process: simulate work (sleep + deterministic transform), update DynamoDB
    - Implement idempotency check: if status already SUCCEEDED/FAILED_FINAL, no-op
* Add structured logs: {traceId, jobId, component, level, msg}

Phase 3 — Containerize + push to ECR
* Build Docker images
* Authenticate to ECR using aws ecr get-login-password | docker login ...
*Push both images

Phase 4 — Deploy Services

**4a. Local K8s Deployment (Optional - for learning):**
* Create Namespace: jobsys
* Deploy:
    - svc-api Deployment + Service
    - svc-worker Deployment
* Configure env via ConfigMap/Secret:
    - AWS_REGION, SQS_QUEUE_URL, DDB_TABLE, LOG_LEVEL
* Health endpoints:
    - liveness /healthz
    - readiness /readyz
* Resource limits (small but present)

**4b. AWS Deployment (Choose one):**

*Option A - EC2 + Docker Compose:*
* SSH to EC2 instance
* Pull images from ECR
* Create docker-compose.yml with environment variables
* Start services: `docker-compose up -d`
* Verify: `docker-compose ps` and `docker-compose logs`

*Option B - ECS Fargate:*
* Create IAM roles for ECS tasks
* Create ECS cluster
* Create task definitions (svc-api, svc-worker)
* Deploy services to Fargate
* Configure environment variables via task definitions
* Health checks via ECS service health checks

Phase 5 — Lambda DLQ handler (60–90 min)
* Create Lambda dlq-handler
* Create SQS event source mapping from jobs-dlq to Lambda
* Lambda updates DynamoDB FAILED_FINAL + stores error payload
* Verify CloudWatch logs for Lambda invocations

Phase 6 — Verification + failure drills (45–90 min)
* Happy path:
    - POST job -> see PENDING -> SUCCEEDED
* Failure path:
    - Make worker fail intentionally for certain payloads
    - Confirm retries then DLQ move
    - Confirm Lambda processes DLQ message and marks FAILED_FINAL

* Idempotency:
    - Re-send same message / duplicate deliveries -> job state remains consistent

Phase 7 — Teardown script (15–30 min)
* Add scripts/teardown.sh to delete:
    - Local K8s resources (if used)
    - ECS services/cluster (if Option B)
    - EC2 instance (if Option A)
    - Lambda + event source mapping
    - SQS queues
    - DynamoDB table (optional)
    - ECR repos (optional)

* Document "cost hotspots" (LBs, NAT gateways, idle clusters, ECS tasks)


##########
Materials (authoritative references)

* SQS DLQ and redrive policies
* SQS long polling (max 20 seconds)
* Lambda + SQS event source mapping behavior (polling, batching, deletes on success)
* Configuring SQS event source mapping for Lambda
* DynamoDB getting started: create table
* DynamoDB key design / best practices
* ECR: authenticate + push images


##########
Repo skeleton (straightforward)

```lua
.
├─ services/
│  ├─ svc-api/
│  └─ svc-worker/
├─ infra/
│  ├─ aws-cli/            # create-queue.sh, create-table.sh, create-lambda.sh
│  ├─ ec2/                 # EC2 + Docker Compose deployment scripts
│  ├─ ecs/                 # ECS Fargate deployment scripts
│  └─ iam/                 # policies (least privilege)
├─ k8s/                    # LOCAL Kubernetes only (for learning)
│  ├─ base/
│  └─ overlays/dev/
├─ scripts/
│  ├─ deploy.sh            # Main deployment script (supports --ec2, --ecs, --k8s-local)
│  ├─ deploy-k8s-local.sh  # Local K8s deployment
│  └─ teardown.sh
└─ docs/
   ├─ architecture.md
   ├─ deployment-options.md
   └─ manual-deployment-guide.md  # EC2 + Docker Compose guide
```


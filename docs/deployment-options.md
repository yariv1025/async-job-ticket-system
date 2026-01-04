# Deployment Options Quick Reference

This document provides a quick comparison of deployment options available for this system.

## Overview

| Option | Use Case | Complexity | Cost | Scalability |
|-------|----------|------------|------|-------------|
| **Local K8s** | Learning, Development | Medium | Free | Manual |
| **ECS Fargate** | Production (Recommended) | Low-Medium | Pay per task | Auto-scaling |
| **EC2 + Docker Compose** | Small apps, Simple setup | Low | Fixed EC2 cost | Manual |

## Option 1: Kubernetes (Local Only)

**When to use:**
- Learning Kubernetes concepts
- Local development and testing
- Understanding container orchestration

**Requirements:**
- Local K8s cluster (minikube, kind, k3d)
- kubectl installed

**Deploy:**
```bash
./scripts/deploy-k8s-local.sh
```

**Pros:**
- Learn K8s without cloud costs
- Same containerized setup as production
- Good for development

**Cons:**
- Not for AWS cloud deployment
- Requires local cluster setup
- Manual scaling

## Option 2: ECS Fargate (Recommended for AWS)

**When to use:**
- Production deployments
- Need auto-scaling
- Want serverless containers (no EC2 management)
- Small to medium applications

**Requirements:**
- AWS account
- AWS CLI configured
- Docker images in ECR

**Deploy:**
```bash
# Phase 1: Infrastructure
./infra/aws-cli/create-table.sh
./infra/aws-cli/create-queues.sh
./infra/aws-cli/create-ecr-repos.sh
./infra/aws-cli/setup-parameter-store.sh

# Phase 2: Build & Push Images
# (see deployment.md for details)

# Phase 3: Deploy
./scripts/deploy.sh --ecs
```

**Pros:**
- No EC2 management
- Auto-scaling built-in
- Pay only for running tasks
- Production-ready
- Integrated with AWS services

**Cons:**
- Slightly more complex than EC2
- Requires understanding of ECS concepts

**Cost:** ~$0.04/hour per task (256 CPU, 512 MB) + data transfer

## Option 3: EC2 + Docker Compose (Simplest)

**When to use:**
- Small applications
- Simple infrastructure needs
- Always-on workloads
- Full control over environment

**Requirements:**
- AWS account
- AWS CLI configured
- Docker images in ECR

**Deploy:**
```bash
# Phase 1: Infrastructure (same as ECS)
./infra/aws-cli/create-table.sh
./infra/aws-cli/create-queues.sh
./infra/aws-cli/create-ecr-repos.sh
./infra/aws-cli/setup-parameter-store.sh

# Phase 2: Build & Push Images (same as ECS)

# Phase 3: Deploy
./scripts/deploy.sh --ec2
```

**Pros:**
- Simplest infrastructure
- Full control
- Easy to understand
- Good for small apps

**Cons:**
- Manual scaling
- EC2 instance always running (cost)
- Need to manage EC2 instance
- Single point of failure (unless multiple instances)

**Cost:** ~$15-30/month for t3.small instance

## Decision Tree

```
Start
  │
  ├─ Learning/Development?
  │   └─> Use Local K8s
  │
  ├─ Production on AWS?
  │   │
  │   ├─ Need auto-scaling?
  │   │   └─> Use ECS Fargate
  │   │
  │   └─ Simple, always-on?
  │       └─> Use EC2 + Docker Compose
```

## Migration Path

1. **Start Local:** Use Local K8s for development
2. **Deploy to AWS:** Choose ECS Fargate or EC2 based on needs
3. **Scale Up:** ECS Fargate can auto-scale; EC2 requires manual scaling

## Quick Commands

### Check ECS Status
```bash
aws ecs describe-services --cluster jobsys-cluster --services svc-api svc-worker
```

### Check EC2 Status
```bash
aws ec2 describe-instances --filters "Name=tag:Name,Values=jobsys-ec2"
```

### View Logs (ECS)
```bash
aws logs tail /ecs/jobsys/svc-api --follow
```

### View Logs (EC2)
```bash
ssh ec2-user@<IP> 'cd /opt/jobsys && docker-compose logs -f'
```

## Next Steps

For detailed instructions, see [Deployment Guide](deployment.md).


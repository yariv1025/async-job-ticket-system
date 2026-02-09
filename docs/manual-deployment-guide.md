# Manual AWS Deployment Guide

## 🎓 Learning Objectives

This guide will teach you:
- **What cloud services are** and why we use them
- **How AWS services work together** in a real application
- **The concept of managed services** vs. self-hosted
- **Security in the cloud** (IAM roles and policies)
- **Event-driven architecture** (SQS, Lambda)
- **Infrastructure as Code** concepts

---

## 📚 Understanding Cloud Services

### What is "The Cloud"?

Instead of buying and maintaining physical servers, you **rent computing resources** from AWS. Think of it like:
- **Old way:** Buy a car, maintain it, park it, insure it
- **Cloud way:** Use Uber - pay only when you use it, no maintenance

### Why Use Managed Services?

**Managed services** (like DynamoDB, SQS) are services where AWS handles:
- Server maintenance
- Software updates
- Scaling (handling more traffic)
- Backups
- Security patches

You just **configure and use** them. This is why we use:
- **DynamoDB** instead of installing MySQL on EC2
- **SQS** instead of running RabbitMQ
- **Lambda** instead of managing servers for small functions

---

## 🎯 Architecture Overview

Before we start, understand the **data flow**:

```
Client → API (EC2) → DynamoDB (store job) → SQS (send message)
                  
Worker (EC2) ← SQS (receive message) → DynamoDB (update job status)
           
DLQ (SQS) → Lambda → DynamoDB (mark as failed)
```

**Key Concept:** Services communicate through **AWS APIs**, not direct connections. This is called a **loosely coupled architecture**.

---

## ✅ Prerequisites

### 1. AWS Account Setup

**What you need:**
- AWS account (free tier eligible)
- AWS CLI installed and configured
- Basic terminal knowledge

**Verify AWS CLI:**
```bash
aws --version
aws sts get-caller-identity  # Should show your account ID
```

**If AWS CLI is not configured:**

If the `aws sts get-caller-identity` command fails or shows an error, you need to configure AWS CLI with your credentials.

**Step 1: Get AWS Access Keys**

1. Log in to [AWS Console](https://console.aws.amazon.com)
2. Click on your username (top right) → **Security credentials**
3. Scroll to **Access keys** section
4. Click **Create access key**
5. Choose **Command Line Interface (CLI)** as the use case
6. Check the confirmation box and click **Next**
7. Optionally add a description tag, then click **Create access key**
8. **IMPORTANT:** Copy both the **Access Key ID** and **Secret Access Key** immediately (you won't see the secret again!)

**Step 2: Configure AWS CLI**

Run the configure command:
```bash
aws configure
```

You'll be prompted for:
- **AWS Access Key ID:** Paste your access key ID
- **AWS Secret Access Key:** Paste your secret access key
- **Default region name:** Enter `us-east-1` (or your preferred region)
- **Default output format:** Enter `json` (recommended)

**Verify configuration:**
```bash
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

**💡 Security Tip:** Never share your access keys or commit them to version control. If keys are exposed, delete them immediately and create new ones.

**Set your region:**
```bash
export AWS_REGION=us-east-1  # Or your preferred region
```

### 2. Understanding AWS Regions

**Concept:** AWS has data centers worldwide called **regions**. Each region is independent.

**Why it matters:** 
- Services in one region can't directly access services in another
- Choose a region close to you (lower latency)
- Free tier applies per region

**Common regions:**
- `us-east-1` (N. Virginia) - often cheapest
- `us-west-2` (Oregon)
- `eu-west-1` (Ireland)

---

## 📋 Step-by-Step Deployment

### Step 1: Create DynamoDB Table

**What is DynamoDB?**
A **NoSQL database** - think of it as a giant spreadsheet where each row can have different columns. AWS manages the servers for you.

**Why DynamoDB?**
- No server management
- Auto-scaling
- Fast (millisecond latency)
- Pay only for what you use

**Create the table:**

```bash
aws dynamodb create-table \
    --table-name Jobs \
    --attribute-definitions \
        AttributeName=jobId,AttributeType=S \
        AttributeName=idempotencyKey,AttributeType=S \
    --key-schema \
        AttributeName=jobId,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=idempotencyKey-index,KeySchema=[{AttributeName=idempotencyKey,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}' \
    --billing-mode PROVISIONED \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region $AWS_REGION
```

**Understanding the command:**
- `--table-name Jobs`: Name of our table
- `--key-schema`: `jobId` is the **primary key** (like a row ID)
- `--global-secondary-indexes`: Allows querying by `idempotencyKey` (like a database index)
- `--billing-mode PROVISIONED`: We specify capacity (free tier: 25 read/write units)

**Verify:**
```bash
aws dynamodb describe-table --table-name Jobs --region $AWS_REGION
```

**Expected output:** Table status should be `ACTIVE` (takes ~30 seconds)

**💡 Learning Point:** DynamoDB is **serverless** - you don't manage servers, just configure the table structure.

---

### Step 2: Create SQS Queues

**What is SQS?**
**Simple Queue Service** - a message queue. Think of it as a **post office box**:
- One service puts messages in (API)
- Another service takes messages out (Worker)
- Messages wait in the queue until processed

**Why SQS?**
- **Decoupling:** API doesn't wait for worker to process
- **Reliability:** Messages are stored until processed
- **Scalability:** Can handle millions of messages

**Create main queue:**

```bash
aws sqs create-queue \
    --queue-name jobs-queue \
    --attributes \
        VisibilityTimeout=300,MessageRetentionPeriod=1209600 \
    --region $AWS_REGION
```

**Understanding:**
- `VisibilityTimeout=300`: When a worker reads a message, it's "invisible" for 5 minutes (processing time)
- `MessageRetentionPeriod=1209600`: Messages kept for 14 days if not processed

**Save the queue URL:**
```bash
QUEUE_URL=$(aws sqs get-queue-url --queue-name jobs-queue --region $AWS_REGION --query 'QueueUrl' --output text)
echo "Queue URL: $QUEUE_URL"
```

**Create Dead Letter Queue (DLQ):**

**What is a DLQ?**
A **Dead Letter Queue** holds messages that failed processing multiple times. It's like a "failed mail" box.

**Why DLQ?**
- Prevents infinite retries
- Allows investigation of failed messages
- Keeps main queue clean

```bash
aws sqs create-queue \
    --queue-name jobs-dlq \
    --attributes MessageRetentionPeriod=1209600 \
    --region $AWS_REGION
```

**Get DLQ URL:**
```bash
DLQ_URL=$(aws sqs get-queue-url --queue-name jobs-dlq --region $AWS_REGION --query 'QueueUrl' --output text)
DLQ_ARN=$(aws sqs get-queue-attributes \
    --queue-url "$DLQ_URL" \
    --attribute-names QueueArn \
    --region $AWS_REGION \
    --query 'Attributes.QueueArn' \
    --output text)
echo "DLQ ARN: $DLQ_ARN"
```

**Connect DLQ to main queue (Redrive Policy):**

**What is Redrive?**
A policy that automatically moves messages from main queue to DLQ after X failed attempts.

```bash
aws sqs set-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attributes \
        '{"RedrivePolicy":"{\"deadLetterTargetArn\":\"'$DLQ_ARN'\",\"maxReceiveCount\":3}"}' \
    --region $AWS_REGION
```

**Understanding:**
- `maxReceiveCount=3`: After 3 failed processing attempts, message goes to DLQ

**Verify:**
```bash
aws sqs list-queues --region $AWS_REGION
```

**💡 Learning Point:** SQS provides **asynchronous messaging** - services don't need to be running at the same time.

---

### Step 3: Create ECR Repositories

**What is ECR?**
**Elastic Container Registry** - a place to store Docker images (like Docker Hub, but private on AWS).

**Why ECR?**
- Private image storage
- Integrated with AWS services
- Secure (IAM-controlled access)

**Create repositories:**

```bash
# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create API repository
aws ecr create-repository \
    --repository-name svc-api \
    --region $AWS_REGION

# Create Worker repository
aws ecr create-repository \
    --repository-name svc-worker \
    --region $AWS_REGION
```

**Verify:**
```bash
aws ecr describe-repositories --region $AWS_REGION
```

**💡 Learning Point:** ECR is like a **private Docker registry** - you push images here, then pull them when deploying.

---

### Step 4: Build and Push Docker Images

**What are Docker images?**
Packaged applications with all dependencies. Like a **shipping container** - works the same everywhere.

**Build images locally:**

```bash
# Navigate to project root
cd /path/to/async-job-ticket-system

# Build API image
cd services/svc-api
docker build -t svc-api:latest .

# Build Worker image
cd ../svc-worker
docker build -t svc-worker:latest .
```

**Login to ECR:**

```bash
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

**Tag and push images:**

```bash
# Tag API image
docker tag svc-api:latest \
    $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/svc-api:latest

# Tag Worker image
docker tag svc-worker:latest \
    $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/svc-worker:latest

# Push API image
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/svc-api:latest

# Push Worker image
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/svc-worker:latest
```

**Verify:**
```bash
aws ecr list-images --repository-name svc-api --region $AWS_REGION
aws ecr list-images --repository-name svc-worker --region $AWS_REGION
```

**💡 Learning Point:** Docker containers ensure your app runs the same way locally and in the cloud.

---

### Step 5: Store Configuration in Parameter Store

**What is Parameter Store?**
A **secure storage** for configuration values (like database URLs, API keys). Better than hardcoding.

**Why Parameter Store?**
- Centralized configuration
- Secure (encrypted)
- Can update without redeploying code
- Free tier: 10,000 parameters

**Store configuration:**

```bash
ENV=dev

# Store SQS queue URL
aws ssm put-parameter \
    --name "/jobsys/$ENV/sqs/queue-url" \
    --value "$QUEUE_URL" \
    --type "String" \
    --region $AWS_REGION \
    --description "SQS queue URL for jobs"

# Store DLQ URL
aws ssm put-parameter \
    --name "/jobsys/$ENV/sqs/dlq-url" \
    --value "$DLQ_URL" \
    --type "String" \
    --region $AWS_REGION \
    --description "SQS DLQ URL for failed jobs"

# Store DynamoDB table name
aws ssm put-parameter \
    --name "/jobsys/$ENV/dynamodb/table-name" \
    --value "Jobs" \
    --type "String" \
    --region $AWS_REGION \
    --description "DynamoDB table name"

# Store AWS region
aws ssm put-parameter \
    --name "/jobsys/$ENV/aws/region" \
    --value "$AWS_REGION" \
    --type "String" \
    --region $AWS_REGION \
    --description "AWS region"
```

**Verify:**
```bash
aws ssm get-parameter \
    --name "/jobsys/$ENV/sqs/queue-url" \
    --region $AWS_REGION \
    --query 'Parameter.Value' \
    --output text
```

**💡 Learning Point:** **Configuration management** separates code from environment-specific values.

---

### Step 6: Create IAM Roles and Policies

**What is IAM?**
**Identity and Access Management** - controls **who can do what** in AWS.

**Key Concepts:**
- **Principle of Least Privilege:** Give only the minimum permissions needed
- **Roles:** Like a "job title" - defines what actions are allowed
- **Policies:** Documents that define permissions

**Why IAM?**
- Security: Services can't access resources they shouldn't
- Audit: Track who did what
- Compliance: Meet security requirements

**Create IAM role for EC2:**

**Step 6.1: Create trust policy**

A **trust policy** defines **who can assume** (use) this role. EC2 instances can assume this role.

```bash
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
```

**Step 6.2: Create the role**

```bash
aws iam create-role \
    --role-name jobsys-ec2-role \
    --assume-role-policy-document file:///tmp/ec2-trust-policy.json \
    --region $AWS_REGION
```

**Step 6.3: Create policy document**

This policy defines what the EC2 instance can do (access DynamoDB, SQS, etc.)

```bash
cat > /tmp/ec2-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/Jobs",
        "arn:aws:dynamodb:*:*:table/Jobs/index/*"
      ]
    },
    {
      "Sid": "SQSAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:*:*:jobs-queue"
    },
    {
      "Sid": "ParameterStoreAccess",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/jobsys/*"
    },
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/jobsys/*"
    }
  ]
}
EOF
```

**Step 6.4: Attach policy to role**

```bash
aws iam put-role-policy \
    --role-name jobsys-ec2-role \
    --policy-name jobsys-ec2-policy \
    --policy-document file:///tmp/ec2-policy.json \
    --region $AWS_REGION
```

**Step 6.5: Create instance profile**

An **instance profile** is a metadata attached to the instance(for a role that can be attached to EC2 instances), and AWS provides temporary credentials via the Instance Metadata Service (IMDS).

Instance profile:
- Metadata attached to the EC2 instance
- Stored in AWS, not running on the instance
- Tells AWS which IAM role the instance can use

Instance Metadata Service (IMDS):
- Built into every EC2 instance
- Provides temporary credentials to the instance
- Accessible at http://169.254.169.254 (link-local address)

The flow:
1. EC2 Instance starts
   ↓
2. AWS checks: "Does this instance have an instance profile?"
   ↓
3. If yes: AWS generates temporary credentials from the IAM role
   ↓
4. Credentials stored in IMDS (Instance Metadata Service)
   ↓
5. Your application on EC2 requests credentials from IMDS
   ↓
6. IMDS returns temporary credentials (valid for ~6 hours)
   ↓
7. Your app uses these credentials to call AWS services


┌─────────────────────────────────────┐
│         EC2 Instance                 │
│  ┌───────────────────────────────┐  │
│  │  Your Application             │  │
│  │  (svc-api, svc-worker)        │  │
│  └───────────┬───────────────────┘  │
│              │                       │
│              │ Requests credentials │
│              ↓                       │
│  ┌───────────────────────────────┐  │
│  │  IMDS (Instance Metadata)     │  │
│  │  http://169.254.169.254       │  │
│  └───────────┬───────────────────┘  │
└──────────────┼───────────────────────┘
               │
               │ Returns temporary credentials
               ↓
┌──────────────────────────────────────┐
│  AWS IAM Service                    │
│  (Validates instance profile)       │
│  (Generates temporary credentials)  │
└──────────────────────────────────────┘


```bash
aws iam create-instance-profile \
    --instance-profile-name jobsys-ec2-role \
    --region $AWS_REGION

aws iam add-role-to-instance-profile \
    --instance-profile-name jobsys-ec2-role \
    --role-name jobsys-ec2-role \
    --region $AWS_REGION
```

**Verify:**
```bash
aws iam get-role --role-name jobsys-ec2-role --region $AWS_REGION
aws iam get-instance-profile --instance-profile-name jobsys-ec2-role --region $AWS_REGION
```

**💡 Learning Point:** IAM ensures **security by default** - services can only access what they're explicitly allowed to.

---

### Step 7: Create EC2 Instance

**What is EC2?**
**Elastic Compute Cloud** - virtual servers in the cloud. You rent a computer that AWS manages.

**Why EC2?**
- Full control over the operating system
- Can run any application
- Pay only for what you use
- Free tier: t3.micro for 750 hours/month

**Step 7.1: Get default VPC**

**What is VPC?**
**Virtual Private Cloud** - your own private network in AWS. Every account has a default VPC.

```bash
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --region $AWS_REGION \
    --query 'Vpcs[0].VpcId' \
    --output text)

echo "VPC ID: $VPC_ID"
```

**Step 7.2: Create security group**

**What is a Security Group?**
A **firewall** that controls inbound/outbound traffic to your EC2 instance.

**Why Security Groups?**
- Security: Only allow necessary ports
- Network isolation: Control who can access your instance

```bash
SG_ID=$(aws ec2 create-security-group \
    --group-name jobsys-ec2-sg \
    --description "Security group for jobsys EC2 instance" \
    --vpc-id "$VPC_ID" \
    --region $AWS_REGION \
    --query 'GroupId' \
    --output text)

echo "Security Group ID: $SG_ID"
```

**Step 7.3: Add rules to security group**

Allow SSH (port 22) and HTTP API (port 8080):

```bash
# Allow SSH from anywhere (you can restrict to your IP)
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 22 \
    --cidr "$MY_IP/32" \
    --region $AWS_REGION

# Allow HTTP API from anywhere (for testing)
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION
```

**Step 7.4: Get latest Amazon Linux 2 AMI**

**What is an AMI?**
**Amazon Machine Image** - a template for creating EC2 instances (like a disk image).

```bash
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
    --output text \
    --region $AWS_REGION)

echo "AMI ID: $AMI_ID"
```

**Step 7.5: Create user data script**

**What is User Data?**
A script that runs **once** when the instance first starts. We'll use it to install Docker and deploy our app.

```bash
cat > /tmp/user-data.sh <<'EOF'
#!/bin/bash
# Install Docker
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create application directory
mkdir -p /opt/jobsys
cd /opt/jobsys

# Create docker-compose.yml
cat > docker-compose.yml <<'COMPOSE_EOF'
version: '3.8'
services:
  api:
    image: ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/svc-api:latest
    ports:
      - "8080:8080"
    environment:
      - AWS_REGION=REGION
      - ENV=dev
      - DDB_TABLE=Jobs
      - SQS_QUEUE_URL=QUEUE_URL
    restart: unless-stopped
  
  worker:
    image: ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/svc-worker:latest
    environment:
      - AWS_REGION=REGION
      - ENV=dev
      - DDB_TABLE=Jobs
      - SQS_QUEUE_URL=QUEUE_URL
    restart: unless-stopped
COMPOSE_EOF

# Replace placeholders (we'll do this manually after instance starts)
# For now, we'll pull images and start services manually
EOF

chmod +x /tmp/user-data.sh
```

**Step 7.6: Launch EC2 instance**

```bash
USER_DATA=$(cat /tmp/user-data.sh | base64 -w 0 2>/dev/null || cat /tmp/user-data.sh | base64)

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type t3.micro \
    --security-group-ids "$SG_ID" \
    --iam-instance-profile Name=jobsys-ec2-role \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=jobsys-ec2},{Key=Environment,Value=dev}]" \
    --region $AWS_REGION \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance ID: $INSTANCE_ID"
```

**Wait for instance to be running:**
```bash
echo "Waiting for instance to start..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region $AWS_REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region $AWS_REGION \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "✅ Instance is running!"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"
echo ""
echo "Wait 2-3 minutes for initialization, then SSH:"
echo "   ssh ec2-user@$PUBLIC_IP"
```

**💡 Learning Point:** EC2 gives you a **virtual server** - a computer in the cloud you can configure and control.

---

### Step 8: Deploy Application to EC2

**Step 8.1: SSH to instance**

Wait 2-3 minutes for initialization, then:

```bash
ssh ec2-user@$PUBLIC_IP
```

**Step 8.2: Login to ECR**

On the EC2 instance:

```bash
# Get your account ID (you'll need to set this)
ACCOUNT_ID="YOUR_ACCOUNT_ID"  # Replace with your account ID
REGION="us-east-1"  # Replace with your region

aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin \
    $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
```

**Step 8.3: Pull images**

```bash
docker pull $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/svc-api:latest
docker pull $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/svc-worker:latest
```

**Step 8.4: Get configuration from Parameter Store**

```bash
QUEUE_URL=$(aws ssm get-parameter \
    --name "/jobsys/dev/sqs/queue-url" \
    --region $REGION \
    --query 'Parameter.Value' \
    --output text)

echo "Queue URL: $QUEUE_URL"
```

**Step 8.5: Create docker-compose.yml**

```bash
mkdir -p /opt/jobsys
cd /opt/jobsys

cat > docker-compose.yml <<EOF
version: '3.8'
services:
  api:
    image: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/svc-api:latest
    ports:
      - "8080:8080"
    environment:
      - AWS_REGION=$REGION
      - ENV=dev
      - DDB_TABLE=Jobs
      - SQS_QUEUE_URL=$QUEUE_URL
    restart: unless-stopped
  
  worker:
    image: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/svc-worker:latest
    environment:
      - AWS_REGION=$REGION
      - ENV=dev
      - DDB_TABLE=Jobs
      - SQS_QUEUE_URL=$QUEUE_URL
    restart: unless-stopped
EOF
```

**Step 8.6: Start services**

```bash
docker-compose up -d
```

**Step 8.7: Verify services are running**

```bash
docker-compose ps
docker-compose logs -f  # Press Ctrl+C to exit
```

**💡 Learning Point:** Docker Compose orchestrates multiple containers - your API and Worker run as separate containers but can communicate.

---

### Step 9: Create Lambda Function

**What is Lambda?**
**Serverless compute** - you write a function, AWS runs it when triggered. No servers to manage!

**Why Lambda?**
- No server management
- Pay only when function runs
- Auto-scaling
- Perfect for event-driven tasks

**Step 9.1: Create Lambda deployment package**

On your local machine:

```bash
cd /path/to/async-job-ticket-system/lambda/dlq-handler

# Create deployment package
zip -r dlq-handler.zip .
```

**Step 9.2: Create IAM role for Lambda**

```bash
# Create trust policy for Lambda
cat > /tmp/lambda-trust-policy.json <<EOF
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
    --role-name dlq-handler-role \
    --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
    --region $AWS_REGION

# Create policy for Lambda
cat > /tmp/lambda-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:UpdateItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/Jobs"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
EOF

# Attach policy
aws iam put-role-policy \
    --role-name dlq-handler-role \
    --policy-name dlq-handler-policy \
    --policy-document file:///tmp/lambda-policy.json \
    --region $AWS_REGION

# Get role ARN
LAMBDA_ROLE_ARN=$(aws iam get-role \
    --role-name dlq-handler-role \
    --region $AWS_REGION \
    --query 'Role.Arn' \
    --output text)

echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"
```

**Step 9.3: Create Lambda function**

```bash
aws lambda create-function \
    --function-name dlq-handler \
    --runtime python3.11 \
    --role "$LAMBDA_ROLE_ARN" \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://dlq-handler.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={DDB_TABLE=Jobs}" \
    --region $AWS_REGION
```

**Verify:**
```bash
aws lambda get-function --function-name dlq-handler --region $AWS_REGION
```

**💡 Learning Point:** Lambda is **event-driven** - it runs automatically when triggered, no need to keep a server running.

---

### Step 10: Connect Lambda to DLQ

**Step 10.1: Create event source mapping**

This connects the DLQ to Lambda - when a message arrives in DLQ, Lambda runs automatically.

```bash
aws lambda create-event-source-mapping \
    --function-name dlq-handler \
    --event-source-arn "$DLQ_ARN" \
    --batch-size 1 \
    --region $AWS_REGION
```

**Verify:**
```bash
aws lambda list-event-source-mappings \
    --function-name dlq-handler \
    --region $AWS_REGION
```

**💡 Learning Point:** **Event source mapping** creates an automatic connection - no polling needed, Lambda is triggered instantly.

---

## 🧪 Testing Your Deployment

### Test 1: Create a Job

```bash
# Replace with your EC2 public IP
API_URL="http://$PUBLIC_IP:8080"

# Create a job
curl -X POST "$API_URL/api/v1/jobs" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-$(date +%s)" \
  -d '{
    "type": "process_document",
    "priority": "normal",
    "params": {
      "source": "s3://bucket/test.pdf"
    }
  }'
```

**Expected:** JSON response with `jobId` and `status: "PENDING"`

### Test 2: Check Job Status

```bash
# Use the jobId from previous response
JOB_ID="YOUR_JOB_ID"

curl "$API_URL/api/v1/jobs/$JOB_ID"
```

**Expected:** Status should change from `PENDING` → `PROCESSING` → `SUCCEEDED`

### Test 3: Verify in DynamoDB

```bash
aws dynamodb get-item \
    --table-name Jobs \
    --key "{\"jobId\":{\"S\":\"$JOB_ID\"}}" \
    --region $AWS_REGION
```

### Test 4: Check CloudWatch Logs

```bash
# Check API logs
aws logs tail /aws/jobsys/svc-api --follow --region $AWS_REGION

# Check Worker logs
aws logs tail /aws/jobsys/svc-worker --follow --region $AWS_REGION
```

### Test 5: Verify SQS Queue

```bash
# Check queue attributes
aws sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names All \
    --region $AWS_REGION
```

---

## 🎓 Key Concepts Learned

### 1. **Managed Services**
- DynamoDB: Managed database (no servers)
- SQS: Managed message queue (no servers)
- Lambda: Managed compute (no servers)
- ECR: Managed container registry

### 2. **Security (IAM)**
- Roles: Define what services can do
- Policies: Document permissions
- Least Privilege: Minimum necessary permissions

### 3. **Event-Driven Architecture**
- Services communicate through events (SQS messages)
- Decoupled: Services don't need to know about each other
- Scalable: Can add more workers without changing API

### 4. **Infrastructure as Code**
- All resources defined in scripts
- Reproducible deployments
- Version controlled

### 5. **Cloud Benefits**
- No server management
- Auto-scaling potential
- Pay only for what you use
- Global infrastructure

---

## 🧹 Cleanup (Important!)

**To avoid charges, delete everything when done:**

```bash
# Delete Lambda
aws lambda delete-function --function-name dlq-handler --region $AWS_REGION

# Delete event source mapping
ESM_UUID=$(aws lambda list-event-source-mappings \
    --function-name dlq-handler \
    --region $AWS_REGION \
    --query 'EventSourceMappings[0].UUID' \
    --output text)
aws lambda delete-event-source-mapping --uuid "$ESM_UUID" --region $AWS_REGION

# Delete IAM roles
aws iam delete-role-policy --role-name dlq-handler-role --policy-name dlq-handler-policy --region $AWS_REGION
aws iam delete-role --role-name dlq-handler-role --region $AWS_REGION

aws iam remove-role-from-instance-profile --instance-profile-name jobsys-ec2-role --role-name jobsys-ec2-role --region $AWS_REGION
aws iam delete-instance-profile --instance-profile-name jobsys-ec2-role --region $AWS_REGION
aws iam delete-role-policy --role-name jobsys-ec2-role --policy-name jobsys-ec2-policy --region $AWS_REGION
aws iam delete-role --role-name jobsys-ec2-role --region $AWS_REGION

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region $AWS_REGION

# Delete security group
aws ec2 delete-security-group --group-id "$SG_ID" --region $AWS_REGION

# Delete SQS queues
aws sqs delete-queue --queue-url "$QUEUE_URL" --region $AWS_REGION
aws sqs delete-queue --queue-url "$DLQ_URL" --region $AWS_REGION

# Delete DynamoDB table
aws dynamodb delete-table --table-name Jobs --region $AWS_REGION

# Delete ECR images and repositories
aws ecr batch-delete-image \
    --repository-name svc-api \
    --image-ids imageTag=latest \
    --region $AWS_REGION
aws ecr delete-repository --repository-name svc-api --region $AWS_REGION

aws ecr batch-delete-image \
    --repository-name svc-worker \
    --image-ids imageTag=latest \
    --region $AWS_REGION
aws ecr delete-repository --repository-name svc-worker --region $AWS_REGION

# Delete Parameter Store parameters
aws ssm delete-parameter --name "/jobsys/dev/sqs/queue-url" --region $AWS_REGION
aws ssm delete-parameter --name "/jobsys/dev/sqs/dlq-url" --region $AWS_REGION
aws ssm delete-parameter --name "/jobsys/dev/dynamodb/table-name" --region $AWS_REGION
aws ssm delete-parameter --name "/jobsys/dev/aws/region" --region $AWS_REGION
```

---

## 📚 Further Learning

### AWS Concepts to Explore:
1. **VPC and Networking:** Subnets, route tables, internet gateways
2. **Auto Scaling:** Automatically add/remove EC2 instances
3. **Load Balancing:** Distribute traffic across multiple instances
4. **CloudFormation:** Infrastructure as Code (automated version of this guide)
5. **Monitoring:** CloudWatch alarms, dashboards, metrics

### Practice Ideas:
1. Add auto-scaling to EC2
2. Set up CloudWatch alarms
3. Create a CloudFormation template
4. Add HTTPS with Application Load Balancer
5. Implement blue/green deployments

---

## 🆘 Troubleshooting

### EC2 instance not accessible
- Check security group rules
- Verify instance is running: `aws ec2 describe-instance-status --instance-ids $INSTANCE_ID`
- Check if public IP changed (use Elastic IP for static IP)

### Services can't access AWS resources
- Verify IAM role is attached: `aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].IamInstanceProfile'`
- Check IAM policy permissions
- Verify resource ARNs match in policy

### Lambda not triggered
- Check event source mapping status
- Verify DLQ has messages: `aws sqs get-queue-attributes --queue-url $DLQ_URL --attribute-names ApproximateNumberOfMessages`
- Check Lambda logs: `aws logs tail /aws/lambda/dlq-handler --follow`

### Docker images not pulling
- Verify ECR login: `aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com`
- Check IAM role has ECR permissions
- Verify image exists: `aws ecr list-images --repository-name svc-api`

---

## ✅ Success Checklist

- [ ] DynamoDB table created and active
- [ ] SQS queues created with redrive policy
- [ ] ECR repositories created
- [ ] Docker images built and pushed
- [ ] Parameter Store values set
- [ ] IAM roles and policies created
- [ ] EC2 instance running
- [ ] Services deployed and running
- [ ] Lambda function created
- [ ] Event source mapping configured
- [ ] Test job created successfully
- [ ] Job processed successfully
- [ ] Logs visible in CloudWatch

**Congratulations!** You've manually deployed a complete cloud application and learned how AWS services work together! 🎉


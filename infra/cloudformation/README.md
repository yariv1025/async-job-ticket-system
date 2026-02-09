# CloudFormation Infrastructure as Code

This directory contains production-grade CloudFormation templates for deploying the Job System infrastructure.

## 📁 Directory Structure

```
infra/cloudformation/
├── templates/           # CloudFormation YAML templates
│   ├── 01-iam.yaml
│   ├── 02-dynamodb.yaml
│   ├── 03-sqs.yaml
│   ├── 04-ecr.yaml
│   ├── 05-parameter-store.yaml
│   ├── 06-lambda.yaml
│   ├── 07-ec2.yaml
│   └── 08-cloudwatch.yaml
├── parameters/          # Parameter files for different environments
│   ├── dev.json
│   └── prod.json
├── deploy.sh           # Automated deployment script
├── teardown.sh         # Cleanup script
└── README.md           # This file
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI configured:**
   ```bash
   aws --version
   aws sts get-caller-identity
   ```

2. **Set your region:**
   ```bash
   export AWS_REGION=us-east-1
   ```

3. **Install jq (for deploy script):**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install jq
   
   # macOS
   brew install jq
   ```

### Deploy Infrastructure

**Option 1: Using the automated script (recommended):**

```bash
cd infra/cloudformation
./deploy.sh dev
```

**Option 2: Manual deployment:**

```bash
# 1. Deploy IAM
aws cloudformation create-stack \
    --stack-name jobsys-iam \
    --template-body file://templates/01-iam.yaml \
    --parameters file://parameters/dev.json \
    --capabilities CAPABILITY_NAMED_IAM \
    --region us-east-1

# Wait for completion
aws cloudformation wait stack-create-complete \
    --stack-name jobsys-iam \
    --region us-east-1

# 2. Continue with other stacks...
# See docs/iac-cloudformation-guide.md for full instructions
```

### Teardown (Delete All Infrastructure)

```bash
cd infra/cloudformation
./teardown.sh dev
```

**⚠️ Warning:** This will delete all resources. Make sure you have backups if needed!

## 📋 Stack Deployment Order

Stacks must be deployed in this order due to dependencies:

1. **IAM** (`01-iam.yaml`) - Creates roles needed by other resources
2. **DynamoDB** (`02-dynamodb.yaml`) - Database table
3. **SQS** (`03-sqs.yaml`) - Message queues
4. **ECR** (`04-ecr.yaml`) - Container repositories
5. **Parameter Store** (`05-parameter-store.yaml`) - Configuration storage
6. **CloudWatch** (`08-cloudwatch.yaml`) - Log groups
7. **Lambda** (`06-lambda.yaml`) - DLQ handler function
8. **EC2** (`07-ec2.yaml`) - Compute instance (optional)

## 🎯 Template Details

### 01-iam.yaml
- EC2 instance role and instance profile
- Lambda execution role
- Least privilege IAM policies

### 02-dynamodb.yaml
- Jobs table with GSI for idempotency
- Point-in-time recovery enabled
- TTL enabled for automatic cleanup

### 03-sqs.yaml
- Main jobs queue
- Dead letter queue (DLQ)
- Redrive policy configured

### 04-ecr.yaml
- ECR repositories for API and Worker services
- Lifecycle policies (keep last 10 images)
- Image scanning enabled

### 05-parameter-store.yaml
- Stores configuration values
- References outputs from other stacks

### 06-lambda.yaml
- DLQ handler Lambda function
- Event source mapping (DLQ → Lambda)
- X-Ray tracing enabled

### 07-ec2.yaml
- EC2 instance (optional)
- Security group
- User data script for Docker setup

### 08-cloudwatch.yaml
- CloudWatch log groups
- Retention policies

## 🔧 Customization

### Modify Parameters

Edit `parameters/dev.json` or `parameters/prod.json`:

```json
{
  "ParameterKey": "InstanceType",
  "ParameterValue": "t3.small"
}
```

### Add New Resources

1. Create a new template file in `templates/`
2. Add parameters to parameter files
3. Update `deploy.sh` to include the new stack

## 📊 Viewing Stack Information

### List All Stacks

```bash
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --region us-east-1
```

### View Stack Outputs

```bash
aws cloudformation describe-stacks \
    --stack-name jobsys-dynamodb \
    --region us-east-1 \
    --query 'Stacks[0].Outputs'
```

### View Stack Events

```bash
aws cloudformation describe-stack-events \
    --stack-name jobsys-dynamodb \
    --region us-east-1 \
    --max-items 10
```

## 🐛 Troubleshooting

### Stack Creation Failed

1. Check stack events:
   ```bash
   aws cloudformation describe-stack-events \
       --stack-name <stack-name> \
       --region us-east-1
   ```

2. Common issues:
   - **IAM permissions**: Need `CAPABILITY_NAMED_IAM` for IAM resources
   - **Resource already exists**: Delete existing resources or use different names
   - **Invalid parameters**: Check parameter file format

### Stack Update Failed

1. CloudFormation shows a change set before updating
2. Review the change set to see what will change
3. Some updates require replacement (will delete and recreate)

### Resources Not Deleting

Some resources take time to delete:
- DynamoDB tables (can take several minutes)
- ECR repositories (must be empty first)
- IAM roles (may have dependencies)

## 📚 Learn More

See the comprehensive guide: `docs/iac-cloudformation-guide.md`

## ✅ Best Practices

1. ✅ Always validate templates before deploying
2. ✅ Use parameter files for environment-specific configs
3. ✅ Tag all resources for cost tracking
4. ✅ Review change sets before updating
5. ✅ Test in dev before prod
6. ✅ Version control all templates
7. ✅ Use stack outputs for cross-stack references
8. ✅ Follow least privilege for IAM

## 🎓 What You've Learned

By using these templates, you've learned:

- ✅ Infrastructure as Code concepts
- ✅ CloudFormation template structure
- ✅ Parameterization and reusability
- ✅ Stack dependencies and ordering
- ✅ Production-grade practices
- ✅ How industry professionals deploy infrastructure

This is exactly how real DevOps teams manage cloud infrastructure! 🚀


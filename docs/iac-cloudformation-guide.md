# Production-Grade Infrastructure as Code Guide (CloudFormation)

## 🎓 Learning Objectives

This guide will teach you:
- **What Infrastructure as Code (IaC) is** and why industry uses it
- **How CloudFormation works** (AWS's native IaC tool)
- **Production-grade practices**: parameterization, outputs, conditions, nested stacks
- **Security best practices**: least privilege IAM, resource tagging
- **CI/CD pipelines**: Automate infrastructure and application deployment
- **How to manage infrastructure** like a professional DevOps engineer

---

## 📚 What is Infrastructure as Code?

### The Problem with Manual Infrastructure

**Before IaC:**
- Infrastructure created via console clicks or one-off scripts
- No version control
- Hard to reproduce
- Difficult to track changes
- Error-prone manual processes
- "Snowflake servers" (each one different)

**With IaC:**
- Infrastructure defined in code (YAML/JSON)
- Version controlled (Git)
- Reproducible (same result every time)
- Auditable (see all changes)
- Testable (can validate before deploying)
- **Declarative**: You describe **what** you want, not **how** to create it

### Real-World Analogy

Think of IaC like a **recipe**:
- **Manual way:** "Add some salt, maybe a pinch, taste it, add more..."
- **IaC way:** "Add exactly 5g of salt" (repeatable, documented, versioned)

### Why CloudFormation?

**CloudFormation** is AWS's native IaC tool:
- ✅ **Free** (no additional cost)
- ✅ **Native** (built into AWS)
- ✅ **Powerful** (supports all AWS services)
- ✅ **Industry standard** (used by many companies)
- ✅ **Integrated** (works with AWS Console, CLI, SDKs)

**Alternatives:**
- Terraform (very popular, multi-cloud)
- Pulumi (code-based, multiple languages)
- CDK (AWS's programmatic approach)

We'll use CloudFormation because it's free, native, and teaches core IaC concepts.

---

## 🏗️ CloudFormation Concepts

### Stack

A **stack** is a collection of AWS resources managed as a single unit. Think of it as a "deployment unit."

**Example:** Our "jobsys" stack contains:
- DynamoDB table
- SQS queues
- IAM roles
- Lambda function
- etc.

### Template

A **template** is a JSON or YAML file that describes your infrastructure. It's like a blueprint.

**Template Structure:**
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Description of what this template does'

Parameters:      # Inputs (like function parameters)
  Environment:
    Type: String
    Default: dev

Resources:       # The actual AWS resources
  MyTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: Jobs

Outputs:         # Values returned after creation
  TableName:
    Value: !Ref MyTable
```

### Key Concepts

1. **Parameters**: Inputs to your template (environment, instance size, etc.)
2. **Resources**: The AWS resources you want to create
3. **Outputs**: Values you want to export (URLs, ARNs, etc.)
4. **Conditions**: Logic to create resources conditionally
5. **Mappings**: Key-value lookups (like switch statements)
6. **Intrinsic Functions**: Built-in functions (`!Ref`, `!GetAtt`, `!Sub`, etc.)

That’s the set of "options" you have in CloudFormation: **Parameters** for inputs, **Resources** for what gets created, **Conditions** for when and how, **Outputs** for what you get back, and **intrinsics** to wire it all together.

**Quick reference – where you can use what**

Not every section can use every intrinsic. The table below shows what is allowed where (✅ = allowed, ❌ = not allowed).

| Section      | Parameters | Ref | GetAtt | Sub | If | Conditions | Motivation |
|-------------|------------|-----|--------|-----|----|------------|------------|
| **Parameters** | ✅ define | ✅ | ❌ | ✅ | ❌ | ❌ | **Inputs.** You define and reference parameters; no resource attributes or conditions yet. |
| **Conditions** | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ define | **When and how.** Conditions are pure logic (Ref/equals/etc.); no resource attributes. |
| **Resources**  | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ use | **What gets created.** You reference inputs, other resources (Ref/GetAtt), and conditional values (If). |
| **Outputs**    | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | **What you get back.** You expose Ref/GetAtt/Sub/If; conditions are already resolved in the stack. |

**Short explanation**

- **Parameters**: Define inputs (types, defaults, allowed values). You can use `!Ref` and `!Sub` in parameter metadata; you cannot use `!GetAtt` (no resources exist yet) or define conditions here.
- **Conditions**: Define true/false expressions using `!Ref` and condition functions (`Fn::Equals`, `Fn::Not`, etc.). Used later in Resources (e.g. `Condition: IsProd`) or in property values via `!If`.
- **Resources**: Define the actual AWS resources. You can use all intrinsics here—`!Ref` and `!GetAtt` to reference other resources, `!Sub` for dynamic strings, `!If` for conditional property values—and attach a `Condition` to create the resource only when a condition is true.
- **Outputs**: Expose values after deployment. You can use `!Ref`, `!GetAtt`, `!Sub`, and `!If`; conditions are not defined here but you can still use `!If` with conditions defined in the Conditions section. Optional `Export` makes a value available to other stacks via `Fn::ImportValue`.

---

## 📁 Template Organization Strategy

For production, we'll organize templates by **resource type**:

```
infra/cloudformation/
├── templates/
│   ├── 01-iam.yaml          # IAM roles and policies
│   ├── 02-dynamodb.yaml     # DynamoDB table
│   ├── 03-sqs.yaml          # SQS queues
│   ├── 04-ecr.yaml          # ECR repositories
│   ├── 05-parameter-store.yaml  # Parameter Store
│   ├── 06-lambda.yaml       # Lambda function
│   ├── 07-ec2.yaml          # EC2 instance (optional)
│   └── 08-cloudwatch.yaml   # CloudWatch log groups
├── master.yaml              # Master template (references all)
└── parameters/
    ├── dev.json             # Dev environment parameters
    └── prod.json            # Prod environment parameters
```

**Why this organization?**
- **Separation of concerns**: Each template has a clear purpose
- **Reusability**: Can deploy individual components
- **Maintainability**: Easier to find and update resources
- **Industry standard**: Matches how teams organize IaC

---

## 🚀 Step-by-Step Deployment

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

3. **Install CloudFormation CLI (optional, for validation):**
   ```bash
   # CloudFormation is built into AWS CLI, no separate install needed
   ```

### Phase 1: Create CloudFormation Templates

We'll create templates following production best practices.

**Key Best Practices:**
- ✅ Use parameters for environment-specific values
- ✅ Add descriptions to all resources
- ✅ Use tags for cost tracking and organization
- ✅ Export outputs for cross-stack references
- ✅ Use conditions for optional resources
- ✅ Follow least privilege for IAM

### Phase 2: Prepare Lambda Code (If Deploying Lambda)

Before deploying the Lambda stack, you need to package and upload the Lambda function code:

```bash
# Navigate to Lambda directory
cd lambda/dlq-handler

# Create deployment package
zip -r dlq-handler.zip src/ requirements.txt

# Upload to S3 (or use inline code for small functions)
aws s3 cp dlq-handler.zip s3://your-bucket/lambda/dlq-handler.zip

# Note: For the template, you can also leave LambdaCodeS3Bucket empty
# and upload the code manually after stack creation
```

**Alternative:** Deploy Lambda stack without code, then update the function code manually:

```bash
# After Lambda stack is created, update function code
aws lambda update-function-code \
    --function-name jobsys-dlq-handler-dev \
    --zip-file fileb://dlq-handler.zip \
    --region $AWS_REGION
```

### Phase 3: Validate Templates

Before deploying, validate your templates:

```bash
# Validate a template
aws cloudformation validate-template \
    --template-body file://infra/cloudformation/templates/01-iam.yaml \
    --region $AWS_REGION
```

**Expected output:**
```json
{
    "Parameters": [...],
    "Description": "...",
    "Capabilities": []
}
```

**Tip:** Install `cfn-lint` for additional validation:
```bash
pip install cfn-lint
cfn-lint infra/cloudformation/templates/*.yaml
```

### Phase 3: Deploy Stack

**Option 1: Automated Deployment (Recommended)**

Use the provided deployment script that handles dependencies automatically:

```bash
cd infra/cloudformation
./deploy.sh dev
```

The script will:
- Deploy stacks in the correct order
- Handle stack outputs and cross-stack references
- Wait for each stack to complete
- Show progress and errors

**Option 2: Manual Deployment**

Deploy resources in order (IAM first, then resources that depend on IAM):

```bash
# 1. Deploy IAM roles
aws cloudformation create-stack \
    --stack-name jobsys-iam \
    --template-body file://infra/cloudformation/templates/01-iam.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $AWS_REGION

# Wait for completion
aws cloudformation wait stack-create-complete \
    --stack-name jobsys-iam \
    --region $AWS_REGION

# 2. Deploy DynamoDB
aws cloudformation create-stack \
    --stack-name jobsys-dynamodb \
    --template-body file://infra/cloudformation/templates/02-dynamodb.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-dynamodb --region $AWS_REGION

# 3. Deploy SQS
aws cloudformation create-stack \
    --stack-name jobsys-sqs \
    --template-body file://infra/cloudformation/templates/03-sqs.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-sqs --region $AWS_REGION

# 4. Deploy ECR
aws cloudformation create-stack \
    --stack-name jobsys-ecr \
    --template-body file://infra/cloudformation/templates/04-ecr.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-ecr --region $AWS_REGION

# 5. Deploy Parameter Store (requires TableName, JobsQueueUrl, DLQUrl from stack outputs — use deploy.sh or build params from describe-stacks outputs)
aws cloudformation create-stack \
    --stack-name jobsys-parameter-store \
    --template-body file://infra/cloudformation/templates/05-parameter-store.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-parameter-store --region $AWS_REGION

# 6. Deploy CloudWatch Log Groups
aws cloudformation create-stack \
    --stack-name jobsys-cloudwatch \
    --template-body file://infra/cloudformation/templates/08-cloudwatch.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-cloudwatch --region $AWS_REGION

# 7. Deploy Lambda (requires LambdaExecutionRoleArn, DLQArn, TableName from IAM/SQS/DynamoDB outputs — use deploy.sh or build params from describe-stacks outputs)
aws cloudformation create-stack \
    --stack-name jobsys-lambda \
    --template-body file://infra/cloudformation/templates/06-lambda.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-lambda --region $AWS_REGION

# 8. Deploy EC2 (optional; requires EC2InstanceProfileName, APIRepositoryURI, WorkerRepositoryURI, TableName, JobsQueueUrl, KeyPairName — use deploy.sh for full parameter wiring)
aws cloudformation create-stack \
    --stack-name jobsys-ec2 \
    --template-body file://infra/cloudformation/templates/07-ec2.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION
aws cloudformation wait stack-create-complete --stack-name jobsys-ec2 --region $AWS_REGION
```

**Why deploy in order?**
- IAM roles must exist before resources that use them
- Some resources depend on others (Lambda needs IAM role)
- Easier to debug if one stack fails

**Note:** For Parameter Store and Lambda stacks, you'll need to pass outputs from previous stacks. The automated script handles this automatically.

### Phase 4: Verify Deployment

Check stack status:

```bash
# List all stacks
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE \
    --region $AWS_REGION

# Describe a specific stack
aws cloudformation describe-stacks \
    --stack-name jobsys-dynamodb \
    --region $AWS_REGION

# View stack outputs
aws cloudformation describe-stacks \
    --stack-name jobsys-dynamodb \
    --query 'Stacks[0].Outputs' \
    --region $AWS_REGION
```

### Phase 5: Update Stack

To update infrastructure:

```bash
aws cloudformation update-stack \
    --stack-name jobsys-dynamodb \
    --template-body file://infra/cloudformation/templates/02-dynamodb.yaml \
    --parameters file://infra/cloudformation/parameters/dev.json \
    --region $AWS_REGION

# Wait for update
aws cloudformation wait stack-update-complete \
    --stack-name jobsys-dynamodb \
    --region $AWS_REGION
```

**CloudFormation is smart:**
- Only changes what's different
- Shows you a change set before applying
- Can rollback on failure

---

## 🧹 Teardown (Cleanup)

**Option 1: Automated Teardown (Recommended)**

```bash
cd infra/cloudformation
./teardown.sh dev
```

The script will:
- Delete stacks in the correct order (dependencies first)
- Wait for each deletion to complete
- Show progress and status

**Option 2: Manual Teardown**

```bash
# Delete in reverse order (dependencies first)
aws cloudformation delete-stack --stack-name jobsys-ec2 --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-lambda --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-cloudwatch --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-parameter-store --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-ecr --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-sqs --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-dynamodb --region $AWS_REGION
aws cloudformation delete-stack --stack-name jobsys-iam --region $AWS_REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name jobsys-iam --region $AWS_REGION
```

**Important:** 
- CloudFormation will delete resources in the correct order automatically
- Some resources (like DynamoDB tables) may take time to delete
- ECR repositories must be empty before deletion
- ⚠️ **This action cannot be undone!** Make sure you have backups if needed

---

## 🎯 Production Best Practices Learned

### 1. **Parameterization**
- Never hardcode values
- Use parameters for environment-specific configs
- Provide sensible defaults

### 2. **Tagging**
- Tag all resources for cost tracking
- Use consistent tag keys: `Environment`, `Project`, `Owner`
- Enables cost allocation reports

### 3. **Outputs**
- Export important values (ARNs, URLs, IDs)
- Enables cross-stack references
- Makes values discoverable

### 4. **IAM Least Privilege**
- Each resource gets minimum required permissions
- Use separate IAM roles per service
- Never use wildcard permissions in production

### 5. **Change Sets**
- Always review changes before applying
- Use change sets to preview updates
- Test in dev before prod

### 6. **Stack Organization**
- Separate stacks by resource type or lifecycle
- Use nested stacks for complex architectures
- Keep templates focused and reusable

### 7. **Version Control**
- Commit all templates to Git
- Use tags/releases for infrastructure versions
- Document changes in commit messages

### 8. **Validation**
- Validate templates before deploying
- Use linting tools (cfn-lint)
- Test in dev environment first

---

## 🔍 Understanding CloudFormation Functions

### !Ref
References another resource or parameter:

```yaml
TableName: !Ref JobsTable  # Gets the logical ID
QueueUrl: !GetAtt JobsQueue.QueueUrl  # Gets an attribute
```

### !GetAtt
Gets an attribute from a resource:

```yaml
QueueArn: !GetAtt JobsQueue.Arn
```

### !Sub
Substitutes variables in strings:

```yaml
Resource: !Sub "arn:aws:sqs:${AWS::Region}:${AWS::AccountId}:jobs-queue"
```

### !Join
Joins strings with a delimiter:

```yaml
Resource: !Join 
  - ':'
  - - 'arn:aws:sqs'
    - !Ref AWS::Region
    - !Ref AWS::AccountId
    - 'jobs-queue'
```

### Conditions
Conditional resource creation:

```yaml
Conditions:
  CreateProdResources: !Equals [!Ref Environment, prod]

Resources:
  ProdOnlyResource:
    Type: AWS::S3::Bucket
    Condition: CreateProdResources
```

---

## 📊 Monitoring and Troubleshooting

### View Stack Events

```bash
aws cloudformation describe-stack-events \
    --stack-name jobsys-dynamodb \
    --region $AWS_REGION \
    --max-items 10
```

### Common Issues

1. **Stack stuck in CREATE_IN_PROGRESS**
   - Check stack events for errors
   - Some resources take time (DynamoDB, ECR)

2. **IAM permission errors**
   - Ensure you have `CAPABILITY_NAMED_IAM` for IAM resources
   - Check your IAM user/role has CloudFormation permissions

3. **Resource already exists**
   - CloudFormation can't create resources that already exist
   - Delete existing resources or use different names

4. **Dependency errors**
   - Ensure dependent stacks are created first
   - Check outputs are exported correctly

---

## 🚀 CI/CD Pipeline: Automating Infrastructure and Application Deployment

### What is CI/CD?

**CI/CD** (Continuous Integration/Continuous Deployment) automates the process of:
- **CI (Continuous Integration)**: Automatically testing and validating code when you commit
- **CD (Continuous Deployment)**: Automatically deploying code to environments

**Why CI/CD?**
- ✅ Catch errors early (before production)
- ✅ Consistent deployments (same process every time)
- ✅ Faster releases (automated vs manual)
- ✅ Better collaboration (team sees changes immediately)
- ✅ Rollback capability (can revert bad deployments)

### How IaC and CI/CD Work Together

```
Developer commits code
        ↓
CI: Validate CloudFormation templates
        ↓
CI: Run application tests
        ↓
CD: Deploy infrastructure (if changed)
        ↓
CD: Build Docker images → Push to ECR
        ↓
CD: Deploy application to EC2/ECS
        ↓
CD: Run smoke tests
```

---

## 📋 Setting Up CI/CD with GitHub Actions

### Prerequisites

1. **GitHub Repository**: Your code must be in a GitHub repo (public or private)
   - ✅ **FREE**: GitHub Actions provides 2000 minutes/month free for private repos
   - ✅ **FREE**: Unlimited minutes for public repos

2. **AWS Credentials**: You'll need AWS access keys
   - ⚠️ **COST WARNING**: Using access keys is less secure. For production, use OIDC (see advanced section)
   - ✅ **FREE**: No cost for storing secrets in GitHub

3. **AWS Resources**: Infrastructure must be deployed first (use manual deployment or first CI/CD run)

---

## 🔧 Step 1: Configure GitHub Secrets

**What are secrets?** Encrypted values stored in GitHub (like passwords, API keys).

### Get AWS Access Keys

⚠️ **COST WARNING**: These credentials can create/modify AWS resources. Use a dedicated IAM user with limited permissions.

1. **Create IAM User for CI/CD:**
   ```bash
   # Create user
   aws iam create-user --user-name github-actions-ci
   
   # Attach policy (minimal permissions for CloudFormation)
   aws iam attach-user-policy \
       --user-name github-actions-ci \
       --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
   
   # Create access keys
   aws iam create-access-key --user-name github-actions-ci
   ```

2. **Store in GitHub:**
   - Go to your GitHub repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Add:
     - `AWS_ACCESS_KEY_ID`: Your access key ID
     - `AWS_SECRET_ACCESS_KEY`: Your secret access key

✅ **FREE**: Storing secrets in GitHub is free.

---

## 🔧 Step 2: Enable GitHub Actions

The workflow files are already created in `.github/workflows/`:

1. **infrastructure.yml** - Infrastructure CI/CD
2. **application.yml** - Application CI/CD  
3. **combined.yml** - Full pipeline (infrastructure + application)

**To enable:**
- Just commit and push the workflow files
- GitHub Actions will automatically run on the configured triggers

✅ **FREE**: GitHub Actions is free for:
- Public repos: Unlimited minutes
- Private repos: 2000 minutes/month (usually enough for small projects)

---

## 📊 Understanding the Workflows

### Workflow 1: Infrastructure CI/CD (`infrastructure.yml`)

**What it does:**
1. **On PR**: Validates CloudFormation templates
2. **On push to develop**: Deploys to dev automatically
3. **Manual trigger**: Deploy to staging/prod (requires approval)

**Jobs:**
- `validate-templates`: Validates all CloudFormation templates
- `create-change-set`: Shows what will change (for PRs)
- `deploy-dev`: Auto-deploys to dev environment
- `deploy-staging-prod`: Manual deployment with approval

**Cost:**
- ✅ **FREE**: GitHub Actions minutes (within free tier)
- ⚠️ **COST**: AWS resources created/updated (same as manual deployment)
  - DynamoDB: Free tier (25 RCU/WCU)
  - SQS: Free tier (1M requests/month)
  - ECR: Free tier (500MB storage/month)
  - Lambda: Free tier (1M requests/month)
  - EC2: Free tier (750 hours/month for t2.micro/t3.micro)

### Workflow 2: Application CI/CD (`application.yml`)

**What it does:**
1. **On PR**: Runs tests and linting
2. **On push to develop**: Builds Docker images and pushes to ECR
3. **Manual trigger**: Deploy specific service to any environment

**Jobs:**
- `build-and-test`: Runs Python tests and linting
- `build-images`: Builds and pushes Docker images to ECR
- `deploy-dev`: Deploys to dev environment
- `deploy-lambda`: Updates Lambda function code

**Cost:**
- ✅ **FREE**: GitHub Actions minutes (within free tier)
- ⚠️ **COST**: ECR storage for Docker images
  - Free tier: 500MB/month
  - After free tier: ~$0.10 per GB/month
  - Each image: ~50-200MB (depends on your app size)
  - **Estimated**: 2-4 images = ~200-800MB = **FREE** (within free tier)

### Workflow 3: Combined Pipeline (`combined.yml`)

**What it does:**
- Runs infrastructure and application deployment together
- Ensures infrastructure is deployed before application
- Runs smoke tests after deployment

**Cost:**
- Same as individual workflows combined
- ✅ **FREE**: GitHub Actions (within free tier)
- ⚠️ **COST**: AWS resources (same as manual deployment)

---

## 🚀 Using the CI/CD Pipelines

### Scenario 1: Infrastructure Change (CloudFormation Template)

**What happens:**
1. You modify a CloudFormation template
2. Push to `develop` branch or create a PR
3. CI validates the template
4. If valid and merged to `develop`, auto-deploys to dev
5. For prod, manually trigger workflow with approval

**Commands:**
```bash
# Make changes to template
vim infra/cloudformation/templates/02-dynamodb.yaml

# Commit and push
git add infra/cloudformation/templates/02-dynamodb.yaml
git commit -m "Update DynamoDB capacity"
git push origin develop
```

**Result:**
- ✅ Template validated automatically
- ✅ Deployed to dev automatically (if on develop branch)
- ⚠️ **COST**: Only if you change resource sizes (e.g., increase DynamoDB capacity)

### Scenario 2: Application Code Change

**What happens:**
1. You modify application code
2. Push to `develop` branch
3. CI runs tests
4. Builds Docker images
5. Pushes to ECR
6. Deploys to dev (if configured)

**Commands:**
```bash
# Make changes to application
vim services/svc-api/src/svc_api/api/routes.py

# Commit and push
git add services/svc-api/
git commit -m "Add new endpoint"
git push origin develop
```

**Result:**
- ✅ Tests run automatically
- ✅ Docker images built and pushed to ECR
- ⚠️ **COST**: ECR storage (usually FREE within free tier)

### Scenario 3: Manual Deployment to Production

**What happens:**
1. Go to GitHub Actions tab
2. Select workflow (e.g., "Infrastructure CI/CD")
3. Click "Run workflow"
4. Choose environment (staging/prod)
5. Requires approval (if configured)
6. Deploys after approval

**Steps:**
1. GitHub repo → Actions tab
2. Select workflow from left sidebar
3. Click "Run workflow" button
4. Select environment and branch
5. Click "Run workflow"

⚠️ **COST WARNING**: Production deployments may use larger instance sizes or more resources. Check your parameter files before deploying.

---

## 🔒 Security Best Practices

### 1. Use OIDC Instead of Access Keys (Advanced)

**Why?** More secure - no long-lived credentials.

**Setup:**
```yaml
# In workflow file, replace:
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole
    aws-region: us-east-1
```

**Benefits:**
- ✅ No access keys to manage
- ✅ Temporary credentials (auto-rotated)
- ✅ More secure

**Cost:** ✅ **FREE** - No additional cost

### 2. Branch Protection Rules

**Setup:**
1. GitHub repo → Settings → Branches
2. Add rule for `main` branch:
   - Require pull request reviews
   - Require status checks to pass
   - Require branches to be up to date

**Benefits:**
- ✅ Prevents direct pushes to main
- ✅ Requires code review
- ✅ Ensures tests pass before merge

**Cost:** ✅ **FREE**

### 3. Environment Protection

**Setup:**
1. GitHub repo → Settings → Environments
2. Create environments: `dev`, `staging`, `prod`
3. For `prod`: Require reviewers

**Benefits:**
- ✅ Manual approval required for prod
- ✅ Prevents accidental production deployments

**Cost:** ✅ **FREE**

---

## 📊 Monitoring CI/CD Pipelines

### View Pipeline Status

1. **GitHub Actions Tab:**
   - Go to your repo → Actions tab
   - See all workflow runs
   - Click on a run to see details

2. **Check Logs:**
   - Click on a job to see logs
   - Debug failed steps
   - See execution time

### Common Issues

1. **Workflow fails on validation:**
   - Check CloudFormation template syntax
   - Review error messages in logs

2. **Deployment fails:**
   - Check AWS credentials in secrets
   - Verify IAM permissions
   - Check stack events in AWS Console

3. **Tests fail:**
   - Review test output in logs
   - Fix failing tests locally first

---

## 💰 Cost Summary

### GitHub Actions (CI/CD Platform)

✅ **FREE TIER:**
- Public repos: Unlimited minutes
- Private repos: 2000 minutes/month
- Storage: 500MB (usually enough for workflows)

⚠️ **COST AFTER FREE TIER:**
- Private repos: $0.008 per minute (very cheap)
- **Estimated**: Small project = ~10-50 minutes/month = **FREE** or <$0.50/month

### AWS Resources (Deployed Infrastructure)

⚠️ **COST WARNING**: These are the same costs as manual deployment:

**Free Tier (First 12 months for new accounts):**
- EC2: t2.micro/t3.micro = 750 hours/month = **FREE**
- DynamoDB: 25GB storage, 25 RCU/WCU = **FREE**
- SQS: 1M requests/month = **FREE**
- Lambda: 1M requests, 400k GB-seconds = **FREE**
- ECR: 500MB storage = **FREE**
- CloudWatch Logs: 5GB ingestion = **FREE**

**After Free Tier:**
- EC2 t3.micro: ~$7-10/month (if running 24/7)
- DynamoDB: ~$1.25 per million reads, $1.25 per million writes
- SQS: $0.40 per million requests
- Lambda: $0.20 per million requests
- ECR: $0.10 per GB/month
- CloudWatch: $0.50 per GB ingested

**Estimated Monthly Cost (After Free Tier):**
- Small project (low traffic): **$10-20/month**
- Medium project: **$50-100/month**

### CI/CD Specific Costs

✅ **FREE:**
- GitHub Actions (within free tier)
- Workflow execution time
- Secret storage

⚠️ **COST:**
- AWS resources created by CI/CD (same as manual)
- ECR storage for Docker images (usually FREE in free tier)
- Data transfer (if pulling images frequently)

**Key Point:** CI/CD doesn't add significant cost - it just automates what you'd do manually. The main costs are the AWS resources themselves.

---

## ✅ CI/CD Success Checklist

- [ ] GitHub repository created
- [ ] AWS access keys created (IAM user with limited permissions)
- [ ] GitHub secrets configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- [ ] Workflow files committed to repo
- [ ] First infrastructure deployment successful (manual or via CI/CD)
- [ ] Branch protection rules configured (optional but recommended)
- [ ] Environment protection configured for prod (optional but recommended)
- [ ] Test PR created and validated
- [ ] Test deployment to dev successful
- [ ] Monitoring set up (check GitHub Actions tab regularly)

---

## 🎓 What You've Learned

By setting up CI/CD, you now understand:

- ✅ **CI/CD concepts**: Continuous Integration and Continuous Deployment
- ✅ **GitHub Actions**: How to automate workflows
- ✅ **Infrastructure automation**: Deploy infrastructure on code changes
- ✅ **Application automation**: Build and deploy applications automatically
- ✅ **Security**: How to securely store and use AWS credentials
- ✅ **Best practices**: Branch protection, environment approval, testing

**This is exactly how industry professionals deploy infrastructure and applications!** 🚀

---

## 🎓 Next Steps

### Advanced Topics to Explore

1. **Nested Stacks**: Organize complex infrastructure
2. **Stack Sets**: Deploy to multiple accounts/regions
3. **Custom Resources**: Extend CloudFormation with Lambda
4. **Drift Detection**: Detect manual changes
5. **Stack Policies**: Control who can update what
6. **Change Sets**: Preview changes before applying

### Alternative Tools

- **Terraform**: Multi-cloud, state management
- **AWS CDK**: Code-based (Python, TypeScript, etc.)
- **Pulumi**: Modern IaC with real programming languages

### Real-World Workflow

1. **Development**: Make changes to templates locally
2. **Validation**: Run `validate-template` and linting
3. **Testing**: Deploy to dev environment
4. **Review**: Create change set, review in PR
5. **Deployment**: Deploy to staging, then production
6. **Monitoring**: Monitor stack events and resources

---

## 📦 Template Files Created

All CloudFormation templates are located in `infra/cloudformation/templates/`:

- `01-iam.yaml` - IAM roles and policies
- `02-dynamodb.yaml` - DynamoDB table
- `03-sqs.yaml` - SQS queues
- `04-ecr.yaml` - ECR repositories
- `05-parameter-store.yaml` - Parameter Store configuration
- `06-lambda.yaml` - Lambda function
- `07-ec2.yaml` - EC2 instance (optional)
- `08-cloudwatch.yaml` - CloudWatch log groups

Parameter files in `infra/cloudformation/parameters/`:
- `dev.json` - Development environment parameters
- `prod.json` - Production environment parameters

Deployment scripts:
- `deploy.sh` - Automated deployment script
- `teardown.sh` - Cleanup script

## ✅ Success Checklist

### Infrastructure Deployment
- [ ] All templates created and validated
- [ ] Lambda code packaged (if deploying Lambda)
- [ ] IAM stack deployed successfully
- [ ] DynamoDB stack deployed successfully
- [ ] SQS stacks deployed successfully
- [ ] ECR repositories created
- [ ] Parameter Store parameters set
- [ ] CloudWatch log groups created
- [ ] Lambda function deployed (with code)
- [ ] EC2 instance deployed (optional)
- [ ] All outputs verified
- [ ] Resources tagged correctly
- [ ] Stack events reviewed (no errors)
- [ ] Teardown tested successfully

### CI/CD Setup
- [ ] GitHub repository created
- [ ] AWS access keys created (IAM user with limited permissions)
- [ ] GitHub secrets configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- [ ] Workflow files committed to repo
- [ ] First infrastructure deployment successful (manual or via CI/CD)
- [ ] Branch protection rules configured (optional but recommended)
- [ ] Environment protection configured for prod (optional but recommended)
- [ ] Test PR created and validated
- [ ] Test deployment to dev successful
- [ ] Monitoring set up (check GitHub Actions tab regularly)

**Congratulations!** You've learned production-grade Infrastructure as Code! 🎉

You now understand:
- ✅ What IaC is and why it matters
- ✅ How CloudFormation works
- ✅ Production best practices
- ✅ How to organize and deploy infrastructure
- ✅ How to manage infrastructure changes

This is exactly how industry professionals deploy and manage cloud infrastructure!


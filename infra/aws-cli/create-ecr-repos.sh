#!/bin/bash
# Create ECR repositories for services

set -e

REGION="${AWS_REGION:-us-east-1}"
REPOS=("svc-api" "svc-worker")

echo "Creating ECR repositories in region: $REGION"

for repo in "${REPOS[@]}"; do
    echo "Creating repository: $repo"
    
    # Check if repo already exists
    if aws ecr describe-repositories \
        --repository-names "$repo" \
        --region "$REGION" \
        >/dev/null 2>&1; then
        echo "Repository $repo already exists, skipping..."
    else
        aws ecr create-repository \
            --repository-name "$repo" \
            --region "$REGION" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        
        echo "✅ Repository $repo created"
    fi
    
    # Get repository URI
    REPO_URI=$(aws ecr describe-repositories \
        --repository-names "$repo" \
        --region "$REGION" \
        --query 'repositories[0].repositoryUri' \
        --output text)
    
    echo "   Repository URI: $REPO_URI"
done

echo "✅ All ECR repositories created successfully!"


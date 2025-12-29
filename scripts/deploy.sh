#!/bin/bash
# Deployment script for Kubernetes

set -e

NAMESPACE="jobsys"
ECR_ACCOUNT="${ECR_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"
REGION="${AWS_REGION:-us-east-1}"

echo "Deploying to Kubernetes namespace: $NAMESPACE"

# Replace ECR account in deployment files
find k8s/base -name "*.yaml" -type f -exec sed -i "s/<ECR_ACCOUNT>/$ECR_ACCOUNT/g" {} \;

# Apply namespace
kubectl apply -f k8s/base/namespace.yaml

# Apply ConfigMaps
kubectl apply -f k8s/base/svc-api/configmap.yaml
kubectl apply -f k8s/base/svc-worker/configmap.yaml

# Apply Deployments
kubectl apply -f k8s/base/svc-api/deployment.yaml
kubectl apply -f k8s/base/svc-worker/deployment.yaml

# Apply Services
kubectl apply -f k8s/base/svc-api/service.yaml

echo "✅ Deployment complete!"
echo ""
echo "To check status:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -f deployment/svc-api -n $NAMESPACE"
echo "  kubectl logs -f deployment/svc-worker -n $NAMESPACE"


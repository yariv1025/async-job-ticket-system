#!/bin/bash
# Deployment script for Kubernetes (LOCAL ONLY - for learning/development)

set -e

NAMESPACE="jobsys"
ECR_ACCOUNT="${ECR_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "local")}"
REGION="${AWS_REGION:-us-east-1}"

echo "🚀 Deploying to Kubernetes (LOCAL CLUSTER)"
echo "   This is for local development/learning only!"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl is not installed"
    echo "   Install kubectl or use a local cluster (minikube, kind, k3d)"
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ Error: Cannot connect to Kubernetes cluster"
    echo "   Make sure your local cluster is running (minikube start, kind create cluster, etc.)"
    exit 1
fi

echo "Cluster: $(kubectl config current-context)"
echo ""

# Replace ECR account in deployment files (use local images if ECR not available)
if [ "$ECR_ACCOUNT" != "local" ]; then
    echo "Using ECR images: $ECR_ACCOUNT"
    find k8s/base -name "*.yaml" -type f -exec sed -i.bak "s/<ECR_ACCOUNT>/$ECR_ACCOUNT/g" {} \;
    find k8s/base -name "*.yaml.bak" -delete
else
    echo "⚠️  Using local images (ECR not configured)"
    echo "   Make sure to build images locally: docker build -t svc-api:latest services/svc-api/"
    find k8s/base -name "*.yaml" -type f -exec sed -i.bak "s/<ECR_ACCOUNT>.dkr.ecr.*amazonaws.com\/svc-api:latest/svc-api:latest/g" {} \;
    find k8s/base -name "*.yaml" -type f -exec sed -i.bak "s/<ECR_ACCOUNT>.dkr.ecr.*amazonaws.com\/svc-worker:latest/svc-worker:latest/g" {} \;
    find k8s/base -name "*.yaml.bak" -delete
fi

# Apply namespace
echo "Creating namespace..."
kubectl apply -f k8s/base/namespace.yaml

# Apply ConfigMaps
echo "Creating ConfigMaps..."
kubectl apply -f k8s/base/svc-api/configmap.yaml
kubectl apply -f k8s/base/svc-worker/configmap.yaml

# Apply Deployments
echo "Creating Deployments..."
kubectl apply -f k8s/base/svc-api/deployment.yaml
kubectl apply -f k8s/base/svc-worker/deployment.yaml

# Apply Services
echo "Creating Services..."
kubectl apply -f k8s/base/svc-api/service.yaml

echo ""
echo "✅ Kubernetes deployment complete!"
echo ""
echo "To check status:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -f deployment/svc-api -n $NAMESPACE"
echo "  kubectl logs -f deployment/svc-worker -n $NAMESPACE"
echo ""
echo "To port-forward API:"
echo "  kubectl port-forward svc/svc-api 8080:8080 -n $NAMESPACE"


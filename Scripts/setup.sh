#!/bin/bash
set -euo pipefail

CLUSTER_NAME="${1:-eks-platform-dev}"
REGION="${2:-ap-south-1}"

echo "=== EKS Platform Bootstrap ==="
echo "Cluster: $CLUSTER_NAME | Region: $REGION"

# Update kubeconfig
echo "[1/5] Updating kubeconfig..."
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

# Install ArgoCD
echo "[2/5] Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

# Apply ArgoCD Applications
echo "[3/5] Applying ArgoCD Applications..."
kubectl apply -f kubernetes/argocd/applications/

# Install Metrics Server
echo "[4/5] Installing Metrics Server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify
echo "[5/5] Verifying cluster..."
kubectl get nodes
kubectl get pods -n argocd
kubectl get pods -n monitoring

ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
echo ""
echo "=== Setup Complete ==="
echo "ArgoCD admin password: $ARGOCD_PWD"
echo "Run: kubectl port-forward svc/argocd-server -n argocd 8080:443"
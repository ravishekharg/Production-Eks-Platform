```markdown
# Production EKS Platform on AWS

A production-grade Kubernetes platform built on AWS EKS with full GitOps, 
observability, and security automation. Demonstrates real-world cloud architecture 
patterns used in enterprise environments.

## Architecture

[Add architecture diagram — use draw.io or Excalidraw and export as PNG]

- Multi-AZ VPC with public/private subnets
- EKS 1.30 with managed node groups
- ArgoCD for GitOps continuous delivery
- kube-prometheus-stack for full observability
- Sealed Secrets for secure secret management
- GitHub Actions for IaC CI/CD with OIDC authentication

## Tech Stack

| Layer | Tool |
|-------|------|
| Cloud | AWS (EKS, VPC, IAM, ECR, S3) |
| IaC | Terraform 1.7 |
| Orchestration | Kubernetes 1.30 / EKS |
| GitOps | ArgoCD |
| Monitoring | Prometheus + Grafana |
| Secrets | Sealed Secrets |
| CI/CD | GitHub Actions (OIDC) |
| Language | Python (Flask, boto3) |

## Quick Start

```bash
# 1. Provision infrastructure
cd terraform/environments/dev
terraform init && terraform apply

# 2. Bootstrap cluster
chmod +x scripts/setup.sh
./scripts/setup.sh eks-platform-dev ap-south-1

# 3. Run cost optimizer
pip install boto3
python scripts/cost_optimizer.py --region ap-south-1
```

## Cost Optimizer Output Example

```
AWS COST OPTIMIZATION REPORT
Account : 123456789012   Region: ap-south-1
❗ EC2 (t3.medium)  — Idle avg CPU 1.2% — Saving: $50.00/month
❗ EBS gp3 (100GB)  — Unattached      — Saving: $8.00/month
💰 Total estimated monthly savings: $58.00
```

## Key Outcomes Demonstrated
- Zero-downtime rolling deployments via ArgoCD
- Infrastructure-as-Code with remote state and locking
- Automated cost visibility using Python + boto3
- Production security: non-root containers, IRSA, OIDC auth
```

---

## Commit & Push

```bash
git init
git add .
git commit -m "feat: production EKS platform with GitOps and cost optimizer"
git remote add origin https://github.com/YOUR_USERNAME/production-eks-platform.git
git push -u origin main
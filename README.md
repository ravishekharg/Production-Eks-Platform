# Production EKS Platform on AWS

A production-grade Kubernetes platform built on AWS EKS with GitOps delivery,
observability, and IAM-based security automation. Demonstrates real-world
cloud architecture patterns used in enterprise environments.

## Architecture

- Multi-AZ VPC with public and private subnets, one NAT gateway per AZ
- EKS 1.30 cluster with a managed node group (private subnets only)
- IAM Roles for Service Accounts (IRSA) via an OIDC provider, for the ALB
  Controller, Cluster Autoscaler, and External DNS
- ArgoCD for GitOps continuous delivery of cluster add-ons and the sample app
- kube-prometheus-stack (Prometheus, Alertmanager, Grafana) for observability
- Sealed Secrets for encrypted-at-rest secret management in Git
- GitHub Actions for Terraform CI/CD using OIDC (no long-lived AWS keys)
- A sample Flask app deployed behind an ALB Ingress, with an HPA and a
  default-deny-style NetworkPolicy

```
Internet
   │
   ▼
ALB (Ingress) ──► sample-app Service ──► sample-app Pods (EKS, private subnets)
                                              │
                                              ├─ ArgoCD (GitOps sync)
                                              ├─ Prometheus / Grafana (metrics)
                                              └─ Sealed Secrets (secret decryption)
```

## Repository Structure

```
Terraform/
  backend.tf                  # One-time bootstrap: S3 state bucket + DynamoDB lock table
  Modules/
    vpc/                      # VPC, subnets, NAT/IGW, route tables
    eks/                      # EKS cluster, managed node group, OIDC provider
    iam/                      # IRSA roles for ALB Controller, Cluster Autoscaler, External DNS
  Environments/
    dev/                      # Dev environment root module (terraform.tfvars, main.tf)
    prod/                     # Prod environment root module (adds S3 backup bucket)

Kubernetes/
  argocd/applications/        # ArgoCD Application manifests (monitoring, sealed-secrets)
  monitoring/                 # Custom Helm values for kube-prometheus-stack

Apps/sample-app/
  app.py, Dockerfile          # Sample Flask service
  k8s/                        # Deployment, Service, Ingress, HPA, NetworkPolicy

Scripts/
  setup.sh                    # Post-provision cluster bootstrap (ArgoCD, metrics-server)
  cost_optimizer.py           # boto3-based idle-resource / cost audit report

.github/workflows/
  terraform-plan.yaml         # fmt/validate/tflint/plan on PRs, via OIDC
  terraform-apply.yaml        # terraform apply on merge to main, via OIDC
```

## Prerequisites

- Terraform >= 1.6
- AWS CLI v2, configured with credentials for the target account
- kubectl
- An AWS account with permissions to create VPC/EKS/IAM resources
- (Recommended) `tflint` for local linting, matching CI

## Setup and Deploy

1. **Bootstrap remote state** (once per AWS account):

   ```bash
   terraform -chdir=Terraform apply -target=aws_s3_bucket.terraform_state \
     -target=aws_s3_bucket_versioning.terraform_state \
     -target=aws_s3_bucket_server_side_encryption_configuration.terraform_state \
     -target=aws_s3_bucket_public_access_block.terraform_state \
     -target=aws_dynamodb_table.terraform_locks
   ```

   Then uncomment and fill in the `backend "s3"` block in
   `Terraform/Environments/<env>/main.tf` with the bucket/table this creates,
   and update `terraform.tfvars` for the environment (region, project name).

2. **Provision infrastructure:**

   ```bash
   cd Terraform/Environments/dev
   terraform init
   terraform apply
   ```

3. **Bootstrap the cluster** (ArgoCD, metrics-server, ArgoCD Applications):

   ```bash
   chmod +x Scripts/setup.sh
   ./Scripts/setup.sh eks-platform-dev ap-south-1
   ```

4. **Deploy the sample app** (or let ArgoCD manage it via a GitOps
   Application pointing at `Apps/sample-app/k8s/`):

   ```bash
   kubectl apply -f Apps/sample-app/k8s/
   ```

5. **Run the cost optimizer** (requires AWS credentials with read access to
   EC2/CloudWatch):

   ```bash
   pip install boto3
   python Scripts/cost_optimizer.py --region ap-south-1
   ```

## CI/CD

`.github/workflows/terraform-plan.yaml` runs `terraform fmt -check`,
`terraform validate`, and `tflint` on every PR touching `Terraform/**`, then
posts the plan as a PR comment. `.github/workflows/terraform-apply.yaml`
applies on merge to `main`. Both authenticate to AWS via GitHub OIDC
(`role-to-assume: ${{ secrets.AWS_ROLE_ARN }}`) — no static AWS keys are
stored in the repo or in GitHub Secrets.

## Security Notes

- Terraform state is stored in an S3 bucket with versioning, KMS encryption,
  and public access blocked, plus DynamoDB state locking.
- Node groups run in private subnets only; the EKS control plane has both
  private and public endpoint access enabled by default in
  `Terraform/Modules/eks/main.tf` — restrict `public_access_cidrs` (or set
  `endpoint_public_access = false`) for real production use.
- Sample app containers run as a non-root user, drop all Linux capabilities,
  and disallow privilege escalation.
- Secrets are never committed in plaintext; use Sealed Secrets for any
  cluster secret material, and see `.gitignore` for excluded credential
  file patterns.

## Key Outcomes Demonstrated

- Zero-downtime rolling deployments via ArgoCD
- Infrastructure-as-Code with remote state and locking
- Automated cost visibility using Python + boto3
- Production security: non-root containers, IRSA, OIDC-based CI/CD auth

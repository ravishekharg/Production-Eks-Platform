# -*- coding: utf-8 -*-
"""Generates Darviq_Eks_High_Level_Design.docx from the docx_builder helper.
Run from the Docs/ directory: python gen_hld.py
"""
from docx_builder import DesignDoc

VERSION = "1.0"
DATE = "July 31, 2026"

doc = DesignDoc(
    project_name="Darviq Eks",
    subtitle="Production-Style AWS EKS Platform on Terraform and Kubernetes",
    doc_kind="High-Level Design (HLD)",
    version=VERSION,
    date=DATE,
)
doc.add_document_control()
doc.add_toc_field()

# ---------------------------------------------------------------------------
# 1. Introduction
# ---------------------------------------------------------------------------
doc.add_heading1("1. Introduction")

doc.add_heading2("1.1 Purpose")
doc.add_paragraph(
    "This document describes the high-level design of Darviq Eks, a "
    "production-style Amazon EKS (Elastic Kubernetes Service) platform "
    "provisioned entirely with Terraform and operated with a GitOps "
    "delivery model. It explains the platform's architecture, the "
    "responsibilities of each infrastructure and application component, "
    "the end-to-end path from a Terraform change to a running workload, "
    "and the security and operational posture the platform demonstrates. "
    "The document is intended to give a reader who has not seen the repository "
    "a clear picture of what the platform actually provisions and how the "
    "pieces fit together, before drilling into implementation detail in the "
    "companion Low-Level Design (LLD) document."
)

doc.add_heading2("1.2 Scope")
doc.add_paragraph("In scope for this document:")
doc.add_bullets([
    "The Terraform modules and root (environment) configurations under Terraform/ "
    "that provision the VPC, the EKS cluster and its managed node group, and the "
    "IAM roles used for IRSA (IAM Roles for Service Accounts).",
    "The Kubernetes-layer add-ons managed via ArgoCD (kube-prometheus-stack, "
    "Sealed Secrets) and the one sample workload (Apps/sample-app) that "
    "demonstrates a realistic application deployment on the platform.",
    "The GitHub Actions CI/CD workflows that plan and apply Terraform changes.",
    "The supporting operational scripts (cluster bootstrap, cost-optimization "
    "audit).",
    "The security model as actually implemented: IAM policies, security-group "
    "and subnet segmentation, Kubernetes NetworkPolicy, and pod security context.",
])
doc.add_paragraph("Out of scope for this document:")
doc.add_bullets([
    "Any application business logic beyond the minimal Flask sample used to "
    "exercise the platform (Apps/sample-app is a smoke-test workload, not a "
    "product).",
    "Multi-cluster or multi-region topologies — this platform provisions a "
    "single cluster per environment (dev, prod).",
    "Cost or usage figures for a live AWS account — the platform has not been "
    "kept running continuously; the cost-optimizer script is described as a "
    "capability, not as a report against real billing data.",
    "Detailed Helm chart internals for third-party charts (kube-prometheus-stack, "
    "Sealed Secrets) beyond the values this repository overrides.",
])

doc.add_heading2("1.3 Intended audience")
doc.add_bullets([
    "Reviewers assessing this repository as part of the Darviq Systems "
    "portfolio (recruiters, engineering reviewers).",
    "Engineers who want to reuse or extend the Terraform modules or the "
    "GitOps layout for their own EKS environment.",
    "The repository owner, as a record of the design intent behind the code.",
])

doc.add_heading2("1.4 Definitions & abbreviations")
doc.add_table(
    headers=["Term", "Definition"],
    rows=[
        ["EKS", "Amazon Elastic Kubernetes Service — AWS's managed Kubernetes control plane."],
        ["VPC", "Virtual Private Cloud — an isolated network within AWS."],
        ["IRSA", "IAM Roles for Service Accounts — lets a Kubernetes ServiceAccount assume a scoped AWS IAM role via OIDC federation, without static credentials."],
        ["OIDC", "OpenID Connect — the federated-identity protocol EKS exposes and that GitHub Actions and IRSA both use to authenticate to AWS without long-lived keys."],
        ["ALB", "Application Load Balancer — the AWS load balancer type provisioned by the AWS Load Balancer Controller for Kubernetes Ingress resources."],
        ["HPA", "Horizontal Pod Autoscaler — scales pod replica count based on observed metrics such as CPU/memory utilization."],
        ["GitOps", "An operating model where the desired cluster state is declared in Git and a controller (ArgoCD) continuously reconciles the live cluster to match it."],
        ["ArgoCD", "The GitOps continuous-delivery controller used in this repository to sync Helm-chart-based Applications into the cluster."],
        ["NAT Gateway", "Managed AWS service that lets resources in private subnets reach the internet outbound without being publicly reachable inbound."],
        ["Sealed Secrets", "A Bitnami controller that lets Kubernetes Secret manifests be encrypted and safely committed to Git; only the in-cluster controller can decrypt them."],
        ["tflint", "A Terraform-specific linter run in CI in addition to terraform fmt/validate."],
        ["State locking", "A DynamoDB-backed mechanism preventing two concurrent Terraform runs from corrupting the same state file."],
    ],
)

# ---------------------------------------------------------------------------
# 2. System overview
# ---------------------------------------------------------------------------
doc.add_heading1("2. System overview")

doc.add_heading2("2.1 Problem statement")
doc.add_paragraph(
    "Running Kubernetes on AWS in a way that reflects real production practice "
    "requires more than a single 'create cluster' call: it requires a "
    "segmented network, least-privilege IAM boundaries scoped per workload "
    "rather than per node, a repeatable and auditable provisioning process, and "
    "a GitOps-based delivery mechanism so that what's running in the cluster "
    "matches what's declared in source control. Darviq Eks exists to "
    "demonstrate that pattern end-to-end, at a scale small enough to run and "
    "review in a portfolio context, but structured the way a production "
    "platform would be: modular Terraform, environment-specific root modules, "
    "IRSA instead of node-wide IAM, GitOps add-on delivery, and CI/CD that "
    "authenticates to AWS without storing static credentials."
)

doc.add_heading2("2.2 Proposed solution summary")
doc.add_paragraph(
    "The platform is provisioned by three composable Terraform modules — "
    "vpc, eks, and iam — instantiated from two environment root modules "
    "(Terraform/Environments/dev and .../prod) that differ only in sizing "
    "(CIDR ranges, number of AZs, instance types, node counts) and in which "
    "modules they call. GitHub Actions runs terraform fmt/validate/tflint and "
    "posts a plan on every pull request touching Terraform/**, then applies "
    "on merge to main, authenticating via GitHub's OIDC provider so no AWS "
    "access keys are stored as GitHub Secrets. Once the cluster exists, "
    "Scripts/setup.sh bootstraps ArgoCD and the metrics-server and applies the "
    "ArgoCD Application manifests under Kubernetes/argocd/applications/, which "
    "in turn pull in kube-prometheus-stack (observability) and Sealed Secrets "
    "(encrypted-at-rest secret management) from their upstream Helm "
    "repositories. A single sample Flask application under Apps/sample-app "
    "demonstrates the workload-facing pieces: an ALB-backed Ingress, an HPA, "
    "a default-deny-style NetworkPolicy, and a non-root/no-capabilities "
    "container security posture."
)

# ---------------------------------------------------------------------------
# 3. Architecture overview
# ---------------------------------------------------------------------------
doc.add_heading1("3. Architecture overview")

doc.add_table(
    headers=["Component", "Responsibility", "Technology"],
    rows=[
        ["VPC & networking", "Isolated network with public and private subnets across multiple AZs, one NAT Gateway per public subnet, and route tables that send private-subnet egress through NAT.", "Terraform (Terraform/Modules/vpc)"],
        ["EKS control plane", "Managed Kubernetes API server/control plane; hosts the OIDC issuer used for IRSA; logs api/audit/authenticator/controllerManager/scheduler to CloudWatch.", "Terraform (Terraform/Modules/eks), Amazon EKS 1.30"],
        ["Managed node group", "One EC2-backed, on-demand managed node group per environment running in private subnets only, with a configurable min/desired/max size.", "Terraform (Terraform/Modules/eks), EC2"],
        ["IRSA IAM roles", "Scoped IAM roles federated to specific kube-system ServiceAccounts (ALB Controller, Cluster Autoscaler, External DNS) via the cluster's OIDC provider.", "Terraform (Terraform/Modules/iam)"],
        ["Remote state backend", "One-time-bootstrapped S3 bucket (versioned, KMS-encrypted, public access blocked) and DynamoDB lock table for Terraform state.", "Terraform (Terraform/backend.tf), S3, DynamoDB"],
        ["GitOps delivery", "Declarative Application manifests that ArgoCD continuously reconciles against the live cluster (auto-prune, self-heal).", "ArgoCD (Kubernetes/argocd/applications/)"],
        ["Observability stack", "Metrics collection, alerting, and dashboards for the cluster and workloads.", "kube-prometheus-stack (Prometheus, Alertmanager, Grafana) via ArgoCD"],
        ["Secret management", "Encrypts Kubernetes Secret manifests so they can be committed to Git; only the in-cluster controller decrypts them.", "Sealed Secrets via ArgoCD"],
        ["Sample workload", "Minimal Flask service used to exercise Ingress/ALB, HPA, NetworkPolicy, and pod-security settings.", "Flask + Gunicorn, Docker, Kubernetes manifests (Apps/sample-app)"],
        ["CI/CD", "Formats/validates/lints Terraform and posts plan output on PRs; applies to each environment on merge to main via OIDC, with optional manual approval gates for prod.", "GitHub Actions (.github/workflows/)"],
        ["Cost visibility", "Scans a region for idle EC2 instances, unattached EBS volumes, and unassociated Elastic IPs and estimates monthly savings.", "Python + boto3 (Scripts/cost_optimizer.py)"],
    ],
)

doc.add_heading2("3.1 Component descriptions")
doc.add_paragraph(
    "VPC & networking. The vpc module (Terraform/Modules/vpc/main.tf) creates "
    "one aws_vpc, one Internet Gateway, and a variable-length list of public "
    "and private subnets — one pair per availability zone supplied by the "
    "caller. Each public subnet gets its own Elastic IP and NAT Gateway; each "
    "private subnet gets its own route table routed to that AZ's NAT Gateway, "
    "rather than sharing a single NAT Gateway across AZs. Public subnets are "
    "tagged kubernetes.io/role/elb=1 and private subnets kubernetes.io/role/"
    "internal-elb=1 and karpenter.sh/discovery=<cluster_name>, which is how "
    "the AWS Load Balancer Controller and (if ever added) Karpenter would "
    "auto-discover the correct subnets."
)
doc.add_paragraph(
    "EKS control plane and node group. The eks module (Terraform/Modules/eks/"
    "main.tf) creates the aws_eks_cluster with both private and public API "
    "endpoint access enabled, cluster logging turned on for all five log "
    "types, and a single aws_eks_node_group of on-demand instances placed in "
    "the private subnets. It also stands up the IAM OIDC identity provider "
    "for the cluster (via a tls_certificate data source against the issuer "
    "URL), which is the trust anchor every IRSA role in the iam module relies "
    "on."
)
doc.add_paragraph(
    "IRSA IAM roles. The iam module (Terraform/Modules/iam/main.tf) creates "
    "three roles, each trusting the cluster's OIDC provider and scoped by an "
    "sts:AssumeRoleWithWebIdentity condition to one specific kube-system "
    "ServiceAccount: aws-load-balancer-controller (policy imported from "
    "policies/alb-controller-policy.json, the upstream AWS-published policy), "
    "cluster-autoscaler (an inline policy scoped to the "
    "autoscaling:*/ec2:Describe*/eks:DescribeNodegroup actions the autoscaler "
    "needs), and external-dns (an inline policy scoped to Route 53 "
    "ChangeResourceRecordSets/ListHostedZones/ListResourceRecordSets). Note "
    "that the module's own header comment also mentions Karpenter, and the "
    "vpc module tags private subnets for karpenter.sh/discovery, but no "
    "Karpenter IAM role or controller resources are actually defined anywhere "
    "in this repository at present — it is a forward-looking hook, not an "
    "implemented feature (see Section 12)."
)
doc.add_paragraph(
    "GitOps delivery and add-ons. Two ArgoCD Application manifests exist "
    "under Kubernetes/argocd/applications/: kube-prometheus-stack (pointed at "
    "the Prometheus community Helm repo, pinned to chart version 58.1.3, with "
    "custom values from Kubernetes/monitoring/prometheus-values.yaml) and "
    "sealed-secrets (pointed at the Bitnami Labs Helm repo, pinned to 2.15.0). "
    "Both use automated sync with prune and self-heal enabled, so drift "
    "between the Git-declared state and the live cluster is corrected "
    "automatically. ArgoCD itself, however, is installed imperatively by "
    "Scripts/setup.sh via the upstream install.yaml manifest — it is not "
    "provisioned by Terraform or GitOps'd into place itself, which is a "
    "reasonable and common bootstrap pattern (you cannot GitOps-sync the "
    "GitOps controller with itself before it exists) but is worth being "
    "explicit about."
)
doc.add_paragraph(
    "Sample workload. Apps/sample-app is a small Flask application (/, "
    "/health, /ready) served by Gunicorn in a non-root, capability-dropped "
    "container. Its Kubernetes manifests (Apps/sample-app/k8s/) show the "
    "full set of production-style workload concerns this platform is meant "
    "to demonstrate: a Deployment with pod anti-affinity and a zero-downtime "
    "rolling-update strategy, a ClusterIP Service, an ALB-class Ingress with "
    "health-check and SSL-redirect annotations, an HPA scaling on CPU and "
    "memory utilization with distinct scale-up/scale-down behavior windows, "
    "and a default-deny-style NetworkPolicy restricting both ingress and "
    "egress traffic."
)
doc.add_paragraph(
    "CI/CD. Two GitHub Actions workflows drive the Terraform lifecycle: "
    "terraform-plan.yaml runs on every pull request touching Terraform/**, "
    "matrixed over the dev and prod environments, running fmt -check, init, "
    "validate, tflint, and plan, then posting the plan output as a PR "
    "comment. terraform-apply.yaml runs on push to main (same path filter), "
    "re-runs fmt/init/validate/plan and then applies, updates the local "
    "kubeconfig, and runs kubectl get nodes as a smoke check. Both workflows "
    "authenticate to AWS purely via GitHub's OIDC provider and an assumed IAM "
    "role (secrets.AWS_ROLE_ARN) — no static AWS access keys are stored in "
    "the repository or in GitHub Secrets. The apply workflow also uses "
    "GitHub Environments (environment: ${{ matrix.environment }}) so that, "
    "if configured with required reviewers on the prod environment, applies "
    "to prod pause for manual approval."
)

# ---------------------------------------------------------------------------
# 4. End-to-end functional workflow
# ---------------------------------------------------------------------------
doc.add_heading1("4. End-to-end functional workflow")
doc.add_figure_placeholder(
    "Figure 4.1 — Commit-to-running-workload flow: PR opened -> terraform-plan "
    "workflow (fmt/validate/tflint/plan, OIDC auth, plan posted to PR) -> "
    "merge to main -> terraform-apply workflow (plan/apply, OIDC auth, "
    "kubeconfig update, node verification) -> cluster infrastructure updated "
    "-> ArgoCD (already running, bootstrapped once via Scripts/setup.sh) "
    "detects any changed Application source and reconciles kube-prometheus-"
    "stack / Sealed Secrets / the sample app into the cluster."
)
doc.add_paragraph(
    "The platform has two independent reconciliation loops that together "
    "take a change from a developer's commit to a running effect in the "
    "cluster. The first loop governs infrastructure: a change under "
    "Terraform/** opens a PR, CI plans it and posts the plan for review, and "
    "merging to main triggers an apply against the target environment(s). "
    "The second loop governs workloads and add-ons: once the cluster and "
    "ArgoCD exist, any change to an ArgoCD Application's source (a Helm chart "
    "version bump, a values file edit, or — if wired up — a change to the "
    "sample app's manifests) is picked up by ArgoCD's automated sync with "
    "self-heal, so the live cluster state converges back to what's declared "
    "in Git without a human running kubectl apply by hand. The sample app "
    "itself can be applied either loop-agnostically with a direct kubectl "
    "apply -f Apps/sample-app/k8s/, or GitOps-managed if an ArgoCD Application "
    "pointing at that path is added (the README documents this as the "
    "intended pattern, though no such Application manifest ships in the repo "
    "today — only the monitoring and sealed-secrets Applications do)."
)

doc.add_table(
    headers=["Stage", "Trigger", "What runs"],
    rows=[
        ["1. Plan", "Pull request touching Terraform/**", "terraform fmt -check, init, validate, tflint, plan; plan output posted as a PR comment (per environment, dev and prod, in parallel)."],
        ["2. Review", "Human", "Reviewer reads the posted plan diff before approving/merging."],
        ["3. Apply", "Push/merge to main touching Terraform/**", "terraform fmt -check, init, validate, plan, apply against each environment (max-parallel: 1, so dev and prod are not applied concurrently); optional manual approval gate on the prod GitHub Environment."],
        ["4. Cluster verification", "End of apply job", "aws eks update-kubeconfig, then kubectl get nodes to confirm the node group is Ready."],
        ["5. Cluster bootstrap", "One-time, manual", "Scripts/setup.sh installs ArgoCD, applies the ArgoCD Application manifests, installs metrics-server, and prints the initial ArgoCD admin password."],
        ["6. GitOps reconciliation", "Continuous, automated", "ArgoCD syncs kube-prometheus-stack and Sealed Secrets from their upstream Helm repos with prune+selfHeal; drift is corrected automatically."],
        ["7. Workload deploy", "Manual or GitOps", "kubectl apply -f Apps/sample-app/k8s/, or an ArgoCD Application pointed at that path."],
    ],
)

# ---------------------------------------------------------------------------
# 5. Module-wise design overview
# ---------------------------------------------------------------------------
doc.add_heading1("5. Module-wise design overview")

doc.add_heading2("5.1 VPC / networking module (Terraform/Modules/vpc)")
doc.add_paragraph(
    "Provisions the network foundation: one VPC, one Internet Gateway, N "
    "public and N private subnets (N = number of AZs passed in), one NAT "
    "Gateway per public subnet (not a single shared NAT Gateway), and "
    "per-AZ private route tables so each AZ's private subnet egresses "
    "through its own AZ-local NAT Gateway. Inputs are entirely "
    "parameterized (CIDR blocks, AZ list, project/cluster name for tagging) "
    "so dev and prod call the same module with different sizing. Subnet "
    "tags carry the Kubernetes/AWS discovery conventions "
    "(kubernetes.io/role/elb, kubernetes.io/role/internal-elb, "
    "karpenter.sh/discovery) that downstream controllers rely on."
)

doc.add_heading2("5.2 EKS cluster & node-group module (Terraform/Modules/eks)")
doc.add_paragraph(
    "Provisions the aws_eks_cluster (control plane), its dedicated cluster "
    "IAM role (AmazonEKSClusterPolicy + AmazonEKSVPCResourceController), one "
    "aws_eks_node_group with its own node IAM role "
    "(AmazonEKSWorkerNodePolicy + AmazonEKS_CNI_Policy + "
    "AmazonEC2ContainerRegistryReadOnly), and the IAM OIDC provider used for "
    "IRSA. Node group sizing (instance types, desired/min/max) and the "
    "Kubernetes version (default 1.30) are all module inputs. The node group "
    "is deliberately confined to private subnets only, and its update "
    "strategy allows at most one node unavailable at a time during a node "
    "group version/config rollout."
)

doc.add_heading2("5.3 IAM / IRSA module (Terraform/Modules/iam)")
doc.add_paragraph(
    "Provisions IRSA roles for three cluster add-ons — the AWS Load Balancer "
    "Controller, Cluster Autoscaler, and External DNS — each trust-scoped to "
    "one exact kube-system ServiceAccount via the OIDC provider's audience "
    "and subject claims. This module is only invoked from the prod "
    "environment root module today (Terraform/Environments/prod/main.tf); "
    "the dev environment root module does not call it, so dev provisions a "
    "cluster and node group without these IRSA roles unless a future change "
    "adds the module call there too (see Section 11)."
)

doc.add_heading2("5.4 Environment root modules (Terraform/Environments/dev, /prod)")
doc.add_paragraph(
    "Each environment is a self-contained Terraform root module that wires "
    "the vpc and eks (and, for prod, iam) modules together with "
    "environment-specific sizing: dev uses a /16 VPC with 2 AZs and "
    "t3.medium nodes (desired 2, max 4); prod uses a separate /16 CIDR "
    "range with 3 AZs and m5.large nodes (desired 3, min 3, max 10). Prod "
    "additionally provisions a versioned, KMS-encrypted S3 bucket for "
    "backups. Both environments currently have their S3 backend block "
    "commented out — state is local by default until the one-time "
    "Terraform/backend.tf bootstrap has been run and the backend block "
    "manually uncommented and filled in per the README's setup instructions."
)

doc.add_heading2("5.5 GitOps / Kubernetes add-ons (Kubernetes/argocd, Kubernetes/monitoring)")
doc.add_paragraph(
    "Declares the desired add-on state as ArgoCD Application custom "
    "resources: kube-prometheus-stack (observability) and sealed-secrets "
    "(secret encryption), both with automated, self-healing sync. The "
    "Prometheus stack's behavior is customized via "
    "Kubernetes/monitoring/prometheus-values.yaml — 15-day/18GB metric "
    "retention, a 20Gi Prometheus PVC and 2Gi Alertmanager PVC, Grafana with "
    "persistence and two pre-provisioned community dashboards (Kubernetes "
    "Cluster Monitoring and Node Exporter), and an additional scrape config "
    "that picks up any pod carrying the prometheus.io/scrape=true "
    "annotation — which is exactly the annotation the sample app's "
    "Deployment sets on itself."
)

doc.add_heading2("5.6 Sample application (Apps/sample-app)")
doc.add_paragraph(
    "A minimal Flask + Gunicorn service used purely to exercise the "
    "platform's workload-facing features, not as a product in its own "
    "right: a rolling-update Deployment with pod anti-affinity and resource "
    "requests/limits, a ClusterIP Service, an ALB-class Ingress, an HPA, and "
    "a NetworkPolicy. The container runs as a non-root user with all Linux "
    "capabilities dropped and privilege escalation disabled, and ships a "
    "Docker HEALTHCHECK against /health."
)

doc.add_heading2("5.7 CI/CD pipelines (.github/workflows)")
doc.add_paragraph(
    "terraform-plan.yaml and terraform-apply.yaml implement the plan/apply "
    "split described in Section 4, both authenticating to AWS via OIDC "
    "federation rather than static credentials, both matrixed over the dev "
    "and prod environments, and both scoped to only trigger on changes "
    "under Terraform/**."
)

doc.add_heading2("5.8 Operational scripts (Scripts/)")
doc.add_paragraph(
    "Scripts/setup.sh is the one-time, imperative cluster bootstrap: it "
    "points kubectl at the new cluster, installs ArgoCD from its upstream "
    "manifest, applies the repo's ArgoCD Application manifests, installs "
    "metrics-server, and prints the ArgoCD admin password. "
    "Scripts/cost_optimizer.py is a standalone boto3 script (not wired into "
    "CI) that scans a region for idle EC2 instances (avg CPU < 5% over 7 "
    "days via CloudWatch), unattached EBS volumes, and unassociated Elastic "
    "IPs, and prints/writes a JSON report estimating monthly savings."
)

# ---------------------------------------------------------------------------
# 6. Data design / Configuration & state model
# ---------------------------------------------------------------------------
doc.add_heading1("6. Data design (configuration & state model)")
doc.add_paragraph(
    "This platform has no application database — its persistent state is "
    "entirely infrastructure and configuration state, held in a small "
    "number of well-defined places:"
)
doc.add_table(
    headers=["State/config item", "Where it lives", "Notes"],
    rows=[
        ["Terraform state (per environment)", "S3 bucket eks-platform-terraform-state-<account_id>, one object key per environment (e.g. dev/eks-platform/terraform.tfstate)", "Versioned and KMS-encrypted; the bucket and its DynamoDB lock table (terraform-state-lock) are themselves provisioned once by Terraform/backend.tf, a bootstrap root module outside the dev/prod environments."],
        ["Terraform variable values", "Terraform/Environments/<env>/terraform.tfvars and variables.tf", "Per-environment region/project/environment name; validated (environment must be dev/stage/prod) via a Terraform variable validation block."],
        ["Cluster/add-on desired state", "Kubernetes/argocd/applications/*.yaml, Kubernetes/monitoring/prometheus-values.yaml, Apps/sample-app/k8s/*.yaml", "The single source of truth ArgoCD reconciles the live cluster against."],
        ["Application config (sample app)", "Environment variables injected by the Deployment manifest (ENVIRONMENT via the Downward API, APP_VERSION as a literal)", "No external config store or secret manager is used by the sample app itself."],
        ["Secrets", "Encrypted SealedSecret custom resources in Git, decrypted only in-cluster by the Sealed Secrets controller", "Plaintext secrets are never committed; .gitignore excludes common credential file patterns."],
        ["Cost audit output", "cost_report.json, written locally by Scripts/cost_optimizer.py", "Not persisted centrally; a point-in-time report generated on demand."],
    ],
)

# ---------------------------------------------------------------------------
# 7. Technology stack
# ---------------------------------------------------------------------------
doc.add_heading1("7. Technology stack")
doc.add_table(
    headers=["Layer", "Technology", "Notes"],
    rows=[
        ["Infrastructure as Code", "Terraform >= 1.6, hashicorp/aws provider ~> 5.0", "Three reusable modules (vpc, eks, iam) plus two environment root modules (dev, prod)."],
        ["Cloud provider", "AWS (ap-south-1 by default)", "VPC, EKS, EC2, IAM, S3, DynamoDB, Route 53 (via External DNS role)."],
        ["Container orchestration", "Amazon EKS 1.30, managed node groups (on-demand EC2)", "Single node group per environment; private-subnets-only."],
        ["GitOps / continuous delivery", "ArgoCD", "Automated sync with prune + self-heal for the two add-on Applications."],
        ["Observability", "kube-prometheus-stack (Prometheus, Alertmanager, Grafana), metrics-server", "Custom values in Kubernetes/monitoring/prometheus-values.yaml; metrics-server installed directly by Scripts/setup.sh (not via ArgoCD)."],
        ["Secret management", "Sealed Secrets (Bitnami)", "Delivered via ArgoCD Application."],
        ["Ingress / load balancing", "AWS Load Balancer Controller (IRSA role provisioned; controller install itself is an operational prerequisite, not shipped as a manifest in this repo)", "Sample app's Ingress is annotated for ALB, internet-facing, HTTP+HTTPS listeners."],
        ["Sample workload runtime", "Python 3.12, Flask, Gunicorn", "Packaged as a non-root Docker image with a HEALTHCHECK."],
        ["CI/CD", "GitHub Actions, hashicorp/setup-terraform, terraform-linters/setup-tflint, aws-actions/configure-aws-credentials (OIDC)", "No static AWS keys stored anywhere in the pipeline."],
        ["Scripting / tooling", "Bash (Scripts/setup.sh), Python 3 + boto3 (Scripts/cost_optimizer.py)", "Operational, not part of the deployed runtime."],
    ],
)

# ---------------------------------------------------------------------------
# 8. Deployment architecture
# ---------------------------------------------------------------------------
doc.add_heading1("8. Deployment architecture")
doc.add_figure_placeholder(
    "Figure 8.1 — VPC topology: Internet Gateway at the edge; per-AZ public "
    "subnet (NAT Gateway + Elastic IP) and private subnet (EKS nodes) pair, "
    "repeated across 2 AZs in dev / 3 AZs in prod; each private subnet's "
    "route table points 0.0.0.0/0 at its own AZ's NAT Gateway; the EKS "
    "control plane sits outside the subnets as a managed AWS service reachable "
    "via both a private ENI in the VPC and (by default) a public endpoint."
)
doc.add_paragraph(
    "Dev provisions a 10.0.0.0/16 VPC across two AZs (ap-south-1a/1b) with "
    "public subnets 10.0.1.0/24 and 10.0.2.0/24 and private subnets "
    "10.0.10.0/24 and 10.0.11.0/24; its node group runs t3.medium instances "
    "sized min 1 / desired 2 / max 4. Prod provisions a "
    "separate 10.1.0.0/16 VPC across three AZs (ap-south-1a/1b/1c) with "
    "public subnets 10.1.1-3.0/24 and private subnets 10.1.10-12.0/24; its "
    "node group runs m5.large instances sized desired 3 / min 3 / max 10, "
    "and additionally provisions a versioned, KMS-encrypted S3 backup "
    "bucket. In both environments the node group is restricted to private "
    "subnets only, and every private subnet gets its own AZ-local NAT "
    "Gateway rather than sharing one across the VPC, trading a small "
    "additional NAT Gateway cost for AZ-independent egress (no single NAT "
    "Gateway failure takes down every AZ's outbound traffic)."
)
doc.add_table(
    headers=["Setting", "Dev", "Prod"],
    rows=[
        ["VPC CIDR", "10.0.0.0/16", "10.1.0.0/16"],
        ["Availability zones", "2 (ap-south-1a, ap-south-1b)", "3 (ap-south-1a, ap-south-1b, ap-south-1c)"],
        ["Node instance type", "t3.medium", "m5.large"],
        ["Node group sizing (min/desired/max)", "1 / 2 / 4", "3 / 3 / 10"],
        ["IRSA (iam module) provisioned", "No — dev's root module does not call the iam module", "Yes"],
        ["Extra resources", "None", "Versioned, KMS-encrypted S3 backup bucket"],
        ["Kubernetes version", "1.30", "1.30"],
        ["EKS endpoint access", "Private + public (default; not restricted by CIDR)", "Private + public (default; not restricted by CIDR)"],
    ],
)

# ---------------------------------------------------------------------------
# 9. Security design
# ---------------------------------------------------------------------------
doc.add_heading1("9. Security design")
doc.add_bullets([
    "IRSA over node-wide IAM: the ALB Controller, Cluster Autoscaler, and "
    "External DNS each get their own IAM role, trust-scoped by OIDC audience "
    "and subject to one exact kube-system ServiceAccount, rather than "
    "granting these permissions to the EKS node IAM role that every pod on "
    "the node could otherwise reach.",
    "Least-privilege inline policies: the Cluster Autoscaler and External "
    "DNS roles use narrowly scoped inline policies (autoscaling/EC2 describe "
    "+ a small write set for the autoscaler; Route 53 record-set changes and "
    "list operations only for External DNS) rather than broad managed "
    "policies.",
    "Network segmentation: EKS worker nodes run in private subnets only; "
    "public subnets exist solely to host NAT Gateways and (eventually) "
    "internet-facing load balancers, never the nodes themselves.",
    "Kubernetes NetworkPolicy: the sample app ships a default-deny-style "
    "NetworkPolicy permitting ingress only from the ingress-nginx namespace "
    "and same-namespace pods on port 8080, and egress only to a 'data' "
    "namespace on port 3306 plus DNS (53) and HTTPS (443) — a deliberately "
    "restrictive, illustrative policy (the Flask app itself makes no "
    "database calls; the port-3306 rule demonstrates the pattern rather than "
    "reflecting an actual dependency).",
    "Pod-level hardening: the sample app's containers run as a non-root "
    "user (runAsNonRoot, runAsUser 1000), drop all Linux capabilities, and "
    "disallow privilege escalation, both at the Docker level (a dedicated "
    "appuser) and the Kubernetes securityContext level.",
    "Encrypted, access-controlled Terraform state: the state S3 bucket has "
    "versioning, default KMS server-side encryption, and all four public-"
    "access-block settings enabled; DynamoDB provides state locking to "
    "prevent concurrent-apply corruption.",
    "No static cloud credentials in CI: both GitHub Actions workflows "
    "assume an AWS IAM role via GitHub's OIDC identity provider "
    "(role-to-assume: secrets.AWS_ROLE_ARN) instead of storing an access "
    "key/secret pair.",
    "Encrypted secrets in Git: Sealed Secrets ensures any Kubernetes Secret "
    "committed to the repository is ciphertext outside the cluster and only "
    "decryptable by the in-cluster controller's private key.",
    "Known gap, called out honestly: the EKS API server has both private "
    "and public endpoint access enabled with no public_access_cidrs "
    "restriction in either environment — the README itself flags this as a "
    "setting to tighten (endpoint_public_access = false, or a restricted "
    "public_access_cidrs list) before any real production use.",
])

# ---------------------------------------------------------------------------
# 10. Non-functional requirements
# ---------------------------------------------------------------------------
doc.add_heading1("10. Non-functional requirements")
doc.add_table(
    headers=["Attribute", "Target / approach"],
    rows=[
        ["Scalability", "Horizontal scaling at two layers: the HPA scales sample-app pods 2-10 on CPU (70%) and memory (80%) utilization with asymmetric scale-up/scale-down windows; the EKS managed node group itself scales within its configured min/max (1-4 in dev, 3-10 in prod) — node-level autoscaling requires the Cluster Autoscaler add-on to actually be installed in-cluster, since only its IRSA role is provisioned by Terraform today."],
        ["Availability", "Multi-AZ by design: 2 AZs in dev, 3 in prod, each with its own NAT Gateway and private subnet; the node group's update_config caps max_unavailable at 1 during rolling node updates; the sample app's Deployment uses maxUnavailable: 0 / maxSurge: 1 plus preferred pod anti-affinity across hosts, so a single node or pod loss should not cause an outage."],
        ["Cost efficiency", "Right-sized instance types per environment (t3.medium in dev, m5.large in prod), PAY_PER_REQUEST DynamoDB billing for the lock table, and an on-demand cost-optimizer script (Scripts/cost_optimizer.py) that surfaces idle EC2/unattached EBS/unused EIP spend — run manually, not on a schedule, in the current repo."],
        ["Auditability", "EKS control-plane logging enabled for all five log types (api, audit, authenticator, controllerManager, scheduler); Terraform state is versioned in S3 so historical infrastructure state is recoverable; every infra change passes through a reviewed PR with a posted plan before it can reach main."],
        ["Repeatability", "Both environments are produced from the same three Terraform modules with only variable inputs differing, so a third environment (e.g. staging) could be added as a new root module with minimal duplication."],
        ["Recoverability", "Prod provisions a dedicated, versioned, KMS-encrypted S3 backup bucket as a target for future backup automation; Terraform state itself is versioned and lock-protected against concurrent corruption."],
    ],
)

# ---------------------------------------------------------------------------
# 11. Assumptions & constraints
# ---------------------------------------------------------------------------
doc.add_heading1("11. Assumptions & constraints")
doc.add_bullets([
    "The Terraform/backend.tf bootstrap (state S3 bucket + DynamoDB lock "
    "table) must be applied once, out of band, before either environment's "
    "commented-out S3 backend block is uncommented and filled in — until "
    "then, Terraform state for dev/prod is local.",
    "The AWS_ROLE_ARN GitHub secret (and the corresponding IAM role's trust "
    "policy for GitHub's OIDC provider) must be configured outside this "
    "repository for the CI/CD workflows to authenticate at all.",
    "ArgoCD itself is bootstrapped imperatively by Scripts/setup.sh, not by "
    "Terraform or by GitOps — the platform assumes an operator runs this "
    "script once per new cluster.",
    "The dev environment's root module does not currently call the iam "
    "module, so dev does not provision the ALB Controller / Cluster "
    "Autoscaler / External DNS IRSA roles that prod does — dev is assumed "
    "to be a lighter-weight environment, not a full mirror of prod.",
    "IRSA roles exist for the AWS Load Balancer Controller, Cluster "
    "Autoscaler, and External DNS, but installing those controllers "
    "themselves into the cluster (as Helm releases/ArgoCD Applications) is "
    "assumed to be a separate, not-yet-automated operational step.",
    "The sample app's container image reference (your-ecr-repo/sample-app:"
    "latest) is a placeholder — an ECR repository and an image-build/push "
    "step are assumed to exist outside this repository before the "
    "Deployment can actually run.",
    "The EKS API server's public endpoint access is left open "
    "(no public_access_cidrs restriction) in both environments by default; "
    "this is a documented, intentional simplification for a portfolio/demo "
    "repository, not a recommended production default.",
    "A DNS hosted zone and TLS certificate are assumed to be provisioned and "
    "managed outside this repository for the sample app's Ingress host "
    "(app.eks-platform.example.com) and the External DNS role's Route 53 "
    "access to be meaningful.",
])

# ---------------------------------------------------------------------------
# 12. Future enhancements
# ---------------------------------------------------------------------------
doc.add_heading1("12. Future enhancements")
doc.add_bullets([
    "Actually install the AWS Load Balancer Controller, Cluster Autoscaler, "
    "and External DNS into the cluster (as Helm releases or ArgoCD "
    "Applications) so the IRSA roles the iam module already provisions have "
    "a workload to attach to — today the roles exist but the controllers "
    "are not deployed by anything in this repository.",
    "Either implement Karpenter (the private subnets are already tagged "
    "karpenter.sh/discovery and the iam module's header comment mentions "
    "it) or remove the references so the repo doesn't imply a capability "
    "that isn't built.",
    "Call the iam module from the dev environment root module too, so both "
    "environments have IRSA parity, or document the asymmetry as permanent "
    "and intentional.",
    "Restrict the EKS API server's public endpoint access "
    "(public_access_cidrs or endpoint_public_access = false) per the "
    "README's own security note, at least for the prod environment.",
    "Add an ArgoCD Application for the sample app itself (today it's only "
    "deployable via a manual kubectl apply -f), closing the GitOps loop "
    "completely.",
    "Schedule Scripts/cost_optimizer.py (e.g. as a GitHub Actions cron job "
    "or EventBridge rule) rather than running it manually, and expand its "
    "checks beyond EC2/EBS/EIP (e.g. idle load balancers, oversized node "
    "groups against actual utilization).",
    "Add automated tests (e.g. Terratest or terraform test) for the "
    "Terraform modules, and a staging environment root module reusing the "
    "same three modules.",
])

# ---------------------------------------------------------------------------
# 13. Appendix
# ---------------------------------------------------------------------------
doc.add_heading1("13. Appendix")
doc.add_heading2("13.1 References")
doc.add_bullets([
    "Repository README.md (Darviq Eks) — architecture summary, setup steps, "
    "security notes, and key outcomes demonstrated.",
    "Terraform/Modules/vpc, /eks, /iam — module source and variable/output "
    "definitions.",
    "Terraform/Environments/dev, /prod — environment root modules and "
    "terraform.tfvars.",
    "Kubernetes/argocd/applications/*.yaml, Kubernetes/monitoring/"
    "prometheus-values.yaml — GitOps add-on declarations.",
    "Apps/sample-app/ — sample Flask application and its Kubernetes "
    "manifests.",
    ".github/workflows/terraform-plan.yaml, terraform-apply.yaml — CI/CD "
    "pipeline definitions.",
    "Darviq_Eks_Low_Level_Design.docx — the companion LLD document for this "
    "repository.",
])

doc.add_heading2("13.2 Change history")
doc.add_table(
    headers=["Version", "Date", "Description"],
    rows=[
        [VERSION, DATE, "Initial high-level design document"],
    ],
)

doc.save("Darviq_Eks_High_Level_Design.docx")
print("Saved Darviq_Eks_High_Level_Design.docx")

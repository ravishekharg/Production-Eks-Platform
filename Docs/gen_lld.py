# -*- coding: utf-8 -*-
"""Generates Darviq_Eks_Low_Level_Design.docx from the docx_builder helper.
Run from the Docs/ directory: python gen_lld.py
"""
from docx_builder import DesignDoc

VERSION = "1.0"
DATE = "July 31, 2026"

doc = DesignDoc(
    project_name="Darviq Eks",
    subtitle="Production-Style AWS EKS Platform on Terraform and Kubernetes",
    doc_kind="Low-Level Design (LLD)",
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
    "This Low-Level Design (LLD) document expands on the "
    "Darviq_Eks_High_Level_Design.docx document by describing the concrete "
    "Terraform resources, variable contracts, Kubernetes manifests, CI/CD "
    "pipeline steps, and operational scripts that make up the Darviq Eks "
    "repository. Where the HLD describes what each component is responsible "
    "for and how the pieces relate, this document describes how each "
    "component is actually implemented — real resource names, real "
    "variables and defaults, real file paths — so that a reader can locate "
    "and modify the exact code referenced here."
)

doc.add_heading2("1.2 Scope")
doc.add_paragraph(
    "This document covers the Terraform modules (vpc, eks, iam) and "
    "environment root modules (dev, prod), the Kubernetes/ArgoCD add-on "
    "manifests, the sample application and its Kubernetes manifests, the "
    "GitHub Actions workflows, and the two operational scripts. It does not "
    "re-derive the architectural rationale already covered in the HLD; "
    "cross-references to HLD sections are used instead of repeating them."
)

doc.add_heading2("1.3 References")
doc.add_bullets([
    "Darviq_Eks_High_Level_Design.docx — companion HLD document (Sections 3 "
    "and 5 in particular, for the architecture and module list this LLD "
    "expands on).",
    "Terraform/Modules/vpc/{main,variables,outputs}.tf",
    "Terraform/Modules/eks/{main,variables,outputs}.tf",
    "Terraform/Modules/iam/{main,variables,outputs}.tf, "
    "Terraform/Modules/iam/policies/alb-controller-policy.json",
    "Terraform/Environments/dev/{main,variables}.tf, terraform.tfvars",
    "Terraform/Environments/prod/{main,variables}.tf, terraform.tfvars",
    "Terraform/backend.tf",
    "Kubernetes/argocd/applications/{monitoring,sealed-secrets}.yaml",
    "Kubernetes/monitoring/prometheus-values.yaml",
    "Apps/sample-app/{app.py, Dockerfile, requirements.txt}, "
    "Apps/sample-app/k8s/{deployment,service,ingress,hpa,networkpolicy}.yaml",
    ".github/workflows/{terraform-plan,terraform-apply}.yaml",
    "Scripts/setup.sh, Scripts/cost_optimizer.py",
])

# ---------------------------------------------------------------------------
# 2. Detailed module design
# ---------------------------------------------------------------------------
doc.add_heading1("2. Detailed module design")

doc.add_heading2("2.1 VPC / networking module — Terraform/Modules/vpc/main.tf")
doc.add_paragraph(
    "Resources: aws_vpc.main (DNS hostnames and DNS support both enabled); "
    "aws_internet_gateway.main; aws_subnet.public (count = "
    "length(var.public_subnet_cidrs), map_public_ip_on_launch = true, tagged "
    "kubernetes.io/role/elb = \"1\"); aws_subnet.private (count = "
    "length(var.private_subnet_cidrs), tagged kubernetes.io/role/"
    "internal-elb = \"1\" and karpenter.sh/discovery = var.cluster_name); "
    "aws_eip.nat (one per public subnet, domain = \"vpc\"); "
    "aws_nat_gateway.main (one per public subnet, explicit depends_on the "
    "Internet Gateway); aws_route_table.public (single table, default route "
    "to the IGW) with aws_route_table_association.public per public subnet; "
    "aws_route_table.private (one table per AZ, default route to that AZ's "
    "NAT Gateway via count.index) with aws_route_table_association.private "
    "per private subnet. Every private subnet therefore has its own "
    "dedicated NAT Gateway rather than sharing one across the VPC."
)

doc.add_heading2("2.2 EKS cluster & node-group module — Terraform/Modules/eks/main.tf")
doc.add_paragraph(
    "Resources: aws_eks_cluster.main (name = var.cluster_name, version = "
    "var.kubernetes_version, vpc_config.subnet_ids = "
    "var.private_subnet_ids, endpoint_private_access = true, "
    "endpoint_public_access = true, enabled_cluster_log_types = [\"api\", "
    "\"audit\", \"authenticator\", \"controllerManager\", \"scheduler\"]); "
    "aws_iam_role.eks_cluster (trust policy: Service = eks.amazonaws.com) "
    "with aws_iam_role_policy_attachment.eks_cluster_policy "
    "(AmazonEKSClusterPolicy) and .eks_vpc_policy "
    "(AmazonEKSVPCResourceController); aws_eks_node_group.main "
    "(node_group_name = \"${var.cluster_name}-ng-main\", subnet_ids = "
    "var.private_subnet_ids, capacity_type = \"ON_DEMAND\", scaling_config "
    "from var.node_desired_size/max_size/min_size, update_config."
    "max_unavailable = 1, labels = { role = \"general\" }); "
    "aws_iam_role.node_group (trust policy: Service = ec2.amazonaws.com) "
    "with three managed-policy attachments (AmazonEKSWorkerNodePolicy, "
    "AmazonEKS_CNI_Policy, AmazonEC2ContainerRegistryReadOnly); and the IRSA "
    "trust anchor itself — data.tls_certificate.eks (reads the cluster's "
    "OIDC issuer certificate) feeding aws_iam_openid_connect_provider.eks "
    "(client_id_list = [\"sts.amazonaws.com\"], thumbprint from the TLS "
    "certificate's SHA1 fingerprint). Both the cluster's log types and the "
    "node group's update_config.max_unavailable = 1 are hardcoded in this "
    "module, not exposed as variables."
)

doc.add_heading2("2.3 IAM / IRSA module — Terraform/Modules/iam/main.tf")
doc.add_paragraph(
    "The module's own header comment states its scope directly: 'IAM roles "
    "for additional platform services (EKS cluster + node roles are in "
    "eks/main.tf). This module handles: ALB Controller, External DNS, "
    "Cluster Autoscaler, Karpenter' — though, as noted in the HLD (Section "
    "3.1) and Section 6 of this document, no Karpenter resources are "
    "actually defined below that comment. Three role/policy pairs exist, "
    "each following the same shape: an aws_iam_role trusting "
    "var.oidc_provider_arn via sts:AssumeRoleWithWebIdentity, gated by a "
    "StringEquals condition on {oidc_provider_id}:aud = "
    "sts.amazonaws.com and {oidc_provider_id}:sub = "
    "system:serviceaccount:<namespace>:<name>: "
    "aws_iam_role.alb_controller (sub = kube-system:aws-load-balancer-"
    "controller) attached to aws_iam_policy.alb_controller, whose policy "
    "document is loaded verbatim from "
    "policies/alb-controller-policy.json (the upstream AWS-published ALB "
    "Controller IAM policy — ELB/EC2/ACM/WAF/Shield describe+mutate "
    "actions scoped where possible by the elbv2.k8s.aws/cluster resource "
    "tag); aws_iam_role.cluster_autoscaler (sub = kube-system:"
    "cluster-autoscaler) with an inline aws_iam_role_policy granting "
    "autoscaling:Describe*, ec2:Describe*/GetInstanceTypesFrom..., and "
    "eks:DescribeNodegroup (read) plus autoscaling:SetDesiredCapacity and "
    "autoscaling:TerminateInstanceInAutoScalingGroup (write) — both on "
    "Resource = \"*\"; aws_iam_role.external_dns (sub = kube-system:"
    "external-dns) with an inline policy granting route53:"
    "ChangeResourceRecordSets on arn:aws:route53:::hostedzone/* and "
    "route53:ListHostedZones/ListResourceRecordSets on Resource = \"*\"."
)

doc.add_heading2("2.4 Environment root modules — Terraform/Environments/{dev,prod}/main.tf")
doc.add_paragraph(
    "dev/main.tf: required_version >= 1.6.0, aws provider ~> 5.0, region = "
    "var.aws_region (default ap-south-1), default_tags applied to every "
    "resource (Project, Environment = \"dev\", ManagedBy = \"terraform\", "
    "Owner = \"ravi-shekhar-reddy\"). Calls module \"vpc\" with vpc_cidr "
    "10.0.0.0/16, public_subnet_cidrs [10.0.1.0/24, 10.0.2.0/24], "
    "private_subnet_cidrs [10.0.10.0/24, 10.0.11.0/24], availability_zones "
    "[ap-south-1a, ap-south-1b]; then module \"eks\" with "
    "kubernetes_version 1.30, node_instance_types [t3.medium], "
    "node_desired_size 2, node_max_size 4, node_min_size 1. local."
    "cluster_name = \"${var.project_name}-${var.environment}\" (resolves to "
    "eks-platform-dev per terraform.tfvars). dev does not call module "
    "\"iam\" — this is a real, verifiable asymmetry with prod, not a design "
    "inconsistency introduced by this document."
)
doc.add_paragraph(
    "prod/main.tf: same provider/version constraints, Environment = "
    "\"prod\" tag. Calls module \"vpc\" with vpc_cidr 10.1.0.0/16, three "
    "public and three private subnet CIDRs, three AZs (ap-south-1a/1b/1c); "
    "module \"eks\" with node_instance_types [m5.large], node_desired_size "
    "3, node_max_size 10, node_min_size 3; and — unlike dev — module "
    "\"iam\" wired to module.eks.oidc_provider_arn / oidc_provider_url. "
    "Additionally provisions aws_s3_bucket.backups (name = "
    "\"${var.project_name}-prod-backups-${account_id}\") with versioning "
    "and default aws:kms server-side encryption enabled. Root outputs "
    "expose cluster_name, cluster_endpoint, and alb_controller_role."
)
doc.add_paragraph(
    "Both environment root modules currently ship their backend \"s3\" "
    "block commented out; state is local until Terraform/backend.tf has "
    "been applied once (out of band, per the README) and the block is "
    "manually uncommented with the bucket/key/region/dynamodb_table it "
    "creates."
)

doc.add_heading2("2.5 Terraform bootstrap — Terraform/backend.tf")
doc.add_paragraph(
    "A standalone root module (not part of dev or prod) that provisions "
    "the remote-state backend itself: aws_s3_bucket.terraform_state (name "
    "= \"eks-platform-terraform-state-${account_id}\", lifecycle."
    "prevent_destroy = true), aws_s3_bucket_versioning (Enabled), "
    "aws_s3_bucket_server_side_encryption_configuration (aws:kms), "
    "aws_s3_bucket_public_access_block (all four flags true), and "
    "aws_dynamodb_table.terraform_locks (name = \"terraform-state-lock\", "
    "billing_mode PAY_PER_REQUEST, hash_key \"LockID\"). Outputs "
    "state_bucket_name and lock_table_name for use when filling in each "
    "environment's backend block."
)

doc.add_heading2("2.6 GitOps add-ons — Kubernetes/argocd/applications/*.yaml")
doc.add_paragraph(
    "monitoring.yaml: an argoproj.io/v1alpha1 Application named "
    "kube-prometheus-stack, project default, source.repoURL = "
    "https://prometheus-community.github.io/helm-charts, chart "
    "kube-prometheus-stack, targetRevision 58.1.3, helm.valueFiles = "
    "[values.yaml], destination namespace monitoring, syncPolicy.automated "
    "{prune: true, selfHeal: true}, syncOptions [CreateNamespace=true]."
)
doc.add_paragraph(
    "sealed-secrets.yaml: an Application named sealed-secrets, source."
    "repoURL = https://bitnami-labs.github.io/sealed-secrets, chart "
    "sealed-secrets, targetRevision 2.15.0, destination namespace "
    "kube-system, syncPolicy.automated {prune: true, selfHeal: true} (no "
    "CreateNamespace option needed since kube-system always exists)."
)
doc.add_paragraph(
    "Kubernetes/monitoring/prometheus-values.yaml (referenced by the "
    "monitoring Application's helm.valueFiles): grafana.persistence "
    "5Gi, a custom \"platform\" dashboard provider loading two "
    "community dashboards (kubernetes-cluster grafana.com id 7249 rev 1, "
    "node-exporter id 1860 rev 37); prometheus.prometheusSpec.retention "
    "15d / retentionSize 18GB with a 20Gi PVC, "
    "podMonitorSelectorNilUsesHelmValues and "
    "serviceMonitorSelectorNilUsesHelmValues both set false (so Prometheus "
    "only picks up explicitly selected Pod/ServiceMonitors plus the "
    "additionalScrapeConfigs job below), and an additionalScrapeConfigs "
    "job \"platform-pods\" using a kubernetes_sd_configs pod role with "
    "relabel_configs that keep only pods annotated prometheus.io/scrape: "
    "\"true\" and rewrite __metrics_path__ from prometheus.io/path; "
    "alertmanager with a 2Gi PVC; nodeExporter and kubeStateMetrics both "
    "enabled."
)

doc.add_heading2("2.7 Sample application — Apps/sample-app/")
doc.add_paragraph(
    "app.py: a Flask app with three routes — GET / returns a JSON payload "
    "(service, status, hostname via socket.gethostname(), UTC timestamp, "
    "APP_VERSION and ENVIRONMENT from env vars); GET /health returns "
    "{\"status\": \"ok\"}, 200; GET /ready returns {\"status\": \"ready\"}, "
    "200. Dockerfile: python:3.12-slim base, a dedicated non-root appuser/"
    "appgroup created via addgroup/adduser --system, dependencies "
    "installed before the app is copied in, ownership chowned to appuser, "
    "USER appuser before EXPOSE 8080, a Docker HEALTHCHECK polling /health "
    "every 30s, and CMD gunicorn --bind 0.0.0.0:8080 --workers 2 app:app."
)
doc.add_paragraph(
    "k8s/deployment.yaml: replicas 2, RollingUpdate strategy with "
    "maxUnavailable 0 / maxSurge 1, pod securityContext runAsNonRoot / "
    "runAsUser 1000 / fsGroup 2000, container securityContext "
    "allowPrivilegeEscalation false and capabilities.drop [ALL], "
    "prometheus.io/scrape=true and prometheus.io/port=8080 pod "
    "annotations (picked up by the additionalScrapeConfigs job in Section "
    "2.6), resource requests 100m CPU/128Mi memory and limits 500m CPU/"
    "256Mi memory, livenessProbe on /health (initialDelaySeconds 15, "
    "periodSeconds 20) and readinessProbe on /ready (initialDelaySeconds "
    "5, periodSeconds 10), and a preferred podAntiAffinity rule spreading "
    "replicas across distinct nodes (topologyKey kubernetes.io/hostname). "
    "The image reference your-ecr-repo/sample-app:latest is a literal "
    "placeholder pending a real ECR repository."
)
doc.add_paragraph(
    "k8s/service.yaml: ClusterIP Service named sample-app, port 80 -> "
    "targetPort 8080. k8s/ingress.yaml: networking.k8s.io/v1 Ingress "
    "annotated kubernetes.io/ingress.class: alb, "
    "alb.ingress.kubernetes.io/scheme: internet-facing, target-type: ip, "
    "listen-ports [HTTP 80, HTTPS 443], ssl-redirect 443, and ALB "
    "health-check annotations pointed at /health (15s interval, healthy "
    "threshold 2, unhealthy threshold 3); a single host rule for "
    "app.eks-platform.example.com. k8s/hpa.yaml: autoscaling/v2 HPA, "
    "minReplicas 2 / maxReplicas 10, targeting 70% average CPU and 80% "
    "average memory utilization, with an asymmetric behavior block "
    "(scaleDown: 300s stabilization window, 1 pod per 60s; scaleUp: 60s "
    "stabilization window, 2 pods per 60s). k8s/networkpolicy.yaml: "
    "restricts ingress to traffic from the ingress-nginx namespace or "
    "same-namespace pods on port 8080, and egress to a \"data\" namespace "
    "on port 3306 plus unrestricted DNS (53) and HTTPS (443) egress."
)

doc.add_heading2("2.8 CI/CD workflows — .github/workflows/")
doc.add_paragraph(
    "terraform-plan.yaml: triggers on pull_request to main, paths "
    "Terraform/**; permissions id-token: write (for OIDC), contents: read, "
    "pull-requests: write; concurrency group keyed per environment+PR "
    "number with cancel-in-progress; a matrix over [dev, prod] "
    "(fail-fast: false); steps are checkout, configure-aws-credentials "
    "with role-to-assume: secrets.AWS_ROLE_ARN, setup-terraform (version "
    "1.7.0), terraform fmt -check -recursive (run from Terraform/), "
    "terraform init and validate (run from Terraform/Environments/"
    "<env>), setup-tflint (v0.50.3) and tflint --recursive (from "
    "Terraform/), terraform plan -no-color -out=tfplan piped through tee "
    "to plan_output.txt, and a github-script step that reads that file and "
    "posts it (truncated at 65,000 characters) as a PR comment."
)
doc.add_paragraph(
    "terraform-apply.yaml: triggers on push to main, paths Terraform/**; "
    "permissions id-token: write, contents: read; uses GitHub Environments "
    "(environment: ${{ matrix.environment }}) so environment-scoped "
    "secrets resolve automatically and, if required reviewers are "
    "configured on the prod Environment in repo Settings, the job pauses "
    "for manual approval before applying to prod; concurrency group keyed "
    "per environment with cancel-in-progress: false; matrix [dev, prod] "
    "with max-parallel: 1 (dev and prod are never applied concurrently); "
    "steps are checkout, configure-aws-credentials, setup-terraform, "
    "fmt -check, init, validate, terraform plan -out=tfplan, terraform "
    "apply tfplan, aws eks update-kubeconfig --name eks-platform-"
    "${{ matrix.environment }}, and kubectl get nodes as a smoke check."
)

doc.add_heading2("2.9 Operational scripts — Scripts/")
doc.add_paragraph(
    "setup.sh (bash, set -euo pipefail, positional args CLUSTER_NAME "
    "default eks-platform-dev and REGION default ap-south-1): "
    "[1/5] aws eks update-kubeconfig; [2/5] create the argocd namespace "
    "(idempotent via --dry-run=client -o yaml | kubectl apply -f -) and "
    "apply ArgoCD's upstream stable install.yaml, then kubectl wait "
    "--for=condition=available --timeout=300s on deployment/argocd-server; "
    "[3/5] kubectl apply -f Kubernetes/argocd/applications/; [4/5] install "
    "the upstream metrics-server components.yaml; [5/5] kubectl get "
    "nodes, kubectl get pods -n argocd, kubectl get pods -n monitoring, "
    "then decode and print the ArgoCD initial-admin-secret password and a "
    "reminder to port-forward argocd-server."
)
doc.add_paragraph(
    "cost_optimizer.py (Python 3, boto3, dataclasses Finding/CostReport): "
    "check_idle_ec2() paginates ec2:DescribeInstances (running only), "
    "pulls 7-day average CPUUtilization per instance via CloudWatch "
    "get_metric_statistics (Period 86400, Statistics [Average]), and flags "
    "any instance averaging under 5% CPU with a flat estimated saving of "
    "$50/month; check_unattached_ebs() paginates ec2:DescribeVolumes "
    "(status = available) and estimates $0.08/GB/month; "
    "check_unused_elastic_ips() lists ec2:DescribeAddresses and flags any "
    "address with neither an InstanceId nor a NetworkInterfaceId at a "
    "flat $3.65/month. run_audit() drives all three checks against a "
    "given region and the caller's account id (sts:GetCallerIdentity); "
    "print_report() prints a formatted summary to stdout and writes "
    "cost_report.json. Invoked as python Scripts/cost_optimizer.py "
    "--region <region>; not wired into CI or run on a schedule."
)

# ---------------------------------------------------------------------------
# 3. Variable/output contracts and resource dependency graph
# ---------------------------------------------------------------------------
doc.add_heading1("3. Module variable/output contracts and dependency graph")

doc.add_heading2("3.1 vpc module — Terraform/Modules/vpc/variables.tf, outputs.tf")
doc.add_table(
    headers=["Variable", "Type", "Default", "Description"],
    rows=[
        ["project_name", "string", "(required)", "Used for resource naming/tagging."],
        ["cluster_name", "string", "(required)", "Used for the karpenter.sh/discovery subnet tag."],
        ["vpc_cidr", "string", "10.0.0.0/16", "CIDR block for the VPC."],
        ["public_subnet_cidrs", "list(string)", "(required)", "One entry per public subnet/AZ."],
        ["private_subnet_cidrs", "list(string)", "(required)", "One entry per private subnet/AZ."],
        ["availability_zones", "list(string)", "(required)", "Must align index-for-index with the CIDR lists."],
        ["tags", "map(string)", "{}", "Merged onto every resource's tag map."],
    ],
)
doc.add_table(
    headers=["Output", "Description"],
    rows=[
        ["vpc_id", "ID of the created VPC."],
        ["public_subnet_ids", "List of public subnet IDs (aws_subnet.public[*].id)."],
        ["private_subnet_ids", "List of private subnet IDs — consumed directly by the eks module."],
    ],
)

doc.add_heading2("3.2 eks module — Terraform/Modules/eks/variables.tf, outputs.tf")
doc.add_table(
    headers=["Variable", "Type", "Default", "Description"],
    rows=[
        ["cluster_name", "string", "(required)", "EKS cluster and node group naming."],
        ["kubernetes_version", "string", "1.30", "EKS control-plane version."],
        ["private_subnet_ids", "list(string)", "(required)", "From module.vpc.private_subnet_ids; both the cluster and the node group are placed here."],
        ["node_instance_types", "list(string)", "[t3.medium]", "EC2 instance type(s) for the managed node group."],
        ["node_desired_size", "number", "2", "Node group desired capacity."],
        ["node_max_size", "number", "6", "Node group max capacity."],
        ["node_min_size", "number", "1", "Node group min capacity."],
        ["tags", "map(string)", "{}", "Applied to the cluster and node group."],
    ],
)
doc.add_table(
    headers=["Output", "Description"],
    rows=[
        ["cluster_name", "EKS cluster name."],
        ["cluster_endpoint", "EKS API server endpoint URL."],
        ["cluster_ca_certificate", "Base64 cluster CA data, for kubeconfig generation."],
        ["oidc_provider_arn", "ARN of the IAM OIDC provider — consumed by the iam module."],
        ["oidc_provider_url", "OIDC issuer URL — consumed by the iam module."],
    ],
)

doc.add_heading2("3.3 iam module — Terraform/Modules/iam/variables.tf, outputs.tf")
doc.add_table(
    headers=["Variable", "Type", "Default", "Description"],
    rows=[
        ["cluster_name", "string", "(required)", "Used to name each IRSA role."],
        ["oidc_provider_arn", "string", "(required)", "From module.eks.oidc_provider_arn; the Federated principal in each role's trust policy."],
        ["oidc_provider_url", "string", "(required)", "From module.eks.oidc_provider_url; stripped of its https:// prefix to build the OIDC condition keys."],
        ["tags", "map(string)", "{}", "Not currently applied to any resource in main.tf (accepted but unused)."],
    ],
)
doc.add_table(
    headers=["Output", "Description"],
    rows=[
        ["alb_controller_role_arn", "IRSA role ARN for the AWS Load Balancer Controller ServiceAccount."],
        ["cluster_autoscaler_role_arn", "IRSA role ARN for the Cluster Autoscaler ServiceAccount."],
        ["external_dns_role_arn", "IRSA role ARN for the External DNS ServiceAccount."],
    ],
)

doc.add_heading2("3.4 Resource dependency graph")
doc.add_paragraph(
    "The provisioning order is strictly linear across modules, and each "
    "stage's outputs are the next stage's required inputs:"
)
doc.add_bullets([
    "vpc (aws_vpc, subnets, IGW, NAT Gateways, route tables) produces "
    "private_subnet_ids and public_subnet_ids.",
    "eks consumes private_subnet_ids to place both aws_eks_cluster.main and "
    "aws_eks_node_group.main, and additionally creates the OIDC provider "
    "(dependent on the cluster's own identity[0].oidc[0].issuer, so the "
    "cluster must exist first); it produces oidc_provider_arn / "
    "oidc_provider_url.",
    "iam (prod only) consumes oidc_provider_arn/url to create the three "
    "IRSA roles; it has no infrastructure dependents within Terraform "
    "itself — its outputs are consumed by Kubernetes ServiceAccount "
    "annotations that are applied out of band (not by Terraform).",
    "Kubernetes workloads (ArgoCD Applications, the sample app) depend on "
    "the eks module's cluster existing and being reachable, but are applied "
    "via kubectl/ArgoCD, not via a Terraform kubernetes/helm provider — "
    "there is no Terraform-level dependency edge from Kubernetes manifests "
    "back to the eks module; the link is operational (Scripts/setup.sh "
    "runs after terraform apply completes).",
])
doc.add_paragraph(
    "In short: VPC -> EKS cluster + node group + OIDC provider -> IAM/IRSA "
    "roles (prod only) -> [operator runs Scripts/setup.sh] -> ArgoCD -> "
    "ArgoCD Applications (monitoring, sealed-secrets) -> sample app "
    "(manual kubectl apply, or a future ArgoCD Application)."
)

doc.add_heading2("3.5 CI/CD pipeline stage reference")
doc.add_table(
    headers=["Workflow", "Stage", "Command"],
    rows=[
        ["terraform-plan.yaml", "Format check", "terraform fmt -check -recursive (in Terraform/)"],
        ["terraform-plan.yaml", "Init", "terraform init (in Terraform/Environments/<env>)"],
        ["terraform-plan.yaml", "Validate", "terraform validate"],
        ["terraform-plan.yaml", "Lint", "tflint --recursive (in Terraform/)"],
        ["terraform-plan.yaml", "Plan", "terraform plan -no-color -out=tfplan (output teed to plan_output.txt and posted to the PR)"],
        ["terraform-apply.yaml", "Format check / Init / Validate", "Same as plan workflow"],
        ["terraform-apply.yaml", "Plan", "terraform plan -no-color -out=tfplan"],
        ["terraform-apply.yaml", "Apply", "terraform apply tfplan"],
        ["terraform-apply.yaml", "Post-apply verification", "aws eks update-kubeconfig --name eks-platform-<env>; kubectl get nodes"],
    ],
)

doc.add_heading2("3.6 kubectl / Helm operational command reference")
doc.add_table(
    headers=["Purpose", "Command"],
    rows=[
        ["Point kubectl at a provisioned cluster", "aws eks update-kubeconfig --region <region> --name eks-platform-<env>"],
        ["Bootstrap ArgoCD + add-ons on a new cluster", "./Scripts/setup.sh eks-platform-dev ap-south-1"],
        ["Apply/refresh ArgoCD Application manifests", "kubectl apply -f Kubernetes/argocd/applications/"],
        ["Deploy the sample app directly (non-GitOps path)", "kubectl apply -f Apps/sample-app/k8s/"],
        ["Retrieve the ArgoCD initial admin password", "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath=\"{.data.password}\" | base64 -d"],
        ["Reach the ArgoCD UI locally", "kubectl port-forward svc/argocd-server -n argocd 8080:443"],
        ["Run the cost-optimization audit", "python Scripts/cost_optimizer.py --region ap-south-1"],
        ["One-time state-backend bootstrap", "terraform -chdir=Terraform apply -target=aws_s3_bucket.terraform_state -target=aws_s3_bucket_versioning.terraform_state -target=aws_s3_bucket_server_side_encryption_configuration.terraform_state -target=aws_s3_bucket_public_access_block.terraform_state -target=aws_dynamodb_table.terraform_locks"],
    ],
)

# ---------------------------------------------------------------------------
# 4. Sequence flows / process flows
# ---------------------------------------------------------------------------
doc.add_heading1("4. Sequence flows / process flows")

doc.add_heading2("4.1 Terraform plan/apply flow (CI-driven)")
doc.add_table(
    headers=["Step", "Actor / Component", "Action"],
    rows=[
        ["1", "Developer", "Opens a PR that changes a file under Terraform/**."],
        ["2", "GitHub Actions (terraform-plan.yaml)", "Assumes secrets.AWS_ROLE_ARN via OIDC, runs fmt -check, init, validate, tflint, and plan for each of [dev, prod] in parallel."],
        ["3", "GitHub Actions", "Posts the plan output (truncated to 65,000 chars) as a PR comment per environment."],
        ["4", "Reviewer", "Reads the posted plan, requests changes or approves."],
        ["5", "Developer/Reviewer", "Merges the PR to main."],
        ["6", "GitHub Actions (terraform-apply.yaml)", "Assumes AWS_ROLE_ARN via OIDC per environment; if the prod GitHub Environment has required reviewers configured, the prod job pauses for manual approval."],
        ["7", "GitHub Actions", "Re-runs fmt/init/validate/plan, then terraform apply tfplan, sequentially (max-parallel: 1) across [dev, prod]."],
        ["8", "GitHub Actions", "Runs aws eks update-kubeconfig and kubectl get nodes as a post-apply smoke check."],
    ],
)

doc.add_heading2("4.2 New-cluster bootstrap flow")
doc.add_table(
    headers=["Step", "Actor / Component", "Action"],
    rows=[
        ["1", "Operator", "Runs terraform apply in Terraform/Environments/<env> (directly, or via the CI apply flow in 4.1) to create the VPC, EKS cluster, node group, and (prod only) IRSA roles."],
        ["2", "Operator", "Runs ./Scripts/setup.sh <cluster_name> <region>."],
        ["3", "setup.sh", "aws eks update-kubeconfig, then creates the argocd namespace and applies ArgoCD's upstream install.yaml, waiting up to 300s for deployment/argocd-server to become available."],
        ["4", "setup.sh", "kubectl apply -f Kubernetes/argocd/applications/ registers the kube-prometheus-stack and sealed-secrets ArgoCD Applications."],
        ["5", "ArgoCD", "Automated sync (prune + selfHeal) pulls both Helm charts from their upstream repos and installs them into the monitoring and kube-system namespaces respectively."],
        ["6", "setup.sh", "Installs metrics-server from its upstream release manifest, then prints node/pod status and the ArgoCD initial admin password."],
        ["7", "Operator", "Runs kubectl apply -f Apps/sample-app/k8s/ (or wires up an ArgoCD Application for it) to deploy the sample workload."],
    ],
)

doc.add_heading2("4.3 Node group scaling flow")
doc.add_table(
    headers=["Step", "Actor / Component", "Action"],
    rows=[
        ["1", "Kubernetes scheduler", "Cannot place a pending pod because no node in the aws_eks_node_group.main has sufficient allocatable CPU/memory."],
        ["2", "Cluster Autoscaler (if installed in-cluster)", "Detects the unschedulable pod, calls autoscaling:SetDesiredCapacity against the node group's underlying Auto Scaling group, authenticated via the cluster_autoscaler IRSA role."],
        ["3", "AWS Auto Scaling / EKS", "Launches additional EC2 instances up to var.node_max_size (4 in dev, 10 in prod), respecting update_config.max_unavailable = 1 for any concurrent version rollout."],
        ["4", "New node(s)", "Join the cluster in the private subnets, register with kubelet, and become schedulable."],
        ["5", "Kubernetes scheduler", "Places the previously pending pod(s) on the new node(s)."],
        ["6", "Cluster Autoscaler", "After a cooldown period of sustained low utilization, calls autoscaling:TerminateInstanceInAutoScalingGroup to scale back down toward node_desired_size, never below node_min_size (1 in dev, 3 in prod)."],
    ],
)
doc.add_paragraph(
    "Note: this flow depends on the Cluster Autoscaler actually being "
    "installed in the cluster. As documented in Sections 2.3 and 3.4, "
    "Terraform provisions the cluster_autoscaler IRSA role, but no Helm "
    "release or ArgoCD Application for the Cluster Autoscaler controller "
    "itself ships in this repository — until one is added, the node group "
    "will only scale via manual terraform apply changes to "
    "node_desired_size/max_size/min_size, not automatically."
)

doc.add_heading2("4.4 HPA-driven pod scaling flow (sample app)")
doc.add_table(
    headers=["Step", "Actor / Component", "Action"],
    rows=[
        ["1", "metrics-server", "Continuously reports CPU/memory usage per pod to the Kubernetes metrics API."],
        ["2", "HPA controller (Apps/sample-app/k8s/hpa.yaml)", "Compares average CPU/memory utilization across sample-app pods against the 70%/80% targets on its reconciliation interval."],
        ["3", "HPA controller", "If utilization exceeds target, scales up by up to 2 pods per 60-second period (after a 60s stabilization window), bounded by maxReplicas: 10."],
        ["4", "Kubernetes scheduler", "Places new sample-app pods, respecting the Deployment's preferred pod anti-affinity across nodes."],
        ["5", "HPA controller", "If utilization drops, scales down by at most 1 pod per 60-second period after a 300s stabilization window, bounded by minReplicas: 2."],
    ],
)

# ---------------------------------------------------------------------------
# 5. Key algorithms & business logic
# ---------------------------------------------------------------------------
doc.add_heading1("5. Key algorithms & business logic")

doc.add_heading2("5.1 Cost-optimization heuristics — Scripts/cost_optimizer.py")
doc.add_paragraph(
    "The only genuinely algorithmic logic in this repository lives in the "
    "cost optimizer. check_idle_ec2() computes a simple 7-day rolling "
    "average of CloudWatch CPUUtilization datapoints (daily granularity, "
    "Period=86400) per running instance and flags anything averaging under "
    "a fixed 5.0% threshold as idle, at a flat assumed saving of $50/month "
    "regardless of instance type or size — a deliberately simple heuristic, "
    "not a cost-model lookup against actual instance pricing. "
    "check_unattached_ebs() flags every EBS volume in the available "
    "(unattached) state and estimates its cost at a flat $0.08/GB/month "
    "regardless of the volume's actual type-specific price (gp2 vs gp3 vs "
    "io2 pricing differs in reality; the script approximates with the gp3 "
    "rate). check_unused_elastic_ips() flags any Elastic IP address with "
    "neither an attached EC2 instance nor a network interface, at AWS's "
    "flat $3.65/month unassociated-EIP rate."
)

doc.add_heading2("5.2 IRSA least-privilege scoping")
doc.add_paragraph(
    "Each IRSA role's trust policy condition is the key design decision "
    "that makes this a least-privilege pattern rather than a broad grant: "
    "the StringEquals condition ties sts:AssumeRoleWithWebIdentity to one "
    "exact {oidc_provider}:sub value (a fully-qualified "
    "system:serviceaccount:<namespace>:<name>), so only a pod running "
    "under that specific ServiceAccount in that specific namespace can "
    "assume the role — a compromised or misconfigured pod running under a "
    "different ServiceAccount cannot. This is materially different from "
    "attaching these same permissions to the node group's IAM role "
    "(aws_iam_role.node_group in the eks module), which every pod on every "
    "node could reach via the instance metadata service unless additional "
    "IMDS hop-limit or Pod Identity controls were layered on."
)

doc.add_heading2("5.3 Node group update and rollout safety")
doc.add_paragraph(
    "aws_eks_node_group.main.update_config.max_unavailable = 1 (Terraform/"
    "Modules/eks/main.tf) bounds how many nodes EKS is allowed to take "
    "down simultaneously during a managed node group version or config "
    "update, regardless of node group size — a conservative, hardcoded "
    "choice that trades rollout speed for availability and is not "
    "currently exposed as a variable for callers who might want a larger "
    "batch size on bigger node groups."
)

doc.add_heading2("5.4 HPA scale-up/scale-down asymmetry")
doc.add_paragraph(
    "The sample app's HPA (Apps/sample-app/k8s/hpa.yaml) deliberately uses "
    "different behavior windows for scaling up versus down: a short 60s "
    "stabilization window and up-to-2-pods-per-60s on scale-up (react "
    "quickly to load), versus a longer 300s stabilization window and "
    "at-most-1-pod-per-60s on scale-down (avoid flapping/thrashing when "
    "load is noisy or intermittently dips). This is standard HPA "
    "behavior-tuning practice, applied concretely here rather than left at "
    "the Kubernetes defaults."
)

# ---------------------------------------------------------------------------
# 6. Validation & error handling
# ---------------------------------------------------------------------------
doc.add_heading1("6. Validation & error handling")
doc.add_bullets([
    "Terraform variable validation: both environment root modules' "
    "environment variable carries a validation block restricting it to "
    "dev/stage/prod, failing terraform plan/apply immediately with a clear "
    "error message otherwise.",
    "Plan-before-apply safety: terraform-apply.yaml always regenerates and "
    "re-validates the plan (fmt, validate, plan -out=tfplan) immediately "
    "before applying that exact plan file, rather than trusting a "
    "plan produced in a separate job/run — this closes the window for a "
    "stale or tampered plan to be applied.",
    "State locking: the DynamoDB terraform-state-lock table (provisioned "
    "by Terraform/backend.tf) prevents two concurrent terraform apply runs "
    "against the same state from corrupting it; the apply workflow's "
    "concurrency group (per environment, cancel-in-progress: false) adds a "
    "second layer of protection at the CI level by queuing rather than "
    "cancelling in-flight applies.",
    "Sequential environment applies: max-parallel: 1 on the apply "
    "workflow's matrix ensures dev and prod are never being applied at the "
    "same moment, reducing blast radius if something in the apply step "
    "itself misbehaves.",
    "Manual approval gate: GitHub Environment protection rules (if "
    "configured on the prod Environment) pause the apply job before "
    "touching production infrastructure.",
    "Container health checks: the Dockerfile's HEALTHCHECK and the "
    "Deployment's livenessProbe/readinessProbe against /health and /ready "
    "give Kubernetes (and Docker directly) a way to detect and restart an "
    "unhealthy sample-app container, and to hold it out of Service "
    "endpoints until /ready succeeds.",
    "ALB health checks: the Ingress's health-check annotations (interval "
    "15s, healthy threshold 2, unhealthy threshold 3 against /health) let "
    "the provisioned ALB stop routing traffic to unhealthy targets "
    "independently of Kubernetes' own probes.",
    "Known gap: no rollback automation exists for a bad terraform apply "
    "or a bad ArgoCD sync — recovery today relies on ArgoCD's self-heal "
    "(for drift/manual-edit correction, not for a genuinely broken chart "
    "version) or a manual terraform apply / git revert. There is no "
    "automated canary or progressive-delivery step (e.g. Argo Rollouts) "
    "for the sample app.",
    "Known gap: tflint and terraform validate catch syntactic and "
    "provider-schema issues, but nothing in CI checks for drift between "
    "Terraform state and real AWS resource state, or runs a policy/"
    "compliance scanner (e.g. tfsec, Checkov) against the Terraform code.",
])

# ---------------------------------------------------------------------------
# 7. Non-functional implementation details
# ---------------------------------------------------------------------------
doc.add_heading1("7. Non-functional implementation details")

doc.add_heading2("7.1 Security implementation specifics")
doc.add_bullets([
    "OIDC trust, not static keys, in two places: GitHub Actions authenticates "
    "via aws-actions/configure-aws-credentials with role-to-assume against "
    "GitHub's own OIDC provider, and in-cluster workloads authenticate via "
    "the EKS cluster's OIDC provider (aws_iam_openid_connect_provider.eks) "
    "for IRSA — the same federation pattern used at two different trust "
    "boundaries.",
    "Container-level hardening is enforced at both the image layer "
    "(non-root appuser baked into the Docker image) and the pod layer "
    "(runAsNonRoot/runAsUser/fsGroup and capabilities.drop: [ALL] in the "
    "Deployment's securityContext), so the restriction holds even if the "
    "manifest's securityContext were ever accidentally dropped from a "
    "future edit.",
    "State bucket lockdown: all four aws_s3_bucket_public_access_block "
    "flags are set true on the Terraform state bucket, in addition to "
    "default KMS encryption and versioning — state (which can contain "
    "sensitive attribute values) is never publicly reachable.",
])

doc.add_heading2("7.2 Performance / scaling considerations")
doc.add_bullets([
    "Per-AZ NAT Gateways (one per public subnet, not one shared NAT "
    "Gateway) remove a single-NAT-Gateway bottleneck/failure point for "
    "cross-AZ egress bandwidth, at the cost of one NAT Gateway's hourly + "
    "data-processing charge per AZ instead of one total.",
    "Prometheus retention is capped both by time (15d) and size (18GB) "
    "with a 20Gi backing PVC, so the observability stack's storage growth "
    "is bounded rather than unbounded.",
    "The sample app's resource requests (100m CPU/128Mi memory) versus "
    "limits (500m CPU/256Mi memory) give the scheduler a small, "
    "predictable bin-packing footprint per pod while still allowing each "
    "pod some burst headroom under the limit.",
    "Because dev's node group runs t3.medium (burstable, 2 vCPU/4GiB) "
    "against prod's m5.large (fixed performance, 2 vCPU/8GiB) sized 3-10 "
    "vs 1-4, the two environments are not performance-equivalent by "
    "design — dev is intentionally the cheaper, lower-throughput tier.",
])

# ---------------------------------------------------------------------------
# 8. Appendix
# ---------------------------------------------------------------------------
doc.add_heading1("8. Appendix")

doc.add_heading2("8.1 Repository module/file map")
doc.add_code_block(
"""Darviq-Eks/
  README.md
  Terraform/
    backend.tf                       # one-time bootstrap: state S3 bucket + DynamoDB lock table
    Modules/
      vpc/
        main.tf                      # VPC, IGW, public/private subnets, NAT GWs, route tables
        variables.tf
        outputs.tf                   # vpc_id, public_subnet_ids, private_subnet_ids
      eks/
        main.tf                      # EKS cluster, cluster IAM role, node group, node IAM role, OIDC provider
        variables.tf
        outputs.tf                   # cluster_name/endpoint/ca, oidc_provider_arn/url
      iam/
        main.tf                      # IRSA roles: ALB Controller, Cluster Autoscaler, External DNS
        variables.tf
        outputs.tf
        policies/
          alb-controller-policy.json # upstream AWS-published ALB Controller IAM policy
    Environments/
      dev/
        main.tf                      # calls vpc + eks modules only
        variables.tf
        terraform.tfvars             # aws_region, project_name, environment=dev
        .terraform.lock.hcl
      prod/
        main.tf                      # calls vpc + eks + iam modules; adds S3 backup bucket
        variables.tf
        terraform.tfvars             # environment=prod
        .terraform.lock.hcl
  Kubernetes/
    argocd/applications/
      monitoring.yaml                # ArgoCD Application: kube-prometheus-stack
      sealed-secrets.yaml            # ArgoCD Application: sealed-secrets
    monitoring/
      prometheus-values.yaml         # custom Helm values for kube-prometheus-stack
  Apps/
    sample-app/
      app.py                         # Flask app: /, /health, /ready
      Dockerfile                     # non-root, HEALTHCHECK, gunicorn
      requirements.txt
      k8s/
        deployment.yaml
        service.yaml
        ingress.yaml                 # ALB Ingress
        hpa.yaml                     # HorizontalPodAutoscaler
        networkpolicy.yaml           # default-deny-style NetworkPolicy
  Scripts/
    setup.sh                         # one-time cluster bootstrap (ArgoCD, metrics-server)
    cost_optimizer.py                # boto3 idle-resource / cost audit
  .github/workflows/
    terraform-plan.yaml              # fmt/validate/tflint/plan on PRs, via OIDC
    terraform-apply.yaml             # terraform apply on merge to main, via OIDC
  Docs/
    Darviq_Eks_High_Level_Design.docx
    Darviq_Eks_Low_Level_Design.docx
    docx_builder.py                  # shared doc-generation helper
    gen_hld.py, gen_lld.py           # generation scripts for the two docs above
""")

doc.add_heading2("8.2 Environment variable / configuration reference")
doc.add_table(
    headers=["Variable", "Where used", "Description"],
    rows=[
        ["AWS_ROLE_ARN", "GitHub Actions secret, both workflows", "IAM role assumed via GitHub OIDC for all Terraform/AWS operations in CI."],
        ["aws_region (tfvars)", "Terraform/Environments/<env>/terraform.tfvars", "Target AWS region; ap-south-1 in both shipped environments."],
        ["project_name (tfvars)", "Terraform/Environments/<env>/terraform.tfvars", "Resource-naming prefix; eks-platform in both environments."],
        ["environment (tfvars)", "Terraform/Environments/<env>/terraform.tfvars", "dev or prod; validated by a Terraform variable validation block."],
        ["ENVIRONMENT (pod env var)", "Apps/sample-app/k8s/deployment.yaml", "Injected via the Downward API from metadata.namespace; read by app.py's / route."],
        ["APP_VERSION (pod env var)", "Apps/sample-app/k8s/deployment.yaml", "Literal \"1.0.0\"; read by app.py's / route."],
        ["TF_VERSION", ".github/workflows/*.yaml", "Terraform CLI version pinned in CI (1.7.0)."],
        ["AWS_REGION (workflow env)", ".github/workflows/*.yaml", "Region used for the OIDC-authenticated AWS CLI/Terraform steps in CI (ap-south-1)."],
    ],
)

doc.add_heading2("8.3 Change history")
doc.add_table(
    headers=["Version", "Date", "Description"],
    rows=[
        [VERSION, DATE, "Initial low-level design document"],
    ],
)

doc.save("Darviq_Eks_Low_Level_Design.docx")
print("Saved Darviq_Eks_Low_Level_Design.docx")

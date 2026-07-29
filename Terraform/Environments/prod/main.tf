terraform {
  required_version = ">= 1.6.0"
  #backend "s3" {
  #  bucket         = "your-terraform-state-bucket"
  #  key            = "prod/eks-platform/terraform.tfstate"
  #  region         = "ap-south-1"
  #  dynamodb_table = "terraform-state-lock"
  #  encrypt        = true
  #}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "prod"
      ManagedBy   = "terraform"
      Owner       = "ravi-shekhar-reddy"
    }
  }
}

module "vpc" {
  source               = "../../Modules/vpc"
  project_name         = var.project_name
  cluster_name         = local.cluster_name
  vpc_cidr             = "10.1.0.0/16"
  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
  private_subnet_cidrs = ["10.1.10.0/24", "10.1.11.0/24", "10.1.12.0/24"]
  availability_zones   = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
}

module "eks" {
  source              = "../../Modules/eks"
  cluster_name        = local.cluster_name
  kubernetes_version  = "1.30"
  private_subnet_ids  = module.vpc.private_subnet_ids
  node_instance_types = ["m5.large"]
  node_desired_size   = 3
  node_max_size       = 10
  node_min_size       = 3
}

module "iam" {
  source            = "../../Modules/iam"
  cluster_name      = local.cluster_name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
}

# S3 bucket for backups
resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-prod-backups-${data.aws_caller_identity.current.account_id}"
  tags   = { Name = "platform-backups", Environment = "prod" }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  cluster_name = "${var.project_name}-${var.environment}"
}

output "cluster_name" { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "alb_controller_role" { value = module.iam.alb_controller_role_arn }

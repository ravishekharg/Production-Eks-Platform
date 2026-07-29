terraform {
  required_version = ">= 1.6.0"
  #backend "s3" {
  # bucket         = "your-terraform-state-bucket"
  # key            = "dev/eks-platform/terraform.tfstate"
  # region         = "ap-south-1"
  # dynamodb_table = "terraform-state-lock"
  # encrypt        = true
  #}
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "dev"
      ManagedBy   = "terraform"
      Owner       = "ravi-shekhar-reddy"
    }
  }
}

module "vpc" {
  source               = "../../Modules/vpc"
  project_name         = var.project_name
  cluster_name         = local.cluster_name
  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  availability_zones   = ["ap-south-1a", "ap-south-1b"]
}

module "eks" {
  source              = "../../Modules/eks"
  cluster_name        = local.cluster_name
  kubernetes_version  = "1.30"
  private_subnet_ids  = module.vpc.private_subnet_ids
  node_instance_types = ["t3.medium"]
  node_desired_size   = 2
  node_max_size       = 4
  node_min_size       = 1
}

locals {
  cluster_name = "${var.project_name}-${var.environment}"
}
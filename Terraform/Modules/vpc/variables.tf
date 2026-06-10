variable "project_name" {
  type        = string
  description = "Project name for resource naming"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name for subnet tags"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type = list(string)
}

variable "private_subnet_cidrs" {
  type = list(string)
}

variable "availability_zones" {
  type = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
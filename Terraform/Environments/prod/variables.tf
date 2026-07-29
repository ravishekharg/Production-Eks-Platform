variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "project_name" { type = string }
variable "environment" {
  type    = string
  default = "prod"
  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "Must be dev, stage, or prod."
  }
}
# Bootstrap this ONCE before using any environment backend:
# terraform -chdir=terraform/bootstrap apply

resource "aws_s3_bucket" "terraform_state" {
  bucket = "eks-platform-terraform-state-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }

  tags = { Name = "Terraform State", ManagedBy = "terraform" }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = { Name = "Terraform State Lock", ManagedBy = "terraform" }
}

data "aws_caller_identity" "current" {}

output "state_bucket_name" { value = aws_s3_bucket.terraform_state.id }
output "lock_table_name"   { value = aws_dynamodb_table.terraform_locks.name }
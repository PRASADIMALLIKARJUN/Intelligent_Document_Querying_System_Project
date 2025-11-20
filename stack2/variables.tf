variable "aws_region" {
  description = "AWS region for deploying resources"
  type        = string
  default     = "us-east-1"
}

variable "aurora_endpoint" {
  description = "Aurora cluster endpoint"
  type        = string
  default     = "bedrock-aurora-cluster.cluster-cjf0ebby2d5m.us-east-1.rds.amazonaws.com"
}

variable "aurora_secret_arn" {
  description = "Secrets Manager ARN for DB credentials"
  type        = string
  default     = "arn:aws:secretsmanager:us-east-1:413127593923:secret:bedrock-aurora-secret-qDS3w3"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for KB documents"
  type        = string
  default     = "s3-bucket-bedrock-project-malli"
}

variable "bedrock_kb_name" {
  description = "Name for the Bedrock Knowledge Base"
  type        = string
  default     = "intelligent-docs-kb-malli"
}

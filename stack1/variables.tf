variable "aws_region" {
  description = "AWS region for deploying resources"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_name" {
  description = "Name of the Aurora Postgres database"
  type        = string
  default     = "bedrockdatabasepostgres"
}

variable "db_username" {
  description = "Master username for the DB"
  type        = string
  default     = "adminusermalli"
}

variable "db_password" {
  description = "Master password for the DB"
  type        = string
  default     = "MalliStrongPass123!"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
  default     = "s3-bucket-bedrock-project-malli"
}

output "aurora_endpoint" {
  description = "Aurora cluster endpoint (host)"
  value       = aws_rds_cluster.aurora_cluster.endpoint
}

output "aurora_reader_endpoint" {
  description = "Aurora cluster reader endpoint (if available)"
  value       = aws_rds_cluster.aurora_cluster.reader_endpoint
  # reader_endpoint may be empty for some configurations; it's okay.
}

output "aurora_secret_arn" {
  description = "Secrets Manager ARN storing DB credentials"
  value       = aws_secretsmanager_secret.db_secret.arn
}

output "s3_bucket_name" {
  description = "S3 bucket name created for project"
  value       = aws_s3_bucket.project_bucket.id
}

output "vpc_id" {
  description = "VPC ID created for the project"
  value       = aws_vpc.bedrock_vpc.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs used by Aurora"
  value       = [
    aws_subnet.private_subnet_1.id,
    aws_subnet.private_subnet_2.id
  ]
}

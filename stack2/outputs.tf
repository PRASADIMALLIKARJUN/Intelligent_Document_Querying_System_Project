output "bedrock_role_arn" {
  description = "IAM Role ARN to attach to Bedrock Knowledge Base"
  value       = aws_iam_role.bedrock_access_role.arn
}

output "s3_bucket_name" {
  description = "S3 bucket used by the knowledge base"
  value       = var.s3_bucket_name
}

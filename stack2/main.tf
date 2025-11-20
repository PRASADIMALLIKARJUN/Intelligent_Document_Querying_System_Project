##############################################
# Provider
##############################################
provider "aws" {
  region = var.aws_region
}

##############################################
# IAM role for Bedrock to access S3 + Secrets
# (This role will be used by Bedrock Knowledge Base)
##############################################
data "aws_iam_policy_document" "bedrock_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com", ]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "bedrock_access_role" {
  name               = "${var.bedrock_kb_name}-bedrock-role"
  assume_role_policy = data.aws_iam_policy_document.bedrock_assume_role.json
  tags = {
    Name = "${var.bedrock_kb_name}-role"
  }
}

resource "aws_iam_policy" "bedrock_s3_secrets_policy" {
  name        = "${var.bedrock_kb_name}-s3-secrets-policy"
  description = "Allows Bedrock access to S3 bucket and Secrets Manager secret for knowledge base ingestion"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "S3ReadAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}",
          "arn:aws:s3:::${var.s3_bucket_name}/*"
        ]
      },
      {
        Sid = "SecretsManagerRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "${var.aurora_secret_arn}"
        ]
      },
      {
        Sid = "RDSDescribe"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances"
        ]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_policy" {
  role       = aws_iam_role.bedrock_access_role.name
  policy_arn = aws_iam_policy.bedrock_s3_secrets_policy.arn
}



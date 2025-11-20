##############################################
# Provider
##############################################
provider "aws" {
  region = var.aws_region
}

##############################################
# VPC
##############################################
resource "aws_vpc" "bedrock_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "bedrock-project-vpc"
  }
}

##############################################
# Subnets (2 private)
##############################################
resource "aws_subnet" "private_subnet_1" {
  vpc_id                  = aws_vpc.bedrock_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = false

  tags = {
    Name = "private-subnet-1"
  }
}

resource "aws_subnet" "private_subnet_2" {
  vpc_id                  = aws_vpc.bedrock_vpc.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = false

  tags = {
    Name = "private-subnet-2"
  }
}

##############################################
# DB Subnet Group
##############################################
resource "aws_db_subnet_group" "aurora_subnets" {
  name       = "bedrock-aurora-subnet-group"
  subnet_ids = [
    aws_subnet.private_subnet_1.id,
    aws_subnet.private_subnet_2.id
  ]

  tags = {
    Name = "aurora-subnet-group"
  }
}

##############################################
# Security Group for Aurora
##############################################
resource "aws_security_group" "aurora_sg" {
  name        = "aurora-sg"
  description = "Allow access to Aurora"
  vpc_id      = aws_vpc.bedrock_vpc.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # You can restrict to your IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

##############################################
# Aurora PostgreSQL Serverless v2
##############################################
resource "aws_rds_cluster" "aurora_cluster" {
  cluster_identifier      = "bedrock-aurora-cluster"
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"
  database_name           = var.db_name
  master_username         = var.db_username
  master_password         = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.aurora_subnets.name
  vpc_security_group_ids  = [aws_security_group.aurora_sg.id]
  skip_final_snapshot     = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2
  }

  tags = {
    Name = "bedrock-aurora-cluster"
  }
}

resource "aws_rds_cluster_instance" "aurora_instance" {
  identifier         = "aurora-instance-1"
  cluster_identifier = aws_rds_cluster.aurora_cluster.id
  instance_class     = "db.serverless"
  engine             = "aurora-postgresql"
}

##############################################
# S3 Bucket
##############################################
resource "aws_s3_bucket" "project_bucket" {
  bucket = var.s3_bucket_name

  tags = {
    Name = "bedrock-project-bucket"
  }
}

##############################################
# Store DB credentials in Secrets Manager
##############################################
resource "aws_secretsmanager_secret" "db_secret" {
  name = "bedrock-aurora-secret"
}

resource "aws_secretsmanager_secret_version" "db_secret_value" {
  secret_id = aws_secretsmanager_secret.db_secret.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    dbname   = var.db_name
    host     = aws_rds_cluster.aurora_cluster.endpoint
    port     = 5432
  })
}

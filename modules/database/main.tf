resource "aws_secretsmanager_secret" "db_credentials" {
  name = "${var.cluster_identifier}-credentials"
  description = "Credentials for ${var.cluster_identifier}"
}

resource "aws_secretsmanager_secret_version" "db_credentials_version" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.master_username
    password = var.master_password
    dbname   = var.database_name
  })
}

resource "aws_db_subnet_group" "aurora_subnet_group" {
  name       = "${var.cluster_identifier}-subnet-group"
  subnet_ids = var.subnet_ids
  tags = {
    Name = "${var.cluster_identifier}-subnet-group"
  }
}

resource "aws_security_group" "aurora_sg" {
  name        = "${var.cluster_identifier}-sg"
  description = "Allow Postgres access"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_identifier}-sg"
  }
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = var.cluster_identifier
  engine                  = var.engine
  database_name           = var.database_name
  master_username         = var.master_username
  master_password         = var.master_password
  db_subnet_group_name    = aws_db_subnet_group.aurora_subnet_group.name
  vpc_security_group_ids  = [aws_security_group.aurora_sg.id]
  skip_final_snapshot     = true

  serverless_v2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }
}

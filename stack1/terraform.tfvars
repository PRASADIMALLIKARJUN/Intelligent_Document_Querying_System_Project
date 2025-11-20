region = "us-east-1"

vpc_name = "bedrock-poc-vpc"
vpc_cidr = "10.0.0.0/16"

azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

enable_nat_gateway = true
single_nat_gateway = true

cluster_identifier = "my-aurora-serverless"
database_name      = "myapp"
master_username    = "dbadmin"

max_capacity = 2
min_capacity = 1

allowed_cidr_blocks = ["10.0.0.0/16"]

bucket_name_prefix = "bedrock-kb"

tags = {
  Terraform   = "true"
  Environment = "dev"
}

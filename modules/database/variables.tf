variable "cluster_identifier" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }

variable "database_name" { type = string, default = "myapp" }
variable "master_username" { type = string, default = "dbadmin" }
variable "master_password" { type = string, sensitive = true }

variable "max_capacity" { type = number, default = 2 }
variable "min_capacity" { type = number, default = 1 }

variable "allowed_cidr_blocks" { type = list(string), default = ["10.0.0.0/16"] }

variable "engine" { type = string, default = "aurora-postgresql" }
variable "engine_version" { type = string, default = null }

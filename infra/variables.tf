variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "key_pair_name" {
  description = "Name of the EC2 key pair (must already exist in AWS)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small"
}

variable "ebs_volume_size" {
  description = "Size of the EBS data volume in GB"
  type        = number
  default     = 20
}

variable "github_repo_url" {
  description = "HTTPS URL of the GitHub repository to clone on EC2"
  type        = string
  default     = "https://github.com/mrscrum/jira-simulator.git"
}

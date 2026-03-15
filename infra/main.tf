terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Data Sources ---

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_vpc" "default" {
  default = true
}

# --- Security Group ---

resource "aws_security_group" "jira_simulator" {
  name        = "jira-simulator-sg"
  description = "Security group for Jira Team Simulator EC2 instance"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "jira-simulator-sg"
  }
}

# --- IAM Role for EC2 (DLM permissions) ---

resource "aws_iam_role" "jira_simulator" {
  name = "jira-simulator-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "jira-simulator-ec2-role"
  }
}

resource "aws_iam_role_policy" "dlm_permissions" {
  name = "jira-simulator-dlm-policy"
  role = aws_iam_role.jira_simulator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSnapshot",
          "ec2:CreateSnapshots",
          "ec2:DeleteSnapshot",
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "ec2:EnableFastSnapshotRestores",
          "ec2:DescribeFastSnapshotRestores",
          "ec2:DisableFastSnapshotRestores",
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "jira_simulator" {
  name = "jira-simulator-instance-profile"
  role = aws_iam_role.jira_simulator.name
}

# --- DLM IAM Role ---

resource "aws_iam_role" "dlm_lifecycle" {
  name = "jira-simulator-dlm-lifecycle-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "dlm.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "dlm_lifecycle" {
  name = "jira-simulator-dlm-lifecycle-policy"
  role = aws_iam_role.dlm_lifecycle.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSnapshot",
          "ec2:CreateSnapshots",
          "ec2:DeleteSnapshot",
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "ec2:EnableFastSnapshotRestores",
          "ec2:DescribeFastSnapshotRestores",
          "ec2:DisableFastSnapshotRestores",
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "*"
      }
    ]
  })
}

# --- EBS Data Volume ---

resource "aws_ebs_volume" "data" {
  availability_zone = data.aws_availability_zones.available.names[0]
  size              = var.ebs_volume_size
  type              = "gp3"
  encrypted         = true

  tags = {
    Name = "jira-simulator-data"
  }
}

# --- EC2 Instance ---

resource "aws_instance" "jira_simulator" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.jira_simulator.id]
  iam_instance_profile   = aws_iam_instance_profile.jira_simulator.name
  availability_zone      = data.aws_availability_zones.available.names[0]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Install Docker
    dnf update -y
    dnf install -y docker git
    systemctl enable docker
    systemctl start docker

    # Install Docker Compose plugin
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    # Update Docker Buildx (compose build requires >= 0.17.0)
    curl -SL "https://github.com/docker/buildx/releases/download/v0.19.3/buildx-v0.19.3.linux-amd64" \
      -o /usr/local/lib/docker/cli-plugins/docker-buildx
    chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

    # Install Node.js 20 (for frontend build)
    curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
    dnf install -y nodejs

    # Install and enable fail2ban
    dnf install -y fail2ban
    systemctl enable fail2ban
    systemctl start fail2ban

    # Create app directory and clone repo
    mkdir -p /app
    git clone ${var.github_repo_url} /app/jira-simulator

    # Create empty .env with secure permissions
    touch /app/jira-simulator/.env
    chmod 600 /app/jira-simulator/.env

    # Wait for EBS volume to attach
    while [ ! -e /dev/xvdf ] && [ ! -e /dev/nvme1n1 ]; do
      sleep 1
    done

    # Determine device name
    if [ -e /dev/nvme1n1 ]; then
      DEVICE=/dev/nvme1n1
    else
      DEVICE=/dev/xvdf
    fi

    # Format if new (check for existing filesystem)
    if ! blkid $DEVICE; then
      mkfs.ext4 $DEVICE
    fi

    # Mount the data volume
    mkdir -p /data
    mount $DEVICE /data

    # Add to fstab for persistence
    UUID=$(blkid -s UUID -o value $DEVICE)
    if ! grep -q "$UUID" /etc/fstab; then
      echo "UUID=$UUID /data ext4 defaults,nofail 0 2" >> /etc/fstab
    fi

    # Add ec2-user to docker group
    usermod -aG docker ec2-user

    # Set ownership so ec2-user can git pull and manage .env
    chown -R ec2-user:ec2-user /app/jira-simulator
    chown ec2-user:ec2-user /data
    git config --global --add safe.directory /app/jira-simulator

    # Build frontend
    cd /app/jira-simulator/frontend
    npm ci
    npm run build

    # Start application
    cd /app/jira-simulator
    docker compose up -d
  EOF

  tags = {
    Name = "jira-simulator"
  }
}

# --- Attach EBS Volume ---

resource "aws_volume_attachment" "data" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.jira_simulator.id
}

# --- Elastic IP ---

resource "aws_eip" "jira_simulator" {
  instance = aws_instance.jira_simulator.id
  domain   = "vpc"

  tags = {
    Name = "jira-simulator-eip"
  }
}

# --- DLM Snapshot Policy ---

resource "aws_dlm_lifecycle_policy" "snapshots" {
  description        = "Daily snapshots for jira-simulator data volume"
  execution_role_arn = aws_iam_role.dlm_lifecycle.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]

    target_tags = {
      Name = "jira-simulator-data"
    }

    schedule {
      name = "Daily snapshot"

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["02:00"]
      }

      retain_rule {
        count = 7
      }

      tags_to_add = {
        SnapshotCreator = "DLM"
        Project         = "jira-simulator"
      }

      copy_tags = true
    }
  }

  tags = {
    Name = "jira-simulator-snapshot-policy"
  }
}

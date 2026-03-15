# Jira Team Simulator

A multi-team Jira activity simulator that emulates how real engineering teams work, including realistic dysfunctions, handoffs, and cross-team dependencies. Generates authentic Jira data patterns for stress-testing a Sprint Risk Analyzer tool.

**Current stage:** Stage 1 — Data Model (database layer implemented, no API endpoints yet)

## Prerequisites

- AWS account with an EC2 key pair created
- GitHub account
- Jira Cloud instance with API token
- OpenAI API key
- Terraform >= 1.5 installed locally
- Docker and Docker Compose installed locally (for dev)
- Node.js 20+ and Python 3.12+ (for local development)

## Infrastructure Setup

### 1. Clone and configure

```bash
git clone https://github.com/mrscrum/jira-simulator.git
cd jira-simulator
```

### 2. Create Terraform variables

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
# Edit infra/terraform.tfvars with your AWS region and key pair name
```

### 3. Provision AWS resources

```bash
cd infra
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
terraform init
terraform plan    # Review the plan
terraform apply   # Apply after review
```

This creates: EC2 (t3.small), EBS (20GB gp3 encrypted), Elastic IP, DLM snapshot policy (daily, 7-day retention), security group (22/80/443), IAM role.

### 4. Note the outputs

After `terraform apply`, note:
- `elastic_ip` — the public IP of your instance
- `ssh_command` — ready-to-use SSH command
- `ebs_volume_id` — for reference

### 5. Configure the EC2 instance

```bash
# SSH into the instance
ssh -i ~/.ssh/jira_simulator.pem ec2-user@<ELASTIC_IP>

# Populate the .env file
sudo nano /app/jira-simulator/.env
# Add all variables from .env.example with real values
```

### 6. Add GitHub Actions secrets

In the GitHub repo settings, add these secrets:
- `EC2_HOST` — the Elastic IP from Terraform output
- `EC2_USER` — `ec2-user`
- `SSH_PRIVATE_KEY` — contents of your `.pem` file

## Local Development

```bash
cp .env.example .env
# Fill in .env with your values

docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Backend:  http://localhost:8000
# Frontend: http://localhost:5173 (when running vite dev separately)
# API docs: http://localhost:8000/docs
```

## Project Structure

See `AGENTS.md` for the complete directory layout and domain model.

## Data Model

Stage 1 implements the full SQLAlchemy data model with 10 tables:

- **Organization** → has many Teams
- **Team** → has Members, Workflow, DysfunctionConfig, Sprints, Issues
- **Member** → team member with role, capacity, WIP limits
- **Workflow** → ordered sequence of WorkflowSteps (one per team)
- **WorkflowStep** → Jira status mapping with role, wait time, WIP contribution
- **TouchTimeConfig** → per step/issue-type/story-points time distribution
- **DysfunctionConfig** → per-team dysfunction probabilities (one per team)
- **Sprint** → sprint with dates, velocity tracking, scope change tracking
- **Issue** → internal simulation state with Jira mapping, blocking, worker tracking

Database uses SQLite with WAL mode and foreign keys enabled. Alembic manages migrations.

## Running Tests

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -v
.venv/bin/ruff check app/ tests/
```

## Current Limitations (Stage 1)

- No API endpoints (only /health)
- Frontend is a placeholder ("coming soon")
- No simulation engine, no Jira integration
- HTTPS not configured (HTTP only)
- No CRUD operations — data model only

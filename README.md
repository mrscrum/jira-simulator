# Jira Team Simulator

A multi-team Jira activity simulator that emulates how real engineering teams work, including realistic dysfunctions, handoffs, and cross-team dependencies. Generates authentic Jira data patterns for stress-testing a Sprint Risk Analyzer tool.

**Current stage:** Stage 3 — Jira Integration Layer (complete, pending UAT)

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

## Environment Variables

In addition to the base variables in `.env.example`, Stage 3 adds:

| Variable | Description | Default |
|---|---|---|
| `ALERT_EMAIL_FROM` | SES-verified sender email for alerts | `""` (alerting disabled) |
| `ALERT_EMAIL_TO` | Recipient email for alerts | `""` (alerting disabled) |
| `AWS_SES_REGION` | AWS region for SES | `us-east-1` |

## Local Development

```bash
cp .env.example .env
# Fill in .env with your values

docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Backend:  http://localhost:8000
# Frontend: http://localhost:5173 (when running vite dev separately)
# API docs: http://localhost:8000/docs
```

## API Endpoints

### Jira Integration (Stage 3)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/jira/bootstrap/{team_id}` | Bootstrap Jira project for a team |
| `GET` | `/api/jira/bootstrap/{team_id}/status` | Get bootstrap status |
| `GET` | `/api/jira/health` | Jira connectivity health check |
| `GET` | `/api/jira/queue/status` | Write queue status |
| `POST` | `/api/jira/queue/retry-failed` | Retry failed queue entries |
| `GET` | `/api/jira/projects/{project_key}/statuses` | Get project statuses from Jira |

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (`{"status":"ok","stage":"3"}`) |

## Data Model

The SQLAlchemy data model spans 13 tables across two layers:

**Simulation (Stage 1):** Organization, Team, Member, Workflow, WorkflowStep, TouchTimeConfig, DysfunctionConfig, Sprint, Issue

**Jira Integration (Stage 3):** JiraConfig (key-value store), JiraWriteQueueEntry (persistent queue), JiraIssueMap (issue→Jira key mapping), JiraIssueLink (cross-team link tracking)

Database uses SQLite with WAL mode and foreign keys enabled. Alembic manages migrations (7 migrations: 001-007).

## Running Tests

```bash
# Inside Docker (recommended)
docker compose exec backend pip install pytest pytest-asyncio ruff boto3
docker compose exec backend python -m pytest tests/ -v
docker compose exec backend ruff check app/ tests/

# Integration tests (requires real Jira instance)
INTEGRATION_TESTS=true docker compose exec backend python -m pytest tests/integration/ -v
```

## Project Structure

See `AGENTS.md` for the complete directory layout and domain model.

## Current Limitations (Stage 3)

- No simulation engine yet (Stage 4)
- Frontend is a placeholder ("coming soon")
- No CRUD API endpoints for domain entities (organizations, teams, etc.)
- HTTPS not configured (HTTP only)
- Alerting requires AWS SES setup (no-op when unconfigured)

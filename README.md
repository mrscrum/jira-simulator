# Jira Team Simulator

A multi-team Jira activity simulator that emulates how real engineering teams work, including realistic dysfunctions, handoffs, and cross-team dependencies. Generates authentic Jira data patterns for stress-testing a Sprint Risk Analyzer tool.

**Current baseline:** Distribution-based simulation, precomputed sprint schedules, Jira write
queue, and configuration UI are implemented, but end-to-end real-time Jira synchronization is
still partial. See [Requirements and Functionality Map](docs/requirements-functionality-map.md)
for the assessed boundaries and gaps.

**Approved future plan:** The concise requirements, architecture, and milestone roadmap for the
additive v2 live simulator are in [docs/v2/high-level-plan.md](docs/v2/high-level-plan.md), with
milestone status under [backlog/v2/](backlog/v2/README.md). These are planning artifacts only; none of the v2 behavior,
including Codex control or Jira-side manual-intervention ingestion, is implemented beyond the
local persistence shell described below.

## V2 persistence shell

The first additive v2 slice is implemented locally. A fully resolved canonical Scrum blueprint can
be atomically persisted as an isolated `v2_teams` aggregate with one immutable blueprint, initial
run, and runtime shell. Revision `013` adds only `v2_*` tables and can downgrade to `012`; it does
not alter v1 API behavior or invoke Jira/OpenAI.

From `backend/`, run:

```bash
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q
../.venv/bin/python -B -m ruff check --no-cache .
```

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

The generated OpenAPI schema currently exposes 76 operations. The main groups are team/member/
workflow configuration, timing templates, Jira bootstrap and queue health, simulation controls,
sprint scheduling, scheduled-event inspection, and diagnostics. Use `/docs` for the complete live
contract.

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
| `GET` | `/health` | Health check (`{"status":"ok","stage":"4"}`) |

## Data Model

SQLAlchemy metadata currently defines 29 tables covering core team/workflow state, Jira queue and
mapping state, distribution/move-left configuration, timing templates, precomputation runs,
scheduled events, audit records, and the isolated four-table v2 persistence shell. Alembic has 13
migrations (`001`–`013`).

SQLite support enables WAL mode and foreign keys. However, the current production Compose file
forces PostgreSQL and stores it in a Docker named volume; this conflicts with the project rule that
production SQLite must live at `/data/simulator.db` on EBS. Treat persistence as unresolved until
that deployment decision is explicitly reconciled.

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

## Current Limitations

- Precomputed issue outcomes are not reduced back into persistent internal issue state.
- Newly created Jira sprint IDs are not available when add/start/complete events are generated.
- Event dispatch does not enforce sprint activation or per-team pause/deactivation.
- The advertised simulation acceleration controls do not scale the active scheduled-event path.
- Dysfunction and cross-team dependency effects are configuration/data only.
- Real-Jira integration tests are skipped in normal local and CI runs.
- The frontend has broad functionality but only two automated tests.
- The API has no authentication and Nginx has no working TLS configuration.
- Manual changes made directly in Jira are not reliably ingested into internal simulation state.
- Alerting requires AWS SES setup and is a no-op when unconfigured.

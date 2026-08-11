# Jira Team Simulator

A multi-team Jira activity simulator that emulates how real engineering teams work, including realistic dysfunctions, handoffs, and cross-team dependencies. Generates authentic Jira data patterns for stress-testing a Sprint Risk Analyzer tool.

**Current baseline:** Distribution-based simulation, precomputed sprint schedules, Jira write
queue, and configuration UI are implemented, but end-to-end real-time Jira synchronization is
still partial. See [Requirements and Functionality Map](docs/requirements-functionality-map.md)
for the assessed boundaries and gaps.

**Approved future plan:** The concise requirements, architecture, and milestone roadmap for the
additive v2 live simulator are in [docs/v2/high-level-plan.md](docs/v2/high-level-plan.md), with
milestone status under [backlog/v2/](backlog/v2/README.md). The local v2 implementation is limited
to the persistence spine and deterministic kernel described below; a simulation engine, Codex
control, transport delivery, and Jira-side manual-intervention ingestion are not implemented.

## V2 persistence spine

The first two additive v2 persistence slices are implemented locally. A fully resolved canonical Scrum blueprint can
be atomically persisted as an isolated `v2_teams` aggregate with one immutable blueprint, initial
run, and runtime shell. Revision `013` owns that four-table shell. Revision `014` adds explicit
runtime versions plus ordered activity, immutable ground-truth, and generic pending projection
intent ledgers; it independently downgrades to `013`. Neither revision alters v1 API behavior or
invokes Jira/OpenAI. Aware boundary, availability, runtime, and ledger offsets are
normalized to UTC in typed state while the validated canonical input bytes remain the persisted
document and hash source; naive instants are rejected. The canonical document is immutable after
construction, and the wire boundary rejects scalar type coercion plus every non-string JSON object
key recursively instead of accepting `json.dumps` key coercion.

`SqlAlchemyV2UnitOfWork` advances a team/run runtime with one optimistic compare-and-swap and
commits all three caller-ordered ledger tuples in the same transaction. Semantic replay is a stable
no-op only for identical canonical content, including when a concurrent insert wins after lookup;
conflicts and stale writers roll back the whole slice without leaking a raw database uniqueness
error. Public drafts revalidate deterministic identity, canonical bytes/hash, type identifiers,
versions, and aware instants on direct construction, replacement, and before a UOW opens a session.
Each ledger pages by its own exclusive append-sequence cursor. Projection intents are transport
neutral and remain `PENDING`; delivery adapters are deliberately outside this unit of work. Every
public v2 persistence import order registers all seven v2 tables before schema creation.

From `backend/`, run:

```bash
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q
../.venv/bin/python -B -m ruff check --no-cache .
```

## V2 deterministic decision kernel

The first pure v2 kernel slice is implemented locally. `HMAC_SHA256_U53_V1` derives stable
team/run/member/sprint/item/visit/dependency/rework UUIDv5 identities from the existing semantic
namespace and produces immutable unit draws from an NFC-normalized root-seed key plus an exact
canonical decision coordinate. Draws are independent of process, call order, database identity,
clock time, and mutable RNG state. The closed creation-kind and decision enums reject raw strings,
and current decision entities require semantic UUIDs rather than catalog/date strings. Every
ordinal, occurrence, and draw index is a true integer in `0..2^53-1`; fixed-coordinate decisions
require occurrence zero, while only the documented eligibility/forced/arrival decisions accept a
positive caller-supplied occurrence. `UniformDraw` construction is sealed behind the keyed stream,
so direct construction and `dataclasses.replace` cannot forge canonical or digest provenance.

The same slice provides pure bounded dwell and touch sampling. Dwell uses the configured
minimum/p25/p50/p99/maximum anchors with exact endpoints and log1p-space interpolation; touch uses
the exact bounded linear formula. Both accept only explicit finite unit draws, preserve immutable
input/result provenance, and consume no persisted occurrence. This slice adds no database table,
migration, scheduler, engine, or external adapter. Direct construction and replacement of a
`DurationSample` also revalidate that sampled hours equal the exact formula for its retained
parameters and draw.

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

SQLAlchemy metadata currently defines 32 tables covering core team/workflow state, Jira queue and
mapping state, distribution/move-left configuration, timing templates, precomputation runs,
scheduled events, audit records, and the isolated seven-table v2 persistence spine. Alembic has 14
migrations (`001`–`014`).

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
- V2 currently provides persistence contracts plus pure deterministic decision/timing primitives;
  it has no occurrence allocator, live tick engine, business-calendar kernel, scheduler wiring,
  projection worker, API routes, Jira/OpenAI adapter, or live-provider validation.

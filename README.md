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

Four additive v2 persistence slices are implemented locally. A fully resolved canonical
Scrum blueprint can be atomically persisted as an isolated `v2_teams` aggregate with one immutable
blueprint, initial run, and runtime shell. Revision `013` owns that four-table shell. Revision `014` adds explicit
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
public v2 persistence import order registers all 18 v2 tables before schema creation.

Revision `015` adds detached, immutable authoritative Scrum state without changing lifecycle state
or taking transaction ownership. The relational state covers semantic member identities,
run-scoped availability overlays and business-date consumption, work items and immutable factors,
sprints and scope, status visits and exact deterministic timing provenance, explicit semantic
counters, and committed natural-decision eligibility. Every run-derived child uses composite
team/run ownership, duration state uses checked signed 64-bit integer microseconds, and semantic
coordinates use true safe integers. Partial uniqueness enforces one active sprint, one current
scope row per item, and one open visit per item.

The reviewed boundary seals every Task 5 value against ordinary subclass, replacement, mapping,
copy, and reconstruction mutation paths. Status samples are created only from exact trusted Task 3
draws, then reauthenticated on restart against the persisted blueprint seed, team/run/visit
coordinates, timing cell, sampler versions, parameters, formulas, and exact half-even
hours-to-microseconds conversion. Semantic counters and natural evaluations carry typed
work-item/member owner columns with matching revision-015 composite foreign keys and owner-shape
checks. SQLite represents bound booleans as integers, so strict boolean rejection is guaranteed by
the public domain and mapper validation boundary; database checks separately reject non-integer
numeric storage classes and out-of-range values.

`SqlAlchemyScrumStateMapper` accepts a caller-owned SQLAlchemy `Session` and sparse tuple-only
after-images. Under `no_autoflush`, it resolves unchanged persisted owners and visit samples omitted
from the write set, validates the complete merged snapshot against persisted blueprint authority
before Task 5 DML, flushes constraints without commit/rollback, and returns detached values in
deterministic semantic order. It rejects mixed or missing parents, invalid member positions,
route/status/activity mismatches, unsupported natural owners, duplicate semantic coordinates, and
conflicting active/open/current after-images before writing. Both `add` and `load` require an empty
caller ORM unit of work (`new`, `dirty`, and `deleted`) before authority SQL so pending objects cannot
be implicitly flushed or reflected in the returned snapshot. `add` also rejects a coordinate-free
empty write set before SQL; callers with no Task 5 after-images skip the mapper.

All Task 5 authority and state reads refresh matching ORM identities from the current transaction's
database view instead of trusting clean, unexpired caller cache entries. Persisted team/run/
blueprint/sample corruption and deleted run authority therefore reject, while valid external state
updates appear in the complete returned snapshot without expiring unrelated cached identities.
Member-only candidate reads use the same boundary. If a complete visit/sample after-image restores
an externally cascade-deleted same-key visit and sample, the mapper detaches only those
confirmed-missing target-local identities before insertion, avoiding stale-row errors and
SQLAlchemy identity-conflict warnings while preserving unrelated caller cache entries.

Status visits use an exact `str | None` activity key. Approved null-activity route steps persist and
restart only as zero-touch visits with no member owner, while activity-bearing steps require their
exact activity/member binding. Every complete snapshot and newly inserted visit has exactly one
blueprint-authenticated sample; a sparse update to an existing visit may omit only an unchanged
sample that the mapper has loaded and reauthenticated. Required-work hashes are exact plain
lower-case SHA-256 strings. Trusted sample creation exactly revalidates every nested deterministic
draw scalar and the complete keyed HMAC, including low-bit changes and equality-spoofing
subclasses. Retained dwell/touch unit values are exact finite built-in floats in `[0, 1]`, so
stateful float subclasses reject before SQL binding. The original Task 5 `add` path narrowly updates
existing visit after-images; the Task 6 authoritative path described below applies reviewed sparse
after-image semantics without changing that public compatibility boundary.
Aware offset instants normalize to UTC while naive instants reject. The canonical resolved blueprint
remains the only home for names, roles, configured capacity/WIP, responsibilities, proficiency,
routes, timing grids, calendar, and policy configuration. Revision `015` independently downgrades to
populated revision `014` without changing its legacy, runtime, or live-ledger rows. Task 6 consumes
that schema unchanged and adds no allocator, lifecycle transition, scheduler, or external delivery.

## V2 authoritative atomic slices

Task 6 was committed as `4cfaa65` (`feat(v2): commit scrum state atomically`). Review-fix round 1 is
commit `6bac956` (`fix(v2): enforce authoritative after-image identity`). Review-fix round 2 now
normalizes every aware instant retained inside an immutable committed authoritative result to exact
UTC while preserving naive rejection, exact nested types, and caller-owned frozen input. Its
round-2 verification matrix and direct probe are GREEN, and independent Ultra re-review remains
pending.
`AuthoritativeTickSliceCommit` wraps the existing live-slice command with sparse authoritative Scrum
after-images, explicit safe-integer semantic-counter ranges, and eligible natural-decision claims.
The SQLAlchemy unit of work validates the exact immutable command before session creation, opens one
short session, compare-and-swaps runtime, applies touched after-images, advances counters, resolves
natural eligibility, appends ordered activity/ground-truth/pending-projection rows, flushes, and
commits once. Every recognized stale writer, semantic conflict, database error, final-flush failure,
or commit failure rolls back the complete slice.

Claimed sprint/item/visit coordinates retain the existing semantic-ID derivations, while ordinary
sparse updates to already persisted rows consume no allocation again. New work-item owners receive
zero-valued visit/cancellation child counters. Blueprint members and their unavailability counters
must already exist from Task 5/bootstrap; Task 6 rejects missing established members instead of
recreating their identity or counter history. Advanced allocation replay is accepted only when the
entire submitted state, all claims, natural occurrences, and ledger drafts are already persisted and
exact. Identity/history collisions and changed replay raise typed conflicts and roll back the whole
slice. Projection delivery stays strictly post-commit. Task 6 creates no revision `016`, calls no
external adapter/client, and implements no probability, eligibility, transition, labor-allocation,
or live-flow mechanics.

The retained round-2 verification records 252 focused tests, 1037 all-v2 tests with one baseline
warning, and 1555 full-backend tests with 43 skipped and 15 baseline warnings. Ruff, static/shape
checks, the Alembic sole-head/empty-branch/linear-history checks, and the no-migration diff are clean.

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
positive caller-supplied occurrence. The six Task 3 value types are frozen and slotted, expose no
instance mapping, preserve identity across shallow/deep copy, and reject pickle/reduce
reconstruction. `UniformDraw` construction remains sealed behind the keyed stream, so direct
construction and `dataclasses.replace` cannot forge canonical or digest provenance.

The same slice provides pure bounded dwell and touch sampling. Dwell uses the configured
minimum/p25/p50/p99/maximum anchors with exact endpoints and log1p-space interpolation; touch uses
the exact bounded linear formula. Both accept only explicit finite unit draws, preserve ordinary
immutable input/result provenance, and consume no persisted occurrence. This slice adds no database
table, migration, scheduler, engine, or external adapter. Direct construction and replacement of a
`DurationSample` also revalidate that sampled hours equal the exact formula for its retained
parameters and draw. This ordinary immutability contract does not claim resistance to deliberate
low-level mutation through `object.__setattr__`.

## V2 dual-clock business calendar

The reviewed deterministic kernel also contains a pure, immutable business-calendar boundary.
`BusinessCalendar` is constructed only from a resolved calendar blueprint plus its exact IANA
timezone. It normalizes aware inputs and results to UTC, calculates exact calendar and business
elapsed time, adds business durations across workdays/holidays, and exposes business-date,
working-interval, next-working-instant, and business-day-end queries. Local work and cadence
boundaries are resolved through UTC round trips so nonexistent or ambiguous DST wall times reject
instead of silently choosing a fold. If an otherwise aware instant or local boundary cannot be
represented at Python's minimum/maximum datetime after a zone conversion, every public calendar
operation raises the same stable domain `ValueError` instead of leaking `OverflowError`.

Fixed sprint cadence remains independent of business-calendar adjustment: each ordinal retains the
original local anchor clock across DST and is never shifted for a weekend or holiday. Pure
`US_FEDERAL_V1` helpers derive the starter year from the resolved team's explicit IANA timezone,
then materialize the documented observed federal holidays over a bounded full-year horizon. Before
extension, the complete horizon bounds and exact ordered holiday tuple are authenticated against
the frozen policy. A stale request catches up in ten-year blocks until at least two complete local
years remain; replay is an identity-preserving no-op. Timezone inputs must be keys exposed by the
runtime IANA database, and loadable pseudo-zones such as `posixrules` reject. These helpers persist
nothing and do not implement sprint lifecycle, capacity, scheduling, or external delivery.

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

SQLAlchemy metadata currently defines 43 tables covering core team/workflow state, Jira queue and
mapping state, distribution/move-left configuration, timing templates, precomputation runs,
scheduled events, audit records, and the isolated 18-table v2 persistence/state boundary. Alembic
has 15 migrations (`001`–`015`).

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
- V2 currently provides persistent work/sprint/member/status-visit contracts, pure deterministic
  decision/timing/calendar primitives, and the atomic Task 6 state/counter/evaluation/live-ledger
  commit boundary. It has no mechanical eligibility or lifecycle allocator, live tick engine,
  scheduler wiring, projection worker, API routes, Jira/OpenAI adapter, or live-provider validation.

# Jira Team Simulator — Complete Handoff Document

## Project Overview

A **multi-team Jira activity simulator** that emulates how real engineering teams work — including realistic dysfunctions, handoffs, and cross-team dependencies. Its primary purpose is to generate **authentic Jira data patterns** for stress-testing a Sprint Risk Analyzer tool.

**Repository**: https://github.com/mrscrum/jira-simulator  
**Live instance**: http://98.89.183.224 (EC2 t3.small, Amazon Linux 2023)  
**Health check**: http://98.89.183.224/health → `{"status":"ok","stage":"4"}`

---

## Tech Stack

### Backend
- **Python 3.12+**, **FastAPI 0.115+**, **SQLAlchemy 2.0+**, **Alembic** (migrations)
- **SQLite** (local/dev/prod on EC2) / **PostgreSQL 16** (Docker Compose prod option)
- **APScheduler 3.10+** (background tick engine)
- **Pydantic v2** (validation), **httpx** (async HTTP), **boto3** (AWS SES)
- **OpenAI SDK** (LLM for backlog content generation — NOT Anthropic)
- **pytest + pytest-asyncio** (518 tests), **ruff** (linting)

### Frontend
- **React 18.3+**, **TypeScript 5.7**, **Vite 6.0+**, **Tailwind CSS 4.2+**
- **shadcn/ui 4.0+** (component library), **React Query 5.90+** (server state)
- **Plotly.js 3.4+** (boxplot visualization), **@dnd-kit** (drag-and-drop)
- **vitest 2.1+** + **React Testing Library**

### Infrastructure
- **Terraform 1.5+** (AWS: EC2, EBS 20GB gp3 encrypted, DLM snapshots, EIP, SG, IAM)
- **Docker + Docker Compose** (prod + dev configs)
- **Nginx** (reverse proxy + static files)
- **GitHub Actions** (CI/CD: pytest → ruff → vitest → SSH deploy)

---

## Access Keys & Secrets Required

All stored in `.env` on EC2 at `/app/jira-simulator/.env` (chmod 600). Template in `.env.example`:

| Variable | Purpose |
|---|---|
| `JIRA_BASE_URL` | Jira Cloud instance URL (e.g., `https://yourorg.atlassian.net`) |
| `JIRA_EMAIL` | Jira API user email |
| `JIRA_API_TOKEN` | Jira API token (Basic auth) |
| `OPENAI_API_KEY` | OpenAI GPT key (backlog content generation) |
| `DATABASE_URL` | `sqlite:////data/simulator.db` (EC2) or `sqlite:///./data/simulator.db` (local) |
| `ENVIRONMENT` | `production` or `development` |
| `LOG_LEVEL` | `INFO`, `DEBUG`, `WARNING` |
| `TICK_INTERVAL_MINUTES` | Simulation tick frequency (default: 30) |
| `ALERT_EMAIL_FROM` | AWS SES sender email (optional) |
| `ALERT_EMAIL_TO` | Alert recipient email (optional) |
| `AWS_SES_REGION` | SES region (default: us-east-1) |

**GitHub Secrets** (for CI/CD): `EC2_HOST`, `EC2_USER`, `SSH_PRIVATE_KEY`  
**SSH Key**: `~/.ssh/jira_simulator.pem` (for `ssh ec2-user@98.89.183.224`)

---

## Project Structure

```
jira-simulator/
├── AGENTS.md                     # Master project spec (dev flow, domain model, rules)
├── README.md                     # Setup + deploy instructions
├── agent_instruction.md          # Agent handoff context (current state, key files, next task)
├── changelog.md                  # Append-only change log
├── assumptions.md                # Design decisions audit trail
├── stage3.md, stage4.md          # Stage requirement specs
├── docker-compose.yml            # Production (PostgreSQL, backend, nginx)
├── docker-compose.dev.yml        # Dev overrides (hot reload, volume mounts)
├── .env.example                  # Environment variable template
├── .github/workflows/deploy.yml  # CI/CD pipeline
├── infra/                        # Terraform (main.tf, variables.tf, outputs.tf)
├── nginx/nginx.conf              # Reverse proxy config
├── backlog/                      # Task tracking per stage (8 stage files)
├── docs/
│   ├── simulation-engine-rewrite-requirements.md  # Stage 5 rewrite spec
│   └── plan/phase-01..10*.md     # 10-phase implementation plan
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini + alembic/    # 8 migrations (001-008)
│   ├── app/
│   │   ├── main.py               # FastAPI app + lifespan
│   │   ├── config.py             # Pydantic Settings
│   │   ├── database.py           # SQLAlchemy engine + session
│   │   ├── models/               # 19 SQLAlchemy models
│   │   ├── schemas/              # 10 Pydantic schema files
│   │   ├── api/routers/          # 12 API routers (50+ endpoints)
│   │   ├── engine/               # Simulation engine
│   │   │   ├── simulation.py     # Tick orchestrator (state machine)
│   │   │   ├── calendar.py       # Business days, timezones, holidays
│   │   │   ├── capacity.py       # WIP tracking, worker assignment
│   │   │   ├── issue_state_machine.py  # 9 issue states, transitions
│   │   │   ├── sprint_lifecycle.py     # Sprint phases, velocity
│   │   │   ├── backlog.py        # Depth maintenance, story generation
│   │   │   ├── distributions.py  # Touch-time sampling
│   │   │   ├── precompute.py     # Pre-run computations
│   │   │   ├── workflow_engine.py # Per-issue workflow execution
│   │   │   ├── sprint_cadence.py # Automated sprint scheduling
│   │   │   └── events/           # 16 event handlers
│   │   └── integrations/
│   │       ├── jira_client.py    # Async Jira REST API wrapper
│   │       ├── jira_health.py    # ONLINE/OFFLINE/RECOVERING monitor
│   │       ├── jira_write_queue.py # Persistent queue (pacing, retry)
│   │       ├── jira_bootstrapper.py # Idempotent Jira provisioner
│   │       ├── alerting.py       # AWS SES alerts + daily digest
│   │       └── scheduler.py      # APScheduler job definitions
│   └── tests/                    # 518 tests (24+ files)
└── frontend/
    ├── Dockerfile
    ├── package.json, vite.config.ts, tsconfig.json
    └── src/
        ├── App.tsx               # Main shell (team switcher, sections)
        ├── components/
        │   ├── layout/           # Shell, Sidebar, Topbar
        │   ├── ui/               # shadcn/ui primitives
        │   ├── workflow/         # WorkflowDesigner (drag-drop)
        │   ├── members/          # MemberTable CRUD
        │   ├── settings/         # TeamSettings (capacity, hours)
        │   ├── dependencies/     # Cross-team dependency config
        │   ├── simulation/       # SimulationDashboard
        │   ├── templates/        # TemplatePage
        │   └── schedule/         # EventSchedule, FlowMatrix (Plotly boxplots)
        └── hooks/                # React Query hooks per feature
```

---

## Database Schema (24 Models)

### Core (Stages 1-2)
- **Organization** → has many Teams
- **Team** → Members, Workflow, Sprints, configs (8 extra cols from Stage 4)
- **Member** → virtual workers (name, role, capacity, timezone)
- **Workflow** → ordered WorkflowSteps
- **WorkflowStep** → jira_status, role_required, touch_time_config
- **TouchTimeConfig** → per (step, issue_type, story_points) → min/max hours
- **DysfunctionConfig** → probability multipliers per dysfunction type
- **Sprint** → phase, number, dates, committed/completed points
- **Issue** → current state, priority, carried_over, descoped, split_from

### Jira Integration (Stage 3)
- **JiraConfig** — key-value config store
- **JiraWriteQueueEntry** — persistent write queue (PENDING/IN_FLIGHT/DONE/FAILED/SKIPPED)
- **JiraIssueMap** — internal ID → Jira key mapping
- **JiraIssueLink** — cross-team issue link tracking

### Simulation Engine (Stage 4)
- **SimulationEventConfig** — event handler probabilities + thresholds
- **SimulationEventLog** — audit trail of fired events
- **MoveLeftConfig** / **MoveLeftTarget** / **MoveLeftSameStepStatus** — quality engineering config
- **DailyCapacityLog** — historical capacity tracking
- **TimingTemplate** — pre-computed timing patterns (5 types × 6 story points)
- **PrecomputationRun** — metadata for template pre-computation runs

---

## Implementation Status

### COMPLETE
- **Stage 0 — Infrastructure**: AWS provisioned, CI/CD pipeline, Docker, Nginx, GitHub repo
- **Stage 1 — Data Model**: 10 SQLAlchemy models, Alembic migrations, Pydantic schemas, 95 tests
- **Stage 2 — Config UI**: Full React frontend for team/member/workflow/settings management
- **Stage 3 — Jira Integration**: JiraClient, health monitor, write queue, bootstrapper, alerting, 289 tests
- **Stage 4 — Simulation Engine**: Tick orchestrator, 16 event handlers, sprint lifecycle, capacity, backlog, 518 tests

### NOT STARTED (specs exist but no code)
- **Stage 5 — Simulation Engine Rewrite** (formerly "Dysfunction Engine")
  - **Full 10-phase plan exists** in `docs/plan/phase-01..10.md`
  - **Requirements doc** in `docs/simulation-engine-rewrite-requirements.md`
  - Replaces event-probability system with distribution-based workflow engine
  - Key changes: log-normal/uniform distributions, simplified capacity (1 item/member/tick), 3-phase sprint cycle, move-left probability grid, 1:1 Jira status mapping
  - Estimated scope: ~900 lines replaced, ~150 line new orchestrator + modular components
- **Stage 6 — Dashboard UI**: Not specified yet
- **Stage 7 — Hardening**: Not specified yet

---

## Development Methodology & Skills

### Mandatory Development Flow (from AGENTS.md)
1. **Plan Mode First** — ask all questions, get approval before writing code
2. **Task Splitting** — break into context-window-sized tasks, tracked in `backlog/`
3. **TDD** — strict RED→GREEN→REFACTOR (obra/superpowers skill)
4. **Documentation** — update changelog.md, assumptions.md, readme.md, agent_instruction.md after every task
5. **Backlog Maintenance** — update task markers in `backlog/` files

### Required Skills (Claude Code)
1. **obra/superpowers TDD** — enforces RED→GREEN→REFACTOR cycle for all code
2. **ertugrul-dmr/clean-code-skills** — 66 Clean Code rules for Python backend:
   - N1-N7 (naming), F1-F4 (functions), G5 (DRY), G25 (no magic numbers), G30 (single responsibility), G36 (Law of Demeter), P1 (no wildcard imports), P3 (type hints), T1-T9 (test rules)
3. **Custom .claude/skills/**: clean-tests, clean-comments, clean-names, clean-functions, clean-general, python-clean-code, boy-scout

### Key Rules
- Tests written BEFORE code — always
- No function longer than 30 lines
- Dependencies injected, not hardcoded
- Jira assignee/reporter NEVER changed after creation
- All Jira writes batched per tick
- All event handlers use dependency-injected `rng` for deterministic testing
- Alembic migrations are hand-written, not auto-generated

---

## How to Run

### Local Development
```bash
git clone https://github.com/mrscrum/jira-simulator.git && cd jira-simulator
cp .env.example .env  # fill in secrets
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
# Backend: http://localhost:8000/docs  |  Frontend: http://localhost:5173
```

### Run Tests
```bash
# Backend
cd backend && .venv/bin/python -m pytest tests/ --tb=short -q
# Or in Docker
docker compose exec backend python -m pytest tests/ -v

# Frontend
cd frontend && npm test
```

### Deploy (automatic via CI/CD)
```bash
git push origin main  # triggers: pytest → ruff → vitest → SSH deploy to EC2
```

### Manual EC2 Access
```bash
ssh -i ~/.ssh/jira_simulator.pem ec2-user@98.89.183.224
cd /app/jira-simulator
sudo docker compose ps  # check containers
sudo docker compose logs backend --tail 50  # check logs
```

---

## Gotchas & Non-Obvious Details

1. **OpenAI is the LLM provider, NOT Anthropic** — `OPENAI_API_KEY` in `.env`
2. **SQLite on EC2** at `/data/simulator.db` (EBS mount), NOT PostgreSQL (Docker Compose has PG option but EC2 uses SQLite)
3. **Deploy uses `sudo docker compose`** — ec2-user needs sudo for docker group
4. **`jira_proxy.py` is dead code** — replaced by `jira_integration.py` but file still on disk
5. **In-memory SQLite doesn't support WAL** — WAL tests use file-based SQLite
6. **SQLite doesn't support ALTER ADD CONSTRAINT** — `split_from_id` FK enforced at ORM level only
7. **Vite proxy**: `/api/*` → `http://localhost:8000` with path rewrite (strips `/api` prefix)
8. **`_tick_team` in simulation.py has placeholder body** — full wiring needed for integration testing
9. **Pre-existing test failure**: `test_loads_default_database_url` fails in Docker (env override) — not a real bug
10. **Frontend dev server**: port 5173, backend: port 8000

---

## Key Domain Concepts

- **Tick**: One simulation step (configurable interval, default 30min). Each tick processes all active teams.
- **Touch Time**: Actual work duration per workflow step, sampled from configured distribution (min/max hours per issue_type × story_points)
- **Wait Time**: Time in queue waiting for a free worker
- **Move-Left**: Quality regression — issue moves backward in workflow (probability grid)
- **Dysfunction**: Mechanical effects on time model (7 types: low quality story, scope addition, blocking dependency, teammate dark, re-estimation, bug injection, cross-team)
- **Sprint Phases**: PLANNING → ACTIVE → COMPLETED (Stage 4); proposed rewrite adds SIMULATED phase
- **Jira Write Queue**: Persistent, paced (5/sec), with retry logic — all writes batched per tick
- **Bootstrapper**: Idempotent Jira project/board/status provisioner — safe to re-run

---

## What the Next Agent Should Do

1. Read `AGENTS.md` first — it's the master spec
2. Read `agent_instruction.md` — current state and key files
3. Read `docs/simulation-engine-rewrite-requirements.md` — Stage 5 requirements
4. Read `docs/plan/phase-01..10.md` — detailed 10-phase implementation plan
5. Begin Stage 5 (simulation engine rewrite) following the TDD flow
6. After Stage 5: Stages 6 (Dashboard UI) and 7 (Hardening) are undefined — await specs from Pavel

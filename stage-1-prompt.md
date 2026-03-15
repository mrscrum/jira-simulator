# Stage 1 — Data Model & Database Layer

You are continuing the Jira Team Simulator project. Read AGENTS.md first for full
project context. Read agent_instruction.md for current state and handoff notes.

Stage 0 (infrastructure) is complete. This stage builds the data model layer —
no API endpoints, no UI, no simulation logic.

---

## What to build

### 1. Configuration module

`backend/app/config.py` — Pydantic Settings class loading from .env:
- `JIRA_BASE_URL: str`
- `JIRA_EMAIL: str`
- `JIRA_API_TOKEN: str`
- `OPENAI_API_KEY: str`
- `DATABASE_URL: str` (default: `sqlite:///./data/simulator.db`)
- `ENVIRONMENT: str` (default: `production`)
- `LOG_LEVEL: str` (default: `INFO`)
- `TICK_INTERVAL_MINUTES: int` (default: `30`)

### 2. Database setup

`backend/app/database.py`:
- SQLAlchemy engine creation from `DATABASE_URL`
- Session factory (sessionmaker)
- `get_db()` dependency for FastAPI
- For SQLite: enable WAL mode and foreign keys via event listener

### 3. SQLAlchemy models

All models in `backend/app/models/`. One file per entity, plus `__init__.py` re-exporting all.

**Organization** (`organization.py`):
- `id: int` (PK, auto-increment)
- `name: str` (unique, not null)
- `description: str` (nullable)
- `created_at: datetime` (server default UTC)
- `updated_at: datetime` (server default UTC, on-update)
- Relationship: `teams` → Team (one-to-many)

**Team** (`team.py`):
- `id: int` (PK)
- `organization_id: int` (FK → Organization)
- `name: str` (not null)
- `jira_project_key: str` (unique, not null) — the Jira project this team maps to
- `jira_board_id: int` (nullable) — Jira board ID if known
- `is_active: bool` (default True)
- `created_at`, `updated_at`
- Relationships: `organization`, `members`, `workflow`, `dysfunction_config`, `issues`

**Member** (`member.py`):
- `id: int` (PK)
- `team_id: int` (FK → Team)
- `name: str` (not null) — written to sim_assignee/sim_reporter in Jira
- `role: str` (not null) — enum-like: `PO`, `BA`, `DEV`, `QA`, `SM`, `DEVOPS`
- `daily_capacity_hours: float` (default 6.0)
- `max_concurrent_wip: int` (default 3)
- `is_active: bool` (default True)
- `created_at`, `updated_at`
- Relationships: `team`

**Workflow** (`workflow.py`):
- `id: int` (PK)
- `team_id: int` (FK → Team, unique — one workflow per team)
- `name: str` (not null)
- `description: str` (nullable)
- `created_at`, `updated_at`
- Relationships: `team`, `steps` → WorkflowStep (one-to-many, ordered by `order`)

**WorkflowStep** (`workflow_step.py`):
- `id: int` (PK)
- `workflow_id: int` (FK → Workflow)
- `jira_status: str` (not null) — the Jira status name (e.g. "In Development")
- `role_required: str` (not null) — which role handles this step
- `order: int` (not null) — position in workflow sequence
- `max_wait_hours: float` (default 24.0)
- `wip_contribution: float` (default 1.0) — how much WIP capacity this step consumes
- `created_at`, `updated_at`
- Relationships: `workflow`, `touch_time_configs`
- Unique constraint: `(workflow_id, order)` and `(workflow_id, jira_status)`

**TouchTimeConfig** (`touch_time_config.py`):
- `id: int` (PK)
- `workflow_step_id: int` (FK → WorkflowStep)
- `issue_type: str` (not null) — e.g. "Story", "Bug", "Task"
- `story_points: int` (not null) — Fibonacci: 1, 2, 3, 5, 8, 13
- `min_hours: float` (not null)
- `max_hours: float` (not null)
- Unique constraint: `(workflow_step_id, issue_type, story_points)`

**DysfunctionConfig** (`dysfunction_config.py`):
- `id: int` (PK)
- `team_id: int` (FK → Team, unique — one config per team)
- `low_quality_probability: float` (default 0.15)
- `scope_creep_probability: float` (default 0.10)
- `blocking_dependency_probability: float` (default 0.12)
- `dark_teammate_probability: float` (default 0.05)
- `re_estimation_probability: float` (default 0.10)
- `bug_injection_probability: float` (default 0.20)
- `cross_team_block_probability: float` (default 0.08)
- `cross_team_handoff_lag_probability: float` (default 0.10)
- `cross_team_bug_probability: float` (default 0.05)
- `created_at`, `updated_at`
- Relationships: `team`

**Issue** (`issue.py`) — internal simulation state:
- `id: int` (PK)
- `team_id: int` (FK → Team)
- `jira_issue_key: str` (unique, nullable) — set after Jira creation
- `jira_issue_id: str` (nullable) — Jira's internal ID
- `issue_type: str` (not null) — "Story", "Bug", "Task"
- `summary: str` (not null)
- `description: str` (nullable)
- `story_points: int` (nullable) — Fibonacci scale
- `priority: str` (default "Medium")
- `current_workflow_step_id: int` (FK → WorkflowStep, nullable)
- `current_worker_id: int` (FK → Member, nullable) — internal only, not in Jira
- `jira_assignee_id: int` (FK → Member, nullable) — set at creation, never changed
- `jira_reporter_id: int` (FK → Member, nullable) — set at creation, never changed
- `touch_time_remaining_hours: float` (default 0.0)
- `wait_time_accumulated_hours: float` (default 0.0)
- `total_cycle_time_hours: float` (default 0.0)
- `sprint_id: int` (FK → Sprint, nullable)
- `is_blocked: bool` (default False)
- `blocked_by_issue_id: int` (FK → Issue, nullable) — self-referential
- `dysfunction_flags: str` (nullable) — JSON string of active dysfunction types
- `status: str` (default "backlog") — current Jira status name
- `created_at`, `updated_at`
- `completed_at: datetime` (nullable)
- Relationships: `team`, `current_workflow_step`, `current_worker`, `jira_assignee`, `jira_reporter`, `sprint`, `blocked_by`

**Sprint** (`sprint.py`):
- `id: int` (PK)
- `team_id: int` (FK → Team)
- `jira_sprint_id: int` (nullable) — Jira's sprint ID
- `name: str` (not null)
- `goal: str` (nullable)
- `start_date: datetime` (not null)
- `end_date: datetime` (not null)
- `status: str` (default "future") — "future", "active", "closed"
- `planned_velocity: int` (nullable)
- `actual_velocity: int` (nullable)
- `scope_change_points: int` (default 0) — tracks mid-sprint additions
- `created_at`, `updated_at`
- Relationships: `team`, `issues`

### 4. Alembic setup and initial migration

- Initialize Alembic in `backend/alembic/`
- Configure to use the app's DATABASE_URL from config
- Generate initial migration with all models above
- Migration must be idempotent (safe to re-run)

### 5. Pydantic v2 schemas

All schemas in `backend/app/schemas/`. One file per entity, plus `__init__.py`.

For each entity, create:
- `<Entity>Base` — shared fields for create/update
- `<Entity>Create` — fields needed to create a new record
- `<Entity>Read` — fields returned from the API (includes id, timestamps)
- `<Entity>Update` — optional fields for partial updates

Use Pydantic v2 style (`model_config = ConfigDict(from_attributes=True)`).

### 6. Wire models into FastAPI app

Update `backend/app/main.py`:
- Import database setup
- Add startup event to create tables (as fallback — Alembic is primary)
- Keep existing /health endpoint working

---

## Execution rules

Follow AGENTS.md mandatory development flow:

1. **Plan mode first** — ask any clarifying questions before starting
2. **Add all tasks to `backlog/stage-1-data-model.md`** before writing code
3. **TDD for everything** — failing test first, then implementation, then refactor
4. **Clean code rules** apply to all Python files
5. **Update docs after every task**: changelog.md, assumptions.md, readme.md, agent_instruction.md
6. **Update backlog markers in real time**

---

## Test expectations

- Every model: test table creation, required fields, defaults, relationships, constraints
- Every schema: test validation (valid data, missing required fields, invalid types)
- Config: test loading from env vars, test defaults
- Database: test session creation, test get_db dependency
- Alembic: test migration runs forward cleanly
- All tests must run in < 100ms each (use in-memory SQLite for tests)
- Run full test suite before deploying

---

## Deployment

After all tests pass:
1. Push to main — CI/CD will run tests and deploy automatically
2. Verify /health still returns 200 on EC2
3. SSH into EC2 and verify Alembic migration runs: `docker compose exec backend alembic upgrade head`
4. Verify SQLite database is created at /data/simulator.db

---

## UAT checklist

- [ ] All models create tables with correct columns and constraints
- [ ] All relationships work (e.g., team.members returns member list)
- [ ] Unique constraints enforced (e.g., duplicate jira_project_key fails)
- [ ] Alembic migration runs cleanly from scratch
- [ ] Pydantic schemas validate correctly (accept valid, reject invalid)
- [ ] /health endpoint still works
- [ ] Database created at /data/simulator.db on EC2
- [ ] All tests pass (pytest + ruff green)
- [ ] No secrets committed to repo

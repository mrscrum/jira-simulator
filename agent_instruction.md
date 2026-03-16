# Agent Instruction — Jira Team Simulator

## Current Stage
Stage 0 — COMPLETE
Stage 1 — Data Model — COMPLETE
Stage 2 — Config UI — COMPLETE
Stage 3 — Jira Integration Layer — COMPLETE (pending UAT sign-off)
Stage 4 — Simulation Engine — COMPLETE

## What Has Been Implemented
- LLM provider: OpenAI (NOT Anthropic — this was swapped before project start)
- GitHub repo: https://github.com/mrscrum/jira-simulator
- Full directory skeleton per AGENTS.md
- AWS infrastructure live via Terraform: EC2 t3.small, EBS 20GB gp3, DLM snapshots, Elastic IP, Security Group, IAM roles
- Backend scaffold: FastAPI with /health endpoint (stage "4")
- Frontend scaffold: Vite + React + TypeScript + one test
- Docker Compose: backend + nginx, production and dev configs
- CI/CD pipeline: GitHub Actions (pytest → ruff → vitest → SSH deploy to EC2)
- Both required skills installed (obra/superpowers TDD + clean-code-skills)
- **Stage 1 complete:**
  - Pydantic Settings config module loading all env vars
  - SQLAlchemy database module with engine, session factory, get_db
  - SQLite WAL mode and foreign keys enabled via event listener
  - 10 SQLAlchemy models: Organization, Team, Member, Workflow, WorkflowStep, TouchTimeConfig, DysfunctionConfig, Sprint, Issue
  - TimestampMixin base class for DRY (id, created_at, updated_at)
  - All relationships, unique constraints, and defaults per spec
  - Alembic setup with env.py and initial migration (001_initial_schema)
  - Pydantic v2 schemas for all 9 entities (Base, Create, Read, Update)
  - FastAPI lifespan event for table creation fallback
  - 95 tests passing, ruff clean
- **Stage 3 complete:**
  - JiraClient async httpx wrapper (all Jira REST API v3 methods)
  - JiraHealthMonitor with ONLINE/OFFLINE/RECOVERING state machine
  - JiraWriteQueue persistent queue with pacing, recovery, and priority ordering
  - JiraBootstrapper idempotent project/board/field/status provisioner
  - AlertingService with AWS SES email alerts and daily digest
  - APScheduler integration (health check every 60s, daily digest at 08:00 UTC)
  - 4 new DB models: JiraConfig, JiraWriteQueueEntry, JiraIssueMap, JiraIssueLink
  - 3 bootstrap columns on Team model (jira_bootstrapped, jira_bootstrap_warnings, jira_bootstrapped_at)
  - 5 Alembic migrations (003-007)
  - 6 new API endpoints: bootstrap, bootstrap status, health, queue status, retry-failed, project statuses
  - Replaced hardcoded jira_proxy.py with real Jira integration router
  - Pydantic schemas for all Jira API responses
  - boto3 dependency for AWS SES
  - alert_email_from, alert_email_to, aws_ses_region in Settings
  - All integration services wired into FastAPI lifespan
  - 289 tests passing, ruff clean
- **Stage 4 complete:**
  - `engine/calendar.py` — pure functions for timezone-aware business days, working hours, cross-TZ handoff lag (ZoneInfo)
  - `engine/capacity.py` — DailyCapacityState frozen dataclass, WIP tracking, touch-time advancement, available worker selection
  - `engine/issue_state_machine.py` — IssueState StrEnum (9 states), JiraWriteAction dataclass, transition_issue() with valid transition map
  - `engine/sprint_lifecycle.py` — SprintPhase StrEnum, phase advancement logic, capacity-fitted/priority-ordered issue selection, carry-over detection, velocity calc
  - `engine/events/` — BaseEvent ABC, TickContext/EventOutcome dataclasses, registry with 16 event handlers
  - 16 events: carry_over, velocity_drift, sprint_goal_risk, stale_issue, move_left, descope, unplanned_absence, priority_change, split_story, external_block, uneven_load, review_bottleneck, onboarding_tax, late_planning, skipped_retro, scope_commitment_miss
  - `engine/backlog.py` — depth check, story point distribution, TemplateContentGenerator + OpenAIContentGenerator (w/ fallback)
  - `engine/simulation.py` — SimulationEngine tick orchestrator (STOPPED/RUNNING/PAUSED), per-team pause, write queue integration
  - 6 new DB models: SimulationEventConfig, SimulationEventLog, MoveLeftConfig, MoveLeftTarget, MoveLeftSameStepStatus, DailyCapacityLog
  - Extended Team (8 cols), Member (1 col), Sprint (7 cols), Issue (4 cols)
  - Alembic migration 008_stage4_schema
  - Updated Pydantic schemas for all modified entities
  - 20+ simulation API endpoints: engine control, per-team control, sprint management, event config/log, backlog, capacity, health
  - SimulationEngine created in FastAPI lifespan, stored on app.state
  - 518 tests passing, ruff clean

## Live Infrastructure
- **EC2 public IP**: 98.89.183.224
- **Health check**: http://98.89.183.224/health → `{"status":"ok","stage":"4"}`
- **Frontend**: http://98.89.183.224/
- **SSH**: `ssh -i ~/.ssh/jira_simulator.pem ec2-user@98.89.183.224`
- **Data volume**: /data (20GB EBS gp3, encrypted, daily DLM snapshots)
- **App directory**: /app/jira-simulator
- **SQLite**: /data/simulator.db (created by Alembic migration on deploy)

## Key Files and What They Do
- `AGENTS.md` — master project spec (development flow, domain model, tech stack, rules)
- `backend/app/config.py` — Pydantic Settings loading env vars (.env), including alert/SES config
- `backend/app/database.py` — SQLAlchemy engine, session factory, get_db dependency
- `backend/app/models/base.py` — DeclarativeBase + TimestampMixin
- `backend/app/models/*.py` — 19 SQLAlchemy model files (9 original + 4 Jira + 6 Stage 4)
- `backend/app/models/__init__.py` — re-exports all models
- `backend/app/schemas/*.py` — 10 Pydantic schema files (9 original + jira.py)
- `backend/app/schemas/__init__.py` — re-exports all schemas
- `backend/app/main.py` — FastAPI app with lifespan, /health, integration + engine wiring
- `backend/app/engine/calendar.py` — pure business day/timezone/holiday calculations
- `backend/app/engine/capacity.py` — DailyCapacityState, WIP, touch-time advancement
- `backend/app/engine/issue_state_machine.py` — IssueState enum, transition logic, JiraWriteAction
- `backend/app/engine/sprint_lifecycle.py` — SprintPhase, phase advancement, issue selection
- `backend/app/engine/backlog.py` — depth check, content generation (template + OpenAI)
- `backend/app/engine/simulation.py` — tick orchestrator, engine state machine
- `backend/app/engine/events/base.py` — TickContext, EventOutcome, BaseEvent ABC
- `backend/app/engine/events/registry.py` — 16-event handler registry
- `backend/app/engine/events/*.py` — 16 individual event handler modules
- `backend/app/integrations/jira_client.py` — async httpx Jira REST API wrapper
- `backend/app/integrations/jira_health.py` — health monitor state machine
- `backend/app/integrations/jira_write_queue.py` — persistent write queue with pacing
- `backend/app/integrations/jira_bootstrapper.py` — idempotent Jira project provisioner
- `backend/app/integrations/alerting.py` — AWS SES alerting service
- `backend/app/integrations/scheduler.py` — APScheduler job definitions
- `backend/app/integrations/exceptions.py` — typed Jira API exceptions
- `backend/app/api/routers/simulation.py` — 20+ simulation API endpoints
- `backend/app/api/routers/jira_integration.py` — 6 Jira API endpoints
- `backend/alembic/env.py` — Alembic migration environment
- `backend/alembic/versions/001-008` — 8 migrations (001 initial + 002 stage2 + 003-007 Jira + 008 stage4)
- `backend/tests/` — 518 tests across 24+ test files

## Next Task — Stage 5: Dysfunction Events
Per AGENTS.md, Stage 5 covers advanced dysfunction events. Awaiting spec from Pavel.

## Active Decisions / Unresolved Questions
- SprintPhase field exists on Sprint model but is treated as a backup field (user decision: use status primarily)
- OpenAI SDK vs httpx for LLM calls — OpenAI SDK used in backlog.py OpenAIContentGenerator
- Branch protection on main not yet configured
- Pre-existing test_config.py failure: test_loads_default_database_url fails in Docker because container env overrides DATABASE_URL (not a real bug)
- Tick orchestrator _tick_team has placeholder body — full wiring needed when integration-tested with real data

## Gotchas
- **OpenAI is the LLM provider, NOT Anthropic** — check AGENTS.md env vars section
- `.env` and `infra/terraform.tfvars` are gitignored — if you don't see them, they're correctly hidden
- Deploy workflow uses `sudo docker compose` (ec2-user needs sudo for docker)
- Deploy workflow sets `git config --global --add safe.directory /app/jira-simulator`
- **Local venv at backend/.venv/** — run tests: `.venv/bin/python -m pytest tests/ --tb=short -q`
- **Test deps need install after container rebuild**: `docker compose exec backend pip install pytest pytest-asyncio ruff boto3`
- In-memory SQLite doesn't support WAL mode — WAL test uses file-based SQLite
- SQLite doesn't support ALTER ADD CONSTRAINT — split_from_id FK enforced at ORM level only
- Alembic migrations are hand-written, not autogenerated
- `backend/app/api/routers/jira_proxy.py` still exists on disk but is no longer imported (replaced by jira_integration.py)
- All event handlers use dependency-injected `rng` parameter for deterministic testing
- Follow AGENTS.md mandatory development flow: plan → task split → TDD → docs → backlog update

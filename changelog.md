## [2026-03-15] Stage 3 — Jira Integration Layer
### Changed
- Created JiraClient async httpx wrapper (all Jira REST API v3 methods)
- Created JiraHealthMonitor with ONLINE/OFFLINE/RECOVERING state machine
- Created JiraWriteQueue persistent queue with pacing, recovery, and priority ordering
- Created JiraBootstrapper idempotent project/board/field/status provisioner
- Created AlertingService with AWS SES email alerts and daily digest
- Created APScheduler integration (health check every 60s, daily digest at 08:00 UTC)
- Added 4 new DB models: JiraConfig, JiraWriteQueueEntry, JiraIssueMap, JiraIssueLink
- Added 3 bootstrap columns to Team model (jira_bootstrapped, jira_bootstrap_warnings, jira_bootstrapped_at)
- Created 5 Alembic migrations (003-007)
- Added 6 new API endpoints: bootstrap, bootstrap status, health, queue status, retry-failed, project statuses
- Replaced hardcoded jira_proxy.py with real Jira status proxy (with fallback)
- Added Pydantic schemas for all Jira API responses
- Added boto3 dependency for AWS SES
- Added alert_email_from, alert_email_to, aws_ses_region to Settings
- Wired all integration services into FastAPI lifespan
- Updated health endpoint to stage "3"
- 289 tests passing, ruff clean

## [2026-03-15] Stage 1 — Data Model & Database Layer
### Changed
- Implemented Pydantic Settings config module (config.py) loading all env vars
- Implemented database module (database.py) with SQLAlchemy engine, session factory, get_db dependency
- SQLite WAL mode and foreign keys enabled via event listener
- Created 10 SQLAlchemy models: Organization, Team, Member, Workflow, WorkflowStep, TouchTimeConfig, DysfunctionConfig, Sprint, Issue
- Created TimestampMixin base class for id/created_at/updated_at (DRY)
- All models have proper relationships, unique constraints, and defaults per spec
- Issue model has self-referential blocked_by FK and multiple member FKs
- Set up Alembic with env.py, script.py.mako, and initial migration (001_initial_schema)
- Created Pydantic v2 schemas for all 9 entities (Base, Create, Read, Update variants)
- Wired models into FastAPI with lifespan event for table creation fallback
- Updated /health endpoint stage from "0" to "1"
- Added pydantic-settings dependency to pyproject.toml
- Added setuptools package discovery config (include app* only)
- Created .venv with Python 3.12 for local development
- 95 tests total, all passing

## [2026-03-15] Stage 0 — Infrastructure verification and CI/CD fix
### Changed
- Deployed .env to EC2 with all secrets (Jira, OpenAI, app config), chmod 600
- Configured GitHub repository secrets (EC2_HOST, EC2_USER, SSH_PRIVATE_KEY) via API
- Fixed deploy workflow: added git safe.directory and sudo for docker compose
- Fixed /app/jira-simulator ownership to ec2-user (was root from user-data)
- Fixed /data ownership to ec2-user
- Updated Terraform user-data to set correct ownership on future instances
- Verified full CI/CD pipeline end-to-end: tests pass, deploy succeeds, containers rebuilt
- Updated agent_instruction.md with full handoff context for Stage 1
### Fixed
- CI/CD deploy failure: "dubious ownership" git error on EC2
- CI/CD deploy failure: .env permission denied (owned by root, deploy runs as ec2-user)

## [2026-03-15] Stage 0 — Terraform apply and EC2 verification
### Changed
- Terraform applied: 11 AWS resources created (EC2, EBS, EIP, SG, IAM, DLM)
- EC2 root volume increased from 20GB to 30GB (Amazon Linux 2023 AMI minimum)
- User data script updated: added Docker Buildx v0.19.3 install (bundled version too old)
- User data script updated: added Node.js 20 install and frontend build step
- Frontend package-lock.json added to repo
### Fixed
- Docker compose build failure due to outdated buildx (< 0.17.0 bundled with Amazon Linux)
- Frontend 403 error: added frontend build step to user data script

## [2026-03-15] Stage 0 — Initial project skeleton and infrastructure code
### Changed
- Created GitHub repo at https://github.com/mrscrum/jira-simulator
- Full directory skeleton per AGENTS.md repository structure
- Terraform code: EC2 (t3.small, Amazon Linux 2023), EBS (20GB gp3 encrypted), DLM snapshots (daily, 7-day retention), Elastic IP, Security Group (22/80/443), IAM roles
- Docker Compose: backend (FastAPI) + nginx (reverse proxy), plus dev overrides
- Nginx config: static files, /api/* proxy, /health endpoint
- GitHub Actions CI/CD: test → lint → deploy pipeline
- Backend scaffold: FastAPI /health endpoint returning {"status":"ok","stage":"0"}, one passing test
- Frontend scaffold: Vite + React + TypeScript placeholder, one passing test
- Documentation: README, .env.example, agent_instruction.md, all backlog stage files
- Installed obra/superpowers TDD skill and clean-code-skills at project level

## [2026-03-15] Stage 0 — Swap LLM provider from Anthropic to OpenAI
### Changed
- Replaced all Anthropic/Claude references with OpenAI across AGENTS.md, stage-0-prompt.md, and cc-initiate-project.md
- Environment variable `ANTHROPIC_API_KEY` renamed to `OPENAI_API_KEY` in all spec files
- httpx description updated from "Claude API calls" to "OpenAI API calls" in AGENTS.md
- README prerequisites updated from "Anthropic API key" to "OpenAI API key" in stage-0-prompt.md

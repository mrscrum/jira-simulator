# Agent Instruction — Jira Team Simulator

## Current Stage
Stage 0 — COMPLETE (pending final UAT sign-off from Pavel)
Stage 1 — Data Model (NEXT)

## What Has Been Implemented
- LLM provider: OpenAI (NOT Anthropic — this was swapped before project start)
- GitHub repo: https://github.com/mrscrum/jira-simulator
- Full directory skeleton per AGENTS.md
- AWS infrastructure live via Terraform: EC2 t3.small, EBS 20GB gp3, DLM snapshots, Elastic IP, Security Group, IAM roles
- Backend scaffold: FastAPI with /health endpoint + one test (Python 3.12)
- Frontend scaffold: Vite + React + TypeScript + one test
- Docker Compose: backend + nginx, production and dev configs
- CI/CD pipeline: GitHub Actions (pytest → ruff → vitest → SSH deploy to EC2)
- .env deployed on EC2 at /app/jira-simulator/.env (chmod 600)
- GitHub repo secrets configured: EC2_HOST, EC2_USER, SSH_PRIVATE_KEY
- Both required skills installed (obra/superpowers TDD + clean-code-skills)

## Live Infrastructure
- **EC2 public IP**: 98.89.183.224
- **Health check**: http://98.89.183.224/health → `{"status":"ok","stage":"0"}`
- **Frontend**: http://98.89.183.224/
- **SSH**: `ssh -i ~/.ssh/jira_simulator.pem ec2-user@98.89.183.224`
- **Data volume**: /data (20GB EBS gp3, encrypted, daily DLM snapshots)
- **App directory**: /app/jira-simulator
- **SQLite will live at**: /data/simulator.db

## Key Files and What They Do
- `AGENTS.md` — master project spec (development flow, domain model, tech stack, rules)
- `.env` — local credentials (gitignored, NEVER commit)
- `infra/main.tf` — all AWS resources
- `infra/terraform.tfvars` — real AWS values (gitignored, NEVER commit)
- `docker-compose.yml` — production Docker setup (backend + nginx)
- `docker-compose.dev.yml` — local dev overrides
- `nginx/nginx.conf` — reverse proxy + static file serving
- `.github/workflows/deploy.yml` — CI/CD pipeline
- `backend/app/main.py` — FastAPI app with /health endpoint
- `frontend/src/App.tsx` — placeholder React app

## Next Task — Stage 1: Data Model
Per AGENTS.md, Stage 1 covers the full SQLAlchemy domain model and Alembic migrations.
A spec file exists at `backlog/stage-1-data-model.md` (tasks not yet defined).

Entities to model (from AGENTS.md Simulation Domain Model):
1. Organization → has many Teams
2. Team → has Members, Workflow, DysfunctionConfig
3. Member → name, role, daily_capacity_hours, max_concurrent_wip
4. Workflow → has ordered WorkflowSteps
5. WorkflowStep → jira_status, role_required, touch_time_config, max_wait_hours, wip_contribution
6. Issue → internal simulation state mirroring Jira
7. DysfunctionConfig → per-team probabilities

Also needed:
- backend/app/config.py — Pydantic Settings loading env vars
- backend/app/database.py — SQLAlchemy engine/session setup
- Alembic initial migration
- Pydantic v2 schemas for all entities
- Full TDD per AGENTS.md mandatory flow

## Active Decisions / Unresolved Questions
- Pavel has not yet provided a detailed Stage 1 spec — the agent should draft one based on AGENTS.md domain model and get approval before implementing
- OpenAI SDK vs httpx for LLM calls — to be decided in a later stage
- Branch protection on main not yet configured

## Gotchas
- **OpenAI is the LLM provider, NOT Anthropic** — check AGENTS.md env vars section
- `.env` and `infra/terraform.tfvars` are gitignored — if you don't see them, they're correctly hidden
- Deploy workflow uses `sudo docker compose` (ec2-user needs sudo for docker)
- Deploy workflow sets `git config --global --add safe.directory /app/jira-simulator`
- EC2 root volume is 30GB (AMI minimum), data EBS is 20GB
- The `.env` on EC2 is owned by ec2-user with chmod 600
- `/app/jira-simulator` is owned by ec2-user (chown applied post-deploy fix)
- CI/CD pipeline is fully functional — tests pass and deploy succeeds
- Follow AGENTS.md mandatory development flow: plan → task split → TDD → docs → backlog update

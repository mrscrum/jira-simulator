# Agent Instruction — Jira Team Simulator

## Current Stage
Stage 0 — Infrastructure Kickoff (IN PROGRESS)

## What Has Been Implemented
- LLM provider swapped from Anthropic to OpenAI across all spec files
- Credentials stored locally in `.env` (gitignored)
- Both required skills installed (obra/superpowers TDD + clean-code-skills)
- GitHub repo created at https://github.com/mrscrum/jira-simulator
- Full directory skeleton created per AGENTS.md
- All infrastructure code written (Terraform, Docker Compose, Nginx, CI/CD)
- Backend scaffold: FastAPI with /health endpoint + one test
- Frontend scaffold: Vite + React + TypeScript + one test

## What Was Most Recently Changed
- Creating all Stage 0 files: Terraform, Docker, backend/frontend scaffolds, CI/CD pipeline

## Key Files and What They Do
- `AGENTS.md` — master project spec (development flow, domain model, tech stack, rules)
- `stage-0-prompt.md` — Stage 0 spec (infrastructure only)
- `cc-initiate-project.md` — project initiation steps
- `.env` — local credentials (gitignored, NEVER commit)
- `infra/main.tf` — all AWS resources (EC2, EBS, DLM, EIP, SG, IAM)
- `infra/terraform.tfvars` — real AWS values (gitignored, NEVER commit)
- `docker-compose.yml` — production Docker setup (backend + nginx)
- `nginx/nginx.conf` — reverse proxy + static file serving
- `.github/workflows/deploy.yml` — CI/CD pipeline
- `backend/app/main.py` — FastAPI app with /health endpoint
- `frontend/src/App.tsx` — placeholder React app

## Next Task
- Push all files to GitHub
- Run `terraform init` + `terraform plan` (show output, wait for approval)
- Apply terraform after approval
- Verify EC2 is reachable and /health returns 200

## Active Decisions / Unresolved Questions
- Branch protection will be set after CI pipeline runs green at least once
- Pavel needs to manually add GitHub secrets (EC2_HOST, EC2_USER, SSH_PRIVATE_KEY) after terraform apply
- Pavel needs to manually populate .env on EC2 at /app/jira-simulator/.env

## Gotchas
- `.env` and `infra/terraform.tfvars` are gitignored — if you don't see them, they're correctly hidden
- OpenAI is the LLM provider, NOT Anthropic — check AGENTS.md env vars section
- The frontend `dist/` directory won't exist until `npm run build` is run — nginx will 403 initially
- EBS volume device name may be `/dev/xvdf` or `/dev/nvme1n1` depending on instance — user data handles both

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

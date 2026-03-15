# Stage 0 — Infrastructure Kickoff
Status: IN UAT

## Tasks
- [x] Swap LLM provider from Anthropic to OpenAI — completed 2026-03-15
- [x] Store credentials locally (.env + terraform.tfvars) — completed 2026-03-15
- [x] Install required skills (obra/superpowers + clean-code-skills) — completed 2026-03-15
- [x] Create GitHub repo and push skeleton — completed 2026-03-15
- [x] Write Terraform code (EC2, EBS, DLM, EIP, SG, IAM) — completed 2026-03-15
- [x] Write Docker Compose + Nginx config — completed 2026-03-15
- [x] Write GitHub Actions CI/CD pipeline — completed 2026-03-15
- [x] Backend scaffold (FastAPI /health + test) — completed 2026-03-15
- [x] Frontend scaffold (Vite + React + test) — completed 2026-03-15
- [x] Documentation (.env.example, README, backlog, agent_instruction) — completed 2026-03-15
- [x] Terraform init + plan (show output, get approval) — completed 2026-03-15
- [x] Terraform apply + verification — completed 2026-03-15
- [ ] UAT sign-off

## UAT Results
(pending Pavel's verification)

## Notes
- LLM provider changed from Anthropic to OpenAI before project start (user request)
- All credentials stored locally in .env (gitignored), never committed
- Root volume bumped from 20GB to 30GB — Amazon Linux 2023 AMI requires >= 30GB
- Docker buildx updated to v0.19.3 — bundled version too old for compose build
- Node.js 20 installed on EC2 for frontend build (system Node was too old)
- Frontend dist/ built on EC2 to serve the placeholder page

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
- [x] Deploy .env to EC2 with correct permissions — completed 2026-03-15
- [x] Configure GitHub repo secrets (EC2_HOST, EC2_USER, SSH_PRIVATE_KEY) — completed 2026-03-15
- [x] Fix deploy permissions (git safe.directory + sudo docker) — completed 2026-03-15
- [x] Verify CI/CD pipeline end-to-end (tests + deploy) — completed 2026-03-15
- [ ] UAT sign-off

## UAT Results
### Agent self-verification (2026-03-15) — PASS
- http://98.89.183.224/health returns 200 with `{"status":"ok","stage":"0"}`
- Frontend loads at http://98.89.183.224/
- SSH access works via `ssh -i ~/.ssh/jira_simulator.pem ec2-user@98.89.183.224`
- /data volume mounted (20GB gp3, encrypted), writable by ec2-user
- DLM snapshot policy active (policy-0cababb9178b57f4d, daily @ 02:00 UTC, 7 retained)
- .env on EC2 at /app/jira-simulator/.env with chmod 600
- GitHub repo secrets set (EC2_HOST, EC2_USER, SSH_PRIVATE_KEY)
- CI/CD pipeline: tests pass (backend + frontend + ruff), deploy succeeds, containers rebuilt
- Both containers running: backend (uvicorn) + nginx

### Pavel UAT — pending

## Notes
- LLM provider changed from Anthropic to OpenAI before project start (user request)
- All credentials stored locally in .env (gitignored), never committed
- Root volume bumped from 20GB to 30GB — Amazon Linux 2023 AMI requires >= 30GB
- Docker buildx updated to v0.19.3 — bundled version too old for compose build
- Node.js 20 installed on EC2 for frontend build
- Deploy step required fixes: git safe.directory + sudo for docker compose
- /app/jira-simulator ownership changed to ec2-user for deploy to work

# Stage 0 — Infrastructure Kickoff
Status: IN PROGRESS

## Tasks
- [x] Swap LLM provider from Anthropic to OpenAI — completed 2026-03-15
- [x] Store credentials locally (.env + terraform.tfvars) — completed 2026-03-15
- [x] Install required skills (obra/superpowers + clean-code-skills) — completed 2026-03-15
- [ ] Create GitHub repo and push skeleton — in progress
- [ ] Write Terraform code (EC2, EBS, DLM, EIP, SG, IAM)
- [ ] Write Docker Compose + Nginx config
- [ ] Write GitHub Actions CI/CD pipeline
- [ ] Backend scaffold (FastAPI /health + test)
- [ ] Frontend scaffold (Vite + React + test)
- [ ] Documentation (.env.example, README, backlog, agent_instruction)
- [ ] Terraform init + plan (show output, get approval)
- [ ] Terraform apply + verification
- [ ] UAT sign-off

## UAT Results
(pending)

## Notes
- LLM provider changed from Anthropic to OpenAI before project start (user request)
- All credentials stored locally in .env (gitignored), never committed

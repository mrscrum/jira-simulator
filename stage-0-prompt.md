# Stage 0 — Infrastructure Kickoff Prompt

Paste this entire message into Claude Code, replacing the placeholder values with your real credentials.

---

You are starting Stage 0 of the Jira Team Simulator project. Read AGENTS.md first for full
project context. This stage is infrastructure only — no application code.

## Your credentials

```
AWS_ACCESS_KEY_ID:      REPLACE_ME
AWS_SECRET_ACCESS_KEY:  REPLACE_ME
AWS_REGION:             us-east-1
KEY_PAIR_NAME:          REPLACE_ME
GITHUB_TOKEN:           REPLACE_ME
```

## What to build

### 1. GitHub Repository
- Create a new public GitHub repository named `jira-simulator` using the token above
- Initialize with a README and .gitignore (Python)
- Create the full directory skeleton from AGENTS.md (empty placeholder files are fine)
- Add AGENTS.md to the repo root
- Set up branch protection on main: require CI to pass before merge

### 2. Terraform Infrastructure (infra/ directory)

Provision the following AWS resources:

**EC2 Instance**
- AMI: latest Amazon Linux 2023 (fetch current AMI ID via data source at apply time)
- Type: t3.small
- Key pair: as provided above
- IAM instance profile: attach a role with DLM permissions for EBS snapshots
- User data script (runs on first boot):
  - Install Docker and Docker Compose plugin
  - Install Git
  - Install fail2ban and enable it
  - Create /app directory
  - Clone the GitHub repo to /app/jira-simulator
  - Create /app/jira-simulator/.env as an empty file with chmod 600
  - Mount the EBS data volume at /data (format if new, mount if existing)
  - Add /data mount to /etc/fstab for persistence across reboots
  - Run: docker compose up -d from /app/jira-simulator
- Tags: Name=jira-simulator

**EBS Data Volume**
- Size: 20GB, type gp3
- Same availability zone as EC2
- Encrypted: true
- Mount point on EC2: /data
- Tag: Name=jira-simulator-data
- This is where SQLite will live — must survive instance replacement

**EBS Snapshot Policy (DLM)**
- Daily snapshots at 02:00 UTC
- Retain 7 snapshots
- Target: EBS volume tagged Name=jira-simulator-data

**Elastic IP**
- Attach to EC2 instance
- Output the final public DNS hostname

**Security Group**
- Port 22 (SSH): 0.0.0.0/0
- Port 80 (HTTP): 0.0.0.0/0
- Port 443 (HTTPS): 0.0.0.0/0
- Egress: all traffic

**No Route53, no ACM, no ALB, no RDS, no ECS.**

### 3. Terraform files to produce

`infra/main.tf` — all resources above
`infra/variables.tf` — all inputs as variables
`infra/outputs.tf` — elastic IP, public DNS hostname, SSH command, EBS volume ID
`infra/terraform.tfvars.example` — template with descriptions, no real values

### 4. Docker Compose (shell only)

`docker-compose.yml`:
- `backend` service: builds from ./backend, restart unless-stopped, mounts /data:/data,
  loads env vars from .env, exposes port 8000
- `nginx` service: nginx:alpine, restart unless-stopped, mounts ./nginx/nginx.conf and
  ./frontend/dist, exposes ports 80 and 443

`docker-compose.dev.yml`:
- Overrides for local development (volume mounts for hot reload, debug ports)

`nginx/nginx.conf`:
- Serve React build (./frontend/dist) as static files on port 80
- Proxy /api/* to backend:8000
- Return 200 on /health for basic uptime checks
- HTTP only for now (HTTPS added later when domain is configured)

### 5. GitHub Actions CI/CD

`.github/workflows/deploy.yml`:
- Trigger: push to main
- Steps:
  1. Checkout
  2. Run backend tests: `cd backend && pip install -e ".[dev]" && pytest` (will pass trivially
     since no tests exist yet — scaffold the test runner so it works when tests are added)
  3. Run frontend tests: `cd frontend && npm ci && npm test` (same — scaffold only)
  4. Run Ruff: `ruff check backend/` 
  5. On all green: SSH into EC2, cd /app/jira-simulator, git pull, docker compose up -d --build
  6. Verify: docker compose ps (confirm containers are running)
- GitHub secrets required (document in README, do not create — Pavel adds these manually):
  - EC2_HOST (the Elastic IP output from Terraform)
  - EC2_USER (ec2-user)
  - SSH_PRIVATE_KEY (contents of the .pem file)

### 6. Backend scaffold (minimum to make CI pass)

`backend/Dockerfile` — Python 3.12 slim, installs dependencies, runs uvicorn
`backend/pyproject.toml` — project metadata, dependencies (fastapi, uvicorn, sqlalchemy,
  alembic, pydantic, httpx, apscheduler, pytest, ruff)
`backend/app/main.py` — FastAPI app with single GET /health endpoint returning
  `{"status": "ok", "stage": "0"}`
`backend/tests/__init__.py` — empty
`backend/tests/unit/test_health.py` — one test: assert /health returns 200 and correct body

### 7. Frontend scaffold (minimum to make CI pass)

`frontend/` — Vite + React + TypeScript scaffold
`frontend/src/App.tsx` — single div: "Jira Team Simulator — coming soon"
`frontend/tests/` — one trivial test that the App component renders

### 8. .env.example

Document all environment variables with descriptions:
```
# Jira connection
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your-jira-api-token

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Application
DATABASE_URL=sqlite:////data/simulator.db
ENVIRONMENT=production
LOG_LEVEL=INFO
TICK_INTERVAL_MINUTES=30
```

### 9. README.md

Cover:
- Project overview (2–3 sentences)
- Prerequisites (AWS account, GitHub account, Jira Cloud, OpenAI API key)
- Infrastructure setup (terraform init → plan → apply)
- GitHub Actions secrets to add manually after terraform apply
- How to SSH into the instance
- How to add the .env file to the instance after provisioning
- Local development setup

---

## Execution order

1. Create GitHub repo and push skeleton
2. Write Terraform code
3. Run `terraform init` and `terraform plan` — share the plan output for review before apply
4. Wait for plan approval, then `terraform apply`
5. Share the outputs (Elastic IP, public DNS, SSH command)
6. Verify EC2 is reachable and /health returns 200
7. Document the GitHub secrets Pavel needs to add manually

## UAT checklist (what I will verify before signing off)

- [ ] `terraform apply` completed with no errors
- [ ] EC2 public DNS hostname is accessible — `http://<hostname>/health` returns 200
- [ ] Frontend loads at `http://<hostname>/`
- [ ] SSH access works: `ssh -i ~/.ssh/<keypair>.pem ec2-user@<hostname>`
- [ ] `/data` volume is mounted and writable on the instance
- [ ] DLM snapshot policy is visible in AWS console
- [ ] GitHub Actions pipeline runs green on a dummy commit to main
- [ ] `.env` file exists on instance at `/app/jira-simulator/.env` with chmod 600

Do not proceed to Stage 1 until I confirm all UAT items above.

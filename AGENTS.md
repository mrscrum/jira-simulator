# Jira Team Simulator — Claude Code Agent Guide

## Project Purpose

A multi-team Jira activity simulator that emulates how real engineering teams work,
including realistic dysfunctions, handoffs, and cross-team dependencies. Its primary
purpose is to generate authentic Jira data patterns for stress-testing a Sprint Risk
Analyzer tool.

---

## Mandatory Development Flow

This flow is non-negotiable. Follow it in order for every instruction received.

---

### Step 1 — Plan Mode First

Before writing any code or making any changes, always switch to plan mode.
- Read the full instruction carefully
- Ask ALL clarifying questions before proceeding — do not assume anything
- One round of questions is preferred over multiple back-and-forth rounds, so think ahead
- Do not begin implementation until every ambiguity is resolved
- Present the plan explicitly and wait for approval

**Rule: If you are unsure about anything, ask. Never assume and proceed.**

---

### Step 2 — Task Splitting

Break the approved plan into tasks sized to fit within a single context window.
- Each task must be completable start-to-finish in one session without losing context
- If a feature is too large, split at natural seams (model layer, API layer, UI layer)
- Each task must have: a clear goal, explicit inputs, explicit outputs, and a done condition
- Tasks within a stage are listed in `backlog/` before implementation begins

---

### Step 3 — Implementation (TDD + Clean Code)

Execute each task following the obra/superpowers TDD skill and clean-code-skills.
See the Required Skills section for full detail.

Short form:
1. Write failing test (RED)
2. Write minimum code to pass (GREEN)
3. Refactor (still GREEN)
4. No code written before its test — violating this means delete and restart

---

### Step 4 — Documentation (mandatory after every task)

After completing each task, update all of the following before moving to the next task.
No task is complete until all four documents are current.

#### `changelog.md`
- Append an entry for every task completed
- Format:
  ```
  ## [YYYY-MM-DD] Stage N — Task name
  ### Changed
  - What was added, modified, or removed
  ### Fixed
  - Any bugs or issues resolved
  ```
- Never overwrite previous entries — append only

#### `assumptions.md`
- Record everything you decided that was NOT explicitly in the user's instruction
- Format:
  ```
  ## [YYYY-MM-DD] Stage N — Task name
  - Assumed X because Y was not specified
  - Chose library Z because no preference was given — used industry default
  ```
- If you made zero assumptions, write "No assumptions made" for that entry
- This is the audit trail for decisions Pavel did not make

#### `readme.md`
- Always reflects the current state of the project — not a future vision
- Written for a human who has never seen the codebase
- Must always contain:
  - What the system does (current implemented state only)
  - Prerequisites and setup steps
  - How to run locally
  - How to deploy
  - How to configure (env vars, team setup, workflow config)
  - Known limitations of the current stage
- Update in place — this is a living document, not append-only

#### `agent_instruction.md`
- Written for a fresh Claude Code agent picking up the project mid-stream
- Must always contain:
  - Current stage and what has been implemented so far
  - What was most recently changed and why
  - Where key files are and what they do
  - What the next task is
  - Any active decisions or unresolved questions
  - Gotchas, non-obvious constraints, things that burned time
- Update in place after every task — keep it current, not historical

---

### Step 5 — Backlog Maintenance

The `backlog/` folder is the single source of truth for project status.

#### Folder structure:
```
backlog/
├── stage-0-infrastructure.md
├── stage-1-data-model.md
├── stage-2-config-ui.md
├── stage-3-jira-integration.md
├── stage-4-simulation-engine.md
├── stage-5-dysfunction-engine.md
├── stage-6-dashboard-ui.md
└── stage-7-hardening.md
```

#### Each stage file format:
```markdown
# Stage N — [Name]
Status: [NOT STARTED | IN PROGRESS | IN UAT | COMPLETE | BLOCKED]

## Tasks
- [x] Task name — completed YYYY-MM-DD
- [ ] Task name — in progress
- [~] Task name — delayed, reason: ...
- [!] Task name — blocked by: ...

## UAT Results
- YYYY-MM-DD: [PASS / FAIL] — notes

## Notes
Any relevant context, fixes applied after UAT, decisions made during implementation.
```

#### Rules:
- Create all stage files at project start with tasks listed (status: NOT STARTED)
- Update task markers in real time as work progresses — never batch-update at the end
- When a task is delayed or descoped, mark `[~]` and write the reason — never silently drop it
- When UAT finds a defect, add it as a new task `[ ]` under the relevant stage
- Never delete tasks — mark them instead

---

### Flow Summary

```
Receive instruction
  → Plan mode: ask questions, get approval
  → Split into context-window-sized tasks, add to backlog/
  → For each task:
      → TDD: RED → GREEN → REFACTOR
      → Update changelog.md
      → Update assumptions.md
      → Update readme.md
      → Update agent_instruction.md
      → Update backlog/ task marker
  → Deploy
  → UAT
  → If defects: add to backlog, fix, redeploy, re-UAT
  → Sign-off → next stage
```

---

## Agent Responsibilities

Claude Code owns:
- All implementation (backend, frontend, infrastructure)
- All tests (written before implementation — TDD is non-negotiable)
- All infrastructure provisioning and deployment
- All GitHub repository management
- Deploying to dev and promoting to prod after UAT sign-off

The human (Pavel) owns:
- UAT only — accepts or rejects each stage
- Clarification dialogues before each stage spec is written
- Providing credentials and secrets
- Final sign-off before prod promotion

---

## Required Skills

Two external skill sets are mandatory for this project. Both must be installed before
any implementation work begins. Instructions below.

---

### Skill 1 — obra/superpowers TDD (all code, backend and frontend)

**What it is:** The `test-driven-development` skill from the obra/superpowers framework.
Enforces strict RED→GREEN→REFACTOR cycles. Code written before a failing test is deleted.
This is mandatory, not optional.

**Install via Claude Code plugin marketplace (recommended):**
```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```
Quit and restart Claude Code after install.

**Or install manually:**
```bash
git clone https://github.com/obra/superpowers ~/.claude/skills/superpowers
```

**How it activates:** Automatically when writing or modifying any code. You will see the
RED→GREEN→REFACTOR cycle enforced. If you find yourself writing implementation code before
a failing test exists, stop — you are violating this rule.

**Mandatory behaviors this skill enforces:**
- Write the test first. Run it. Watch it FAIL (RED). If it passes, the test is wrong.
- Write the minimum code to make it pass. Run it. Watch it PASS (GREEN).
- Refactor. Run tests again. Still GREEN.
- Any code written before its test is deleted and rewritten test-first.
- This cycle applies to every function, every endpoint, every module — no exceptions.

---

### Skill 2 — ertugrul-dmr/clean-code-skills (backend code only)

**What it is:** 66 clean code rules from Robert C. Martin's *Clean Code*, encoded as
agent skills for Python. Enforces naming, function design, comment hygiene, DRY,
single responsibility, and more. Applies to all backend Python code.

**Install:**
```bash
# Project-level (applies to this project only — preferred)
mkdir -p .claude/skills
git clone https://github.com/ertugrul-dmr/clean-code-skills /tmp/clean-code-skills
cp -r /tmp/clean-code-skills/skills/* .claude/skills/
rm -rf /tmp/clean-code-skills
```

**Or globally:**
```bash
mkdir -p ~/.claude/skills
git clone https://github.com/ertugrul-dmr/clean-code-skills /tmp/clean-code-skills
cp -r /tmp/clean-code-skills/skills/* ~/.claude/skills/
rm -rf /tmp/clean-code-skills
```

**How it activates:** Automatically when writing or reviewing Python backend code.
The `python-clean-code` master skill (all 66 rules) activates for general backend work.
Individual sub-skills activate for targeted scenarios (functions, naming, tests, comments).

**Key rules enforced (non-exhaustive):**
- N1–N7: Descriptive, unambiguous names. No Hungarian notation. No abbreviations.
- F1–F4: Max 3 function arguments. No flag arguments. No dead functions.
- G5: DRY — no duplication.
- G25: No magic numbers — named constants only.
- G30: Functions do one thing.
- G36: Law of Demeter — one dot.
- P1: No wildcard imports.
- P3: Type hints on all public interfaces.
- T1–T9: Tests cover boundaries, run fast (<100ms each), no skipped tests.

**Does NOT apply to:** Frontend TypeScript/React code (Skill 1 TDD still applies there).

---

### Skill Priority Order

Per the obra/superpowers framework, priority is:
1. AGENTS.md instructions (this file) — highest priority
2. Superpowers skills (TDD, etc.)
3. Clean code skills

If any skill instruction conflicts with AGENTS.md, follow AGENTS.md and flag the conflict.

---

## Development Rules (Non-Negotiable)

### Spec-Driven Development
- Each stage begins with a written spec (provided in chat by Pavel)
- Implementation must match the spec exactly
- Any deviation from spec must be flagged and discussed before proceeding
- Spec clarifications go back to Pavel, not decided unilaterally

### TDD — enforced by obra/superpowers skill
See Skill 1 above. Summary: failing test → passing test → refactor. Always.

### Clean Code — enforced by clean-code-skills for backend
See Skill 2 above. All 66 rules apply to every Python file in `backend/`.

### Additional rules not covered by skills
- No function longer than 30 lines without strong justification
- Every module has a clear single responsibility
- Dependencies are injected, not hardcoded
- Tests must pass 100% before any deployment

---

## Technology Stack

### Backend
- **Python 3.12+**
- **FastAPI** — REST API
- **SQLAlchemy** + **Alembic** — ORM and migrations
- **SQLite** — database (file at `/data/simulator.db` on EC2, `./data/simulator.db` locally)
- **APScheduler** — background tick engine
- **Pydantic v2** — request/response validation
- **pytest** — test framework
- **httpx** — async HTTP client (Jira API, OpenAI API calls)
- **Ruff** — linting and formatting (enforced in CI)

### Frontend
- **React 18** with **Vite**
- **TypeScript**
- **shadcn/ui** — component library
- **Tailwind CSS** — styling
- **React Query** — server state management
- **React Testing Library + Vitest** — component tests

### Infrastructure
- **Terraform** — all AWS resources
- **Docker + Docker Compose** — local and EC2 deployment
- **Nginx** — reverse proxy + static file serving
- **GitHub Actions** — CI/CD pipeline
- **fail2ban** — SSH brute-force protection on EC2

### AWS Resources
- EC2 t3.small (Amazon Linux 2023)
- EBS gp3 20GB (mounted at /data — SQLite lives here)
- EBS daily snapshots via DLM (7-day retention)
- Elastic IP
- Security group (ports 80, 443, 22 open)

---

## Repository Structure

```
jira-simulator/
├── AGENTS.md                        # this file
├── README.md
├── docker-compose.yml
├── docker-compose.dev.yml           # local dev overrides
├── .env.example                     # template — never commit real .env
├── .github/
│   └── workflows/
│       └── deploy.yml
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   │   └── routers/
│   │   ├── engine/
│   │   │   ├── simulation.py
│   │   │   ├── capacity.py
│   │   │   ├── workflow.py
│   │   │   ├── dysfunctions.py
│   │   │   ├── cross_team.py
│   │   │   └── sprint_lifecycle.py
│   │   └── integrations/
│   │       ├── jira_client.py
│   │       └── ai_content.py
│   └── tests/
│       ├── unit/
│       └── integration/
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   ├── pages/
    │   ├── hooks/
    │   └── lib/
    └── tests/
```

---

## Simulation Domain Model

### Core Entities

**Organization** → has many **Teams**
Each **Team**:
- Owns one Jira project
- Has its own **Workflow** (based on shared template + overrides)
- Has **Members** (virtual — names written to Jira custom text fields only)
- Has **DysfunctionConfig** (probability per dysfunction type)

**Member**:
- `name` — written to `sim_assignee` / `sim_reporter` custom fields in Jira
- `role` — maps to workflow step ownership
- `daily_capacity_hours` — working hours available per day
- `max_concurrent_wip` — hard ceiling on active issues

**Workflow** → has ordered **WorkflowSteps**
Each **WorkflowStep**:
- `jira_status` — the Jira status name
- `role_required` — which role handles this step
- `touch_time_config` — per issue_type × story_points → `{min_hours, max_hours}`
- `max_wait_hours` — max time in queue before escalation comment
- `wip_contribution` — how much of a person's WIP capacity this step consumes

**Issue** (internal state):
- Mirrors a Jira issue
- Tracks: `current_workflow_step`, `current_worker` (internal only), `touch_time_remaining`, `wait_time_accumulated`, `dysfunction_flags`
- `assignee` and `reporter` in Jira are NEVER changed after creation — handoffs are invisible in Jira

### Simulation Time Model (per workflow step)

```
effective_time_in_status = wait_time + touch_time

wait_time:  time issue sits in queue waiting for a free role/person
            driven by: person.available_hours == 0 OR person.active_wip >= max_concurrent_wip

touch_time: actual work duration, drawn from distribution:
            config[issue_type][story_points] → random(min_hours, max_hours)
            modified by dysfunction multipliers when active
```

Story points use Fibonacci scale: 1, 2, 3, 5, 8, 13

---

## Dysfunction Impact Model

All multiplier ranges are configurable per team. Dysfunctions have quantified mechanical
effects on the time model — they are not just Jira cosmetic changes.

### 1. Low Quality Story
- BA/PO Review: touch_time × 1.5–2.5x, cycle_back_probability 40–70%
- Dev: touch_time × 1.2–1.8x
- QA: touch_time × 1.5–3.0x, cycle_back_probability 50–80%
- Raises: bug_injection_probability +30%, re_estimation_probability +40%

### 2. Mid-Sprint Scope Addition
- All members: available_hours_today × 0.85–0.95 for 1–2 days (context switch tax)
- In-progress issues: touch_time_remaining × 1.1–1.3x
- Sprint: scope_creep_delta += new_issue_points, velocity_forecast recalculated

### 3. Blocking Dependency
- Blocked issue: touch_time PAUSED (not slowed), wait_time unbounded
- Assignee capacity: freed (picks up other work)
- Blocker issue: priority raised, touch_time × 0.8x (focus effect)
- Escalation comment posted after configurable wait threshold

### 4. Teammate Goes Dark
- Person: available_hours → 0 for 2–5 days, max_concurrent_wip → 0
- Their issues: touch_time PAUSED, wait_time accumulates
- After threshold: SM reassigns, new worker touch_time resets to 60–80% of original

### 5. Re-estimation
- Story points: original × 1.5–2.5x
- Touch time budget extended proportionally
- If over sprint capacity: lowest priority issue descoped (60–80% probability)

### 6. Bug Injection
- Triggered on: issue transitions to Done
- Bug touch_time inherits quality context of parent (LOW_QUALITY_AC multiplier stacks)
- Dev interruption tax: current_wip touch_time × 1.1x

### 7. Cross-Team Dysfunctions
- Shared component block: consuming teams enter BLOCKED_EXTERNAL
- Cross-team handoff lag: 4–16 hours + 10–20% touch_time overhead
- Cross-team bug: fix touch_time × 1.3x on both teams
- Escalation ladder: comment → SM escalation → sprint risk flag

### Compound Effects
- Multipliers stack multiplicatively unless a cap is configured
- TEAMMATE_DARK + BLOCKING_DEP on same issue: wait_time = dark_duration + blocker_resolution
- LOW_QUALITY_AC + BUG_INJECTION: bug touch_time = base × AC_multiplier × bug_multiplier

---

## Jira Integration Rules

- **Assignee and reporter in Jira are set at issue creation and NEVER changed**
- Handoffs are tracked internally only — invisible in Jira
- Virtual team member names go into two custom text fields: `sim_assignee`, `sim_reporter`
- Comments are written by the service account but worded as if from the current internal worker
  - Format: `[Alice - QA] Picked up for testing, looks more complex than estimated...`
- All Jira writes are batched per tick — never write mid-tick
- Jira API rate limits: respect 429 responses, retry with exponential backoff
- JiraBootstrapper is idempotent — safe to run multiple times

---

## Deployment Workflow (per stage)

```
1. Spec provided in chat → Claude Code implements tests first
2. All tests green → Claude Code deploys to EC2
3. Pavel does UAT against live instance
4. Defects reported → Claude Code fixes → redeploy → re-UAT
5. Pavel signs off → stage complete → next stage begins
```

Deployment command (GitHub Actions on push to main):
```bash
ssh ec2-user@<ELASTIC_IP> "cd /app/jira-simulator && git pull && docker compose up -d --build"
```

---

## Environment Variables

Never hardcoded. Never committed. Loaded from `.env` on EC2 at `/app/jira-simulator/.env`.

```bash
# Jira
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=...

# OpenAI
OPENAI_API_KEY=...

# App
DATABASE_URL=sqlite:////data/simulator.db
ENVIRONMENT=production
LOG_LEVEL=INFO
TICK_INTERVAL_MINUTES=30
```

`.env.example` in repo documents all variables with descriptions but no values.

---

## CI Pipeline (.github/workflows/deploy.yml)

```
Trigger: push to main

Steps:
1. Run backend tests (pytest)
2. Run frontend tests (vitest)
3. Run Ruff linter
4. If all green: SSH deploy to EC2
5. Verify containers running (docker compose ps)
```

Pipeline must be green before any deploy. A failing test blocks deployment.

---

## Local Development

```bash
# Clone
git clone https://github.com/<org>/jira-simulator.git
cd jira-simulator

# Copy and fill env
cp .env.example .env

# Run locally
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Backend available at: http://localhost:8000
# Frontend available at: http://localhost:5173
# API docs at:           http://localhost:8000/docs
```

---

## Key Constraints to Never Violate

1. Install both skills before writing any code (see Required Skills section)
2. Tests written before code — always, enforced by obra/superpowers TDD skill
3. All backend Python follows clean-code-skills 66 rules — no exceptions
4. Jira assignee/reporter never change after issue creation
5. Dysfunction effects are mechanical (time model changes) not just cosmetic
6. SQLite file lives on EBS volume — never on the root volume
7. Secrets never in repo, never in Terraform state
8. All Jira writes batched per tick — no mid-tick writes
9. Simulation state must survive backend restarts cleanly

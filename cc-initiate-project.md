# Project Initiation — Jira Team Simulator

You are starting a new project called **Jira Team Simulator**. Before doing anything
else, read this entire instruction, then follow the steps below in order.

---

## Step 1 — Read AGENTS.md

This file is attached to this message. Read it fully before proceeding. It defines:
- Your mandatory development flow
- Required skills to install
- The full domain model and technical stack
- All non-negotiable rules

Do not proceed past this step until you have read AGENTS.md completely.

---

## Step 2 — Ask for credentials and configuration

You need the following information before you can create the repository or provision
any infrastructure. Ask the user for all of them now, in a single message. Do not
assume any values. Do not proceed until you have received answers to every item.

Ask the user for:

**AWS credentials:**
- AWS Access Key ID
- AWS Secret Access Key
- AWS Region (e.g. us-east-1)
- EC2 Key Pair name (the name as it appears in the AWS console)

**GitHub:**
- GitHub Personal Access Token (needs repo + workflow scopes)
- Preferred GitHub username or organisation the repo should be created under

**Application secrets (needed for .env.example and EC2 setup instructions):**
- Jira base URL (e.g. https://yourorg.atlassian.net)
- Jira account email
- Jira API token
- OpenAI API key

**Project preferences:**
- Preferred subdomain prefix, or confirm `simulator` is fine
  (will become: ec2-xx-xx-xx-xx.compute.amazonaws.com for now, real subdomain later)
- Tick interval in minutes — how often the simulation engine should wake up and act
  (suggest 30 minutes as default; user can change later)
- Confirm the EC2 .pem key file path on their local machine
  (needed so you can write the correct SSH command into README.md and outputs)

---

## Step 3 — Confirm understanding before acting

Once you have all answers, do the following before writing a single file:

1. Summarise what you are about to do in plain language — the repo name, the AWS
   resources that will be created, the secrets that will be stored where
2. List any assumptions you are making (there should be very few given you asked
   everything above)
3. Ask: "Shall I proceed?"

Wait for explicit confirmation before taking any action.

---

## Step 4 — Install required skills

Before writing any project code, install both required skills as defined in AGENTS.md.

**Skill 1 — obra/superpowers (TDD, all code):**
```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```
If the plugin marketplace is unavailable, install manually:
```bash
git clone https://github.com/obra/superpowers ~/.claude/skills/superpowers
```

**Skill 2 — clean-code-skills (backend Python only):**
```bash
# Will be installed into the project repo during Step 5
# so it travels with the codebase
```
You will add this during repository scaffolding in Step 5.

---

## Step 5 — Execute Stage 0

With credentials confirmed and skills installed, execute Stage 0 exactly as specified
in AGENTS.md and the Stage 0 spec provided separately.

Follow the mandatory development flow from AGENTS.md for every task:
- Add all Stage 0 tasks to `backlog/stage-0-infrastructure.md` before starting
- Complete each task with TDD
- Update `changelog.md`, `assumptions.md`, `readme.md`, `agent_instruction.md`
  after every task
- Update backlog task markers in real time

Before running `terraform apply`, show the full `terraform plan` output and ask:
"Shall I apply this plan?" — wait for explicit approval.

---

## What NOT to do

- Do not generate placeholder or mock values for any credentials — ask for the real ones
- Do not start writing code before receiving confirmation in Step 3
- Do not skip the plan summary in Step 3 even if the task seems straightforward
- Do not run `terraform apply` without explicit user approval of the plan output
- Do not commit any secret values to the repository under any circumstances
- Do not install skills globally if a project-level install is possible

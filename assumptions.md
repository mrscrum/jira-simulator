## [2026-03-15] Stage 0 — Terraform apply and EC2 verification
- Assumed 30GB root volume is acceptable (AMI enforces >= 30GB minimum, spec said 20GB)
- Assumed installing Node.js 20 on EC2 via nodesource is acceptable for frontend builds
- Assumed building frontend on EC2 during user data is the right approach (vs building in CI and deploying dist/)

## [2026-03-15] Stage 0 — Initial project skeleton and infrastructure code
- Assumed `.pem` file path is `~/.ssh/jira_simulator.pem` (user provided `.ssh/jira_simulator.pem` without `~` prefix)
- Assumed AWS default VPC is used — no custom VPC was specified
- Assumed repository is public per stage-0-prompt.md spec
- Assumed `openai` Python SDK added to backend dependencies since OpenAI is the LLM provider
- Assumed branch protection will be configured after CI pipeline runs green at least once (chicken-and-egg: protection requires CI status checks, but no checks exist until first push triggers CI)

## [2026-03-15] Stage 0 — Swap LLM provider from Anthropic to OpenAI
- Assumed the `ai_content.py` integration module (listed in AGENTS.md repo structure) will use OpenAI SDK instead of Anthropic SDK — user confirmed OpenAI as the provider
- Assumed `httpx` remains in the stack for Jira API calls; OpenAI calls may use the `openai` Python SDK directly — to be confirmed during Stage 1 implementation

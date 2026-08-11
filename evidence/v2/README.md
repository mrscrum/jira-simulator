# V2 Implementation Evidence

Create one directory per task: `evidence/v2/<task-id>/README.md`.

Evidence records follow `/docs/v2/implementation-runbook.md`. Do not commit secrets or large raw
logs. Store large artifacts outside Git and record their durable location and checksum.

Planning evidence exists at `V2-S0-T01/README.md`. Local implementation evidence now exists for the
reviewed persistence spine (`M1-T01`, `M1-T02`) and the review-hardened pure deterministic
decision/sampling kernel (`M1-T03`). None of these records claims deployment, UAT, live Jira/OpenAI
access, or M1 completion.

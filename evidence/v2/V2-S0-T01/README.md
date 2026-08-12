# V2-S0-T01 — Freeze the approved v2 plan

> This record captures an earlier detailed planning pass. Pavel subsequently requested a
> high-level plan. The active outcome is now `docs/v2/high-level-plan.md` and the detailed 96-task
> artifacts referenced below are optional background rather than an execution mandate.

- Date: 2026-08-10
- Agent: Codex primary agent with three independent planning reviews
- Branch/baseline: `main` at assessed commit `b65b133`
- Task type: documentation/contract only
- Result: PASS

## Authority and scope

The task captured Pavel's approved requirements, his instruction to use recommended choices where
unspecified, his confirmation, and his later explicit requirement that simulator-managed Jira
projects survive manual sprint/card intervention. It changed planning, contract, backlog, and
handoff documentation only. It made no application/source-code, database, deployment, Jira, OpenAI,
or other external mutation.

The pre-existing dirty worktree was preserved. No stash, reset, clean, checkout, automatic deletion,
or ownership-changing Git action was used.

## Produced artifacts

- Authoritative product requirements, ADRs, glossary, architecture, and operations plan under
  `docs/v2/`.
- Versioned blueprint/draft schemas, canonical Scrum fixture, recommended Scrum/Kanban catalog, and
  domain/Jira/API/MCP/ground-truth contracts under `docs/v2/contracts/`.
- A 96-task, eight-stage executable plan and matching `backlog/v2/` source of truth.
- A 28-row requirement-to-task/evidence matrix with Scrum G5 before Kanban G6.
- Authority/archive pointers that prevent historical v1 plans from being executed as v2.
- Updated `README.md`, `agent_instruction.md`, `assumptions.md`, and `changelog.md` without claiming
  any v2 runtime implementation.

## Verification

Documentation-task checks completed successfully:

- all contract/example JSON parses;
- the canonical Scrum fixture validates against Draft 2020-12 `team-blueprint.schema.json`, including
  the optional capacity-override branch;
- implementation plan and backlog contain the same 96 unique task IDs and exact titles;
- all 28 requirements appear exactly once in the verification matrix;
- every explicit task reference resolves, dependencies point to earlier tasks/gates, and Markdown
  relative links resolve;
- required public-API topology, auth/export, manual-intervention, replay, pause/restart, and outbox
  terminology checks pass;
- Markdown fences balance, no trailing whitespace or unresolved executable `TBD` remains, and
  `git diff --check` passes.

No backend/frontend tests were rerun for this documentation-only task; the evidence-backed assessed
baseline remains recorded in `agent_instruction.md`. No live Jira capability claim was made.

## Stop conditions and next task

`V2-S0-T02` is next but cannot start until the owner safely checkpoints the existing dirty
assessment/planning work. `V2-S0-T03` is a further hard stop for code until the mandatory
Superpowers TDD skill is installed and callable. `V2-S0-T09` requires designated target-tenant Jira
admin credentials, a disposable prefix, and explicit live-mutation authorization; failure of its
public-API topology/column proof blocks the simulation-engine gate.

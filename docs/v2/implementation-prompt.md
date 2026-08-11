# Overnight v2 Implementation Prompt

Copy the prompt below into a new Codex task rooted at this repository.

---

/goal Implement as much of Jira Team Simulator v2 as can be completed safely and correctly in this
run, beginning with the persisted Scrum core and continuing through the next useful vertical slices.
Work independently, keep the repository green, and leave a runnable, evidence-backed morning
handoff rather than stopping for routine confirmations.

You are the primary implementation agent for Jira Team Simulator v2. This is intended to be a long,
largely unattended run. Implementation—not another detailed planning exercise—is the objective.

Read these files first, in this order:

1. [Repository rules and mandatory development flow](/Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/AGENTS.md)
2. [Active v2 requirements and architecture](/Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/docs/v2/high-level-plan.md)
3. [Current implementation assessment](/Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/docs/requirements-functionality-map.md)
4. [Active milestone backlog](/Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/backlog/v2/README.md)
5. [Current agent handoff](/Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/agent_instruction.md)

The other documents under `docs/v2/` and the detailed v2 stage files are optional reference only.
Do not turn them back into mandatory low-level requirements or spend the run expanding plans.

## Autonomy mandate

- The high-level plan and this local execution mandate are already approved. Create a concise
  working plan/backlog for the next implementation slice, but do not pause to request another
  general plan approval before starting.
- Work continuously until the run ends or no safe in-scope work remains. Make reasonable technical
  decisions yourself and record them in `assumptions.md`.
- Do not stop for routine choices, package installation, local environment repair, ordinary test
  failures, naming, schema shape, library selection, or other decisions a capable implementation
  agent can make from the high-level plan and repository evidence.
- If one path is blocked, record the blocker and continue useful independent work elsewhere. Missing
  live Jira/OpenAI credentials must not prevent implementation with fakes and local contract tests.
- Ask Pavel only when continuing would require a new product decision that materially changes the
  high-level plan, an ambiguous destructive action, unavailable secrets/authority for an external
  mutation that has no local substitute, or acceptance of a demonstrated safety/data-loss risk.
- Pavel authorizes continuous **local** implementation across intermediate milestone boundaries for
  this unattended run. Do not mark Pavel's UAT as passed, deploy to production, push to a remote,
  promote releases, or mutate a live Jira tenant without separate explicit authorization.

## Worktree and tooling

1. Inspect `git status`, current diffs, and the actual code before editing. Preserve all existing
   user-owned work; never reset, clean, discard, or blindly overwrite it.
2. You are authorized to make local commits after reviewing their exact scope. If safe, checkpoint
   the current planning/documentation changes and work on a dedicated `codex/v2-live-simulator`
   branch/worktree. Never force-push or rewrite history.
3. Use/install the mandatory Superpowers test-driven-development skill required by `AGENTS.md`
   through the supported plugin or project-local mechanism if it is not already callable. Use the
   available Python clean-code skills for backend work. If the platform itself requires an
   unavailable human approval to install the mandatory skill, continue every safe non-code setup
   task and report that one genuine blocker; never pretend the skill is active.
4. Install ordinary local development dependencies when needed. Never expose or commit secrets.
5. Use subagents for bounded parallel research, test analysis, or non-overlapping implementation
   where helpful, but keep a single writer for migrations and shared contracts.

## Execution priorities

Start coding promptly after a short inspection and near-term task split. Work in this order while
keeping every completed slice usable:

1. Establish a clean baseline and additive v2 boundary without breaking v1.
2. Implement Milestone M1: persisted team blueprints, members/responsibilities, business calendar,
   backlog, status visits, statistical dwell/touch progression, capacity/WIP, fixed Scrum planning
   and lifecycle, restart-safe scheduler state, activity, and calibration ground truth.
3. Prove an autonomous Scrum vertical slice locally with a fake Jira adapter: create a team, plan a
   sprint, advance work over multiple ticks, cross a sprint boundary, carry unfinished work without
   penalty, restart, and resume without downtime catch-up.
4. Continue into Milestone M2 when M1 is green: durable Jira outbox/provisioning abstractions,
   idempotent project/board/issue/sprint projection, typed authenticated control APIs, and the
   private Codex skill/MCP surface. Use fakes unless a disposable live target is explicitly
   authorized.
5. If time remains, continue the next coherent M3 slices, prioritizing Jira manual-intervention
   polling/reconciliation and required causal risks before content/UI polish.

Do not prioritize Kanban, a rich UI, deployment, or speculative scaling ahead of a reliable Scrum
and Codex vertical slice.

## Engineering rules

- Follow strict RED → GREEN → REFACTOR TDD for every production behavior. Never weaken or delete a
  test merely to obtain green output.
- Prefer additive v2 modules and migrations. Reuse sound current components, but do not route v2
  production through the existing whole-sprint precompute path.
- Keep domain mechanics independent of Jira and OpenAI network calls.
- Commit internal state, activity/ground truth, and Jira intent atomically; perform external calls
  asynchronously and idempotently.
- Preserve actual Jira assignee/reporter after creation; simulated handoffs use internal state plus
  `sim_assignee`/`sim_reporter`. Emit no v2 Jira comments.
- Treat supported manual Jira changes as attributed inputs. On restart, reconcile Jira before new
  lifecycle progress or outbound delivery.
- Use deterministic seeded randomness and retain enough provenance to explain every statistical
  outcome. Let the implementation choose practical initial formulas and versioned starter values.
- Avoid placeholders on the active path. A smaller complete vertical slice is better than many
  disconnected stubs.
- Keep functions/modules focused, typed, and testable under the repository clean-code rules.

## Documentation and verification

For every completed implementation slice, update the relevant backlog milestone/task plus
`changelog.md`, `assumptions.md`, `README.md`, `agent_instruction.md`, and concise evidence under
`evidence/v2/`, as required by `AGENTS.md`. Create only the near-term task entries actually needed;
do not recreate the former 96-task plan.

Run focused tests during each TDD cycle and, before the final handoff, run all feasible checks:

- backend test suite and Ruff;
- migration upgrade/rollback/upgrade against disposable SQLite data;
- frontend tests/build for any touched frontend code;
- autonomous v2 smoke test with fake Jira, including restart;
- `git diff --check` and a full changed-file review.

Diagnose and fix failures within scope. Clearly distinguish pre-existing failures, environment-only
limitations, and failures introduced by this run. Never claim live Jira, deployment, or production
acceptance that was not actually performed.

## Morning handoff

Finish with the repository in the strongest green state attainable and provide one concise handoff
containing:

- the working behavior delivered, organized by milestone;
- exact test/lint/build/migration/smoke results;
- local commits and final worktree status;
- how to run and observe the new vertical slice;
- remaining work and genuine external blockers;
- the exact next highest-value implementation slice.

Do not end with a question about a mundane choice. If a true blocker prevents one area, continue all
other safe work and report the blocker only in the final handoff.

---

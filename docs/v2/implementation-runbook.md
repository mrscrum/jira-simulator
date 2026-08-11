# Jira Team Simulator v2 — Implementation Runbook

> **OPTIONAL REFERENCE.** The active direction is [`high-level-plan.md`](high-level-plan.md).
> Follow `/AGENTS.md`; do not treat the former 96-task sequence as a product requirement.

This runbook makes task execution resumable across agents and context windows. It supplements, but
does not weaken, `/AGENTS.md`.

## 1. Preconditions Before Any Code

1. The planning/assessment changes must be checkpointed in Git. Do not stash, reset, clean, or
   overwrite an unowned dirty worktree.
2. Create a dedicated branch and worktree, recommended name `codex/v2-live-simulator`.
3. Confirm the v2 documents and `/backlog/v2/` exist in that worktree.
4. Verify the mandatory obra/superpowers TDD skill is installed and callable. Clean-code skills are
   currently present, but the repository audit found no Superpowers TDD skill in the tree.
5. Install the declared backend/frontend development dependencies through the normal environment;
   never modify source merely because a local executable is missing.
6. Run and record the clean baseline before changing implementation.

If any precondition fails, `V2-S0-T02` or `V2-S0-T03` remains incomplete and code work stops.

## 2. Task Selection

The `/backlog/v2/` files are the execution source of truth. Select the lexicographically first
unchecked task whose dependencies and external prerequisites are complete. Never skip a blocked
task to implement a dependent task.

Before marking a task in progress, read:

- its stage file and task row in `implementation-plan.md`;
- every referenced requirement, decision, contract, and invariant;
- the current `agent_instruction.md` handoff;
- `git status --short --branch`; and
- the actual modules/tests named by the task.

Only one writing agent may own a task/worktree at once. Parallel agents may perform read-only review,
test analysis, or independent design critique. Database migrations and shared contracts are always
single-writer work.

## 3. Task State

Use the marker format required by `/AGENTS.md`:

- `[ ] ID — title` — ready or in progress; append `— in progress YYYY-MM-DD by <agent>` while owned.
- `[x] ID — title — completed YYYY-MM-DD` — evidence and mandatory docs are complete.
- `[~] ID — title — delayed, reason: ...` — explicitly deferred without deletion.
- `[!] ID — title — blocked by: ...` — external/decision blocker.

Stage status moves `NOT STARTED → IN PROGRESS → IN UAT → COMPLETE`. Only Pavel's recorded UAT
acceptance changes `IN UAT` to `COMPLETE`.

## 4. Per-Task Execution Loop

Every code task follows this exact loop:

1. **Restate contract:** list goal, dependencies, in-scope files, invariants, and done evidence.
2. **Inspect:** trace the current active code path and overlapping worktree changes.
3. **RED:** write the smallest meaningful failing test. Run it and retain the failure summary. A test
   that passes before implementation is not RED and must be corrected.
4. **GREEN:** write only enough production code to satisfy the test. Run focused tests.
5. **REFACTOR:** improve names/responsibilities/duplication while focused tests remain green.
6. **Regression:** run the affected stage suite plus mandatory global checks.
7. **Evidence:** add/update `/evidence/v2/<task-id>/README.md` with commands, results, fixtures,
   migrations, screenshots/read-backs, and external Jira IDs. Never store secrets.
8. **Documentation:** update `changelog.md`, `assumptions.md`, `README.md`, `agent_instruction.md`, and
   the backlog marker. Update contracts/ADRs only through an approved change.
9. **Diff audit:** inspect `git diff --check`, `git status`, and every changed hunk. Confirm no
   unrelated user change was overwritten.
10. **Checkpoint:** make one reviewable task commit only when Git actions are authorized. Otherwise
    leave an explicit handoff with exact changed paths and do not claim an isolated checkpoint.

Documentation-only tasks replace RED/GREEN with a link/format/traceability check but still complete
steps 1, 2, and 6–10.

## 5. Standard Verification Commands

Commands may be adapted only to the actual documented environment, and the adaptation must be
recorded. Expected baseline commands are:

```bash
cd backend
.venv/bin/python -m pytest tests/ --tb=short -q
.venv/bin/python -m ruff check app tests

cd ../frontend
npm test
npm run build

cd ..
git diff --check
```

Migration tasks additionally run, against disposable SQLite files:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade -1
.venv/bin/alembic upgrade head
```

Never run a downgrade against production. Stage gates add the commands and artifacts in
`verification-matrix.md`.

## 6. Evidence Contract

Each task evidence record contains:

- task ID, date, agent, branch, starting and ending commit/worktree state;
- requirements/decisions/contracts verified;
- RED command and expected/actual failure;
- GREEN/refactor/regression commands with exit status and concise result;
- migration upgrade/rollback result when applicable;
- external IDs and read-back payload hashes, with secrets redacted;
- screenshots or export/checksum paths when required;
- deviations, limitations, new assumptions, and follow-up task IDs; and
- next ready task and prerequisites.

Generated large logs belong in ignored/artifact storage with a checksum and durable location, not in
Git. Small human-readable summaries and schemas belong in the repository.

## 7. Handoff Template

At every context/task boundary, replace the current handoff section of `agent_instruction.md` with:

```text
Current v2 stage/gate:
Last completed task and reason:
Authoritative plan/contract versions:
Changed files and purpose:
Migrations/external Jira resources created:
Last green commands and results:
Known failures, conflicts, and gotchas:
Assumptions recorded:
Next ready task:
Next task dependencies/external prerequisites:
Worktree/branch status:
```

There must be no unclassified TODO. Convert it to a backlog task, limitation, assumption, or blocker.

## 8. Automatic Progression and Human Gates

An agent may progress through all ready tasks in an approved stage without asking repeated design
questions. It must stop at:

- stage UAT/deployment sign-off required by `/AGENTS.md`;
- live Jira project creation when no confirmed preview/test prefix or insufficient permission exists;
- production migration/deployment without the required backup and Pavel's authorization;
- live expansion beyond five teams;
- a new product/architecture choice not resolved by the approved contracts; or
- any stop condition below.

Automated evidence moves a stage to `IN UAT`, never directly to `COMPLETE`.

## 9. Stop and Escalation Conditions

Stop before mutation when:

- a required task field, contract, dependency, or evidence threshold is missing or says `TBD`;
- the task would change an accepted requirement, invariant, public contract, or ADR;
- a dirty hunk overlaps task files and ownership is unclear;
- an additive migration cannot preserve current v1 data or downgrade safely on a disposable copy;
- Jira permissions/topology contradict company-managed project/board provisioning;
- a destructive Jira operation lacks an exact target, preview, confirmation, and cleanup policy;
- a manual Jira state cannot be represented by the intervention contract;
- Jira read-back remains divergent after the bounded retry/reconciliation procedure;
- a secret appears in code, fixture, output, screenshot, or evidence;
- a statistical check has no fixed algorithm, seed/substream, sample size, or tolerance;
- SQLite shows persistent locking/integrity failure at the approved soak threshold;
- the actual Jira assignee/reporter would be changed by a v2 payload;
- a v2 code path would emit a Jira comment; or
- two writers could advance the same team/version.

Ordinary failing RED tests, implementation mistakes, and refactoring difficulty are not escalation
conditions. Diagnose and continue within the task.

## 10. Jira Safety

- Run unit/contract tests against fakes first.
- Live integration tests require `INTEGRATION_TESTS=true`, an explicitly designated Jira sandbox,
  and a unique configured project prefix.
- Discovery/read-back is allowed before mutation; project creation requires the confirmed
  `create_team` preview/confirmation flow or a specific UAT authorization.
- Do not automatically delete projects, boards, sprints, or issues. Cleanup is a separate confirmed
  operation and is not part of MVP tools.
- Capture Jira resource IDs in evidence, not credentials or full authorization headers.
- Test human intervention with a designated disposable issue/sprint and verify echo suppression.

## 11. Migration and Rollback

- Migrations after the assessed baseline are additive and sequential.
- Do not edit migrations `001`–`012`.
- V1 rows default to `runtime_version=1`; no automatic conversion starts v2 simulation.
- New v2 teams use `runtime_version=2`.
- Data import from a v1 timing/workflow template creates a new versioned copy and retains the source.
- Before deployment, back up the SQLite file and prove restoration to a disposable path.
- Rollback disables v2 routing/scheduler and restores the prior application image; it does not drop
  v2 evidence tables or delete Jira resources.

## 12. Contract Change Procedure

If evidence shows an accepted design cannot meet a gate:

1. stop dependent work;
2. write a short proposed ADR with evidence and alternatives;
3. mark affected backlog tasks blocked;
4. ask Pavel for one concrete decision; and
5. after approval, update requirements, contracts, architecture, verification, tasks, assumptions,
   and handoff together before resuming.

Never make the implementation pass by weakening a test, narrowing the original requirement, or
silently redefining completion.

# Jira Team Simulator v2

Implementation status: **NOT STARTED**

Pavel requested a high-level plan and explicitly left implementation detail to the capable model
that will build it. The active product and architecture plan is therefore:

- [`high-level-plan.md`](high-level-plan.md)

To launch a long, minimally supervised implementation run, use:

- [`implementation-prompt.md`](implementation-prompt.md)

Before implementation, also read `/AGENTS.md`, the current-code assessment in
`/docs/requirements-functionality-map.md`, and the milestone status in `/backlog/v2/README.md`.

The other files in this directory are retained as optional design exploration from the planning
conversation. They can inform implementation, but their low-level algorithms, schemas, 96-task
breakdown, and acceptance mechanics are **not** the active contract and must not override the
high-level plan or a later instruction from Pavel.

## Requirements Authority

When sources conflict, use this order:

1. A later explicit instruction from Pavel.
2. The mandatory development, TDD, documentation, deployment, and UAT process in `/AGENTS.md`.
3. `high-level-plan.md`, which `/AGENTS.md` designates as superseding its older product examples
   where they differ.
4. The current-state evidence in `/docs/requirements-functionality-map.md`.
5. Existing code and tests, which describe v1 behavior but do not redefine v2 requirements.
6. Historical specifications, plans, handoffs, backlog labels, and comments.

An agent must not silently resolve a real conflict that changes the product direction. Record it
and ask Pavel; ordinary implementation choices belong to the implementing model.

## Historical Documents — Do Not Execute

The following files remain useful as historical evidence and sources of selectively reusable
ideas, but their implementation instructions are superseded:

- `/HANDOFF.md`
- `/cc-initiate-project.md`
- `/stage-0-prompt.md`
- `/stage-1-prompt.md`
- `/stage2.md`
- `/stage3.md`
- `/stage4.md`
- `/docs/simulation-engine-rewrite-requirements.md`
- `/docs/baseline-template-spec.md`
- `/docs/plan/phase-01-*.md` through `/docs/plan/phase-10-*.md`
- the legacy root files under `/backlog/`

In particular, historical files do not override the active requirements for persisted live
operation, unchanged carryover without an automatic penalty, or internal-only transcripts.

## Current Execution Pointer

The high-level plan is complete. No implementation code was changed. Before code starts, preserve
and checkpoint the current dirty documentation worktree, verify the mandatory TDD skill required by
`/AGENTS.md`, and use a designated disposable Jira project/tenant for the first provisioning test.

## Resumption Rule

At every new context or agent handoff:

1. Run `git status --short --branch` and preserve all changes whose ownership is unclear.
2. Read the active milestone and choose a reviewable implementation slice.
3. Re-run the last recorded green baseline or explain why it cannot run.
4. Execute that slice through RED → GREEN → REFACTOR.
5. Store evidence and update all mandatory handoff documents before selecting another slice.

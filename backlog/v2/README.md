# Jira Team Simulator v2 Backlog

Product authority is [`/docs/v2/high-level-plan.md`](/docs/v2/high-level-plan.md). Pavel asked that
implementation detail be left to the capable implementing model, so this backlog tracks outcomes,
not a fixed microtask sequence.

## Milestones

- [x] M0 — Agree requirements, architecture, and delivery order — completed 2026-08-10
- [ ] M1 — Deliver the persisted Scrum simulation core — **IN PROGRESS**; active near-term plan:
  [`m1-deterministic-kernel.md`](m1-deterministic-kernel.md)
- [ ] M2 — Deliver one-team live Jira and Codex alpha
- [ ] M3 — Add manual Jira reconciliation, risks, content, transcripts, and ground truth
- [ ] M4 — Release the dashboard-backed five-team Scrum MVP
- [ ] M5 — Add and accept the Kanban vertical slice
- [ ] M6 — Validate 11–14-team scale and harden operations

For each milestone, the implementing model should create only the reviewable, context-sized tasks
needed at that time, following `/AGENTS.md`, and update the relevant stage file before code changes.

The existing stage files contain a detailed planning draft created before Pavel asked for a
high-level plan. They are reference material only; their task IDs and sequencing are not binding.

The reviewed persistence spine is complete through revision 014. Deterministic-kernel Task 3 is
implemented locally with exact HMAC-U53 decisions and bounded dwell/touch sampling. Task 4, the
dual-clock/DST-safe business calendar, remains open; completing it will not by itself complete M1.

Before each M1 slice, preserve unrelated work and verify the mandatory Superpowers TDD skill required
by `/AGENTS.md`. Live Jira mutation always requires a designated disposable project/tenant and
explicit authorization.

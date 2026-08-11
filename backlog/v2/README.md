# Jira Team Simulator v2 Backlog

Product authority is [`/docs/v2/high-level-plan.md`](/docs/v2/high-level-plan.md). Pavel asked that
implementation detail be left to the capable implementing model, so this backlog tracks outcomes,
not a fixed microtask sequence.

## Milestones

- [x] M0 — Agree requirements, architecture, and delivery order — completed 2026-08-10
- [ ] M1 — Deliver the persisted Scrum simulation core — **IN PROGRESS**; the reviewed
  persistence-spine and deterministic-kernel plans are complete, and the next slice needs a new
  context-sized plan
- [ ] M2 — Deliver one-team live Jira and Codex alpha
- [ ] M3 — Add manual Jira reconciliation, risks, content, transcripts, and ground truth
- [ ] M4 — Release the dashboard-backed five-team Scrum MVP
- [ ] M5 — Add and accept the Kanban vertical slice
- [ ] M6 — Validate 11–14-team scale and harden operations

For each milestone, the implementing model should create only the reviewable, context-sized tasks
needed at that time, following `/AGENTS.md`, and update the relevant stage file before code changes.

The existing stage files contain a detailed planning draft created before Pavel asked for a
high-level plan. They are reference material only; their task IDs and sequencing are not binding.

The reviewed persistence spine is complete through revision 014. The
[`m1-deterministic-kernel.md`](m1-deterministic-kernel.md) plan is also complete: Task 3 provides
review-hardened slotted/reconstruction-resistant HMAC-U53 provenance, scoped safe-integer
coordinates, and formula-bound dwell/touch samples; Task 4 provides pure dual-clock/DST-safe
business-calendar, fixed-cadence, and `US_FEDERAL_V1` horizon primitives. M1 remains in progress.
Work/sprint/status-visit persistence is the next plan decision and must not be guessed from the
historical detailed backlog.

Before each M1 slice, preserve unrelated work and verify the mandatory Superpowers TDD skill required
by `/AGENTS.md`. Live Jira mutation always requires a designated disposable project/tenant and
explicit authorization.

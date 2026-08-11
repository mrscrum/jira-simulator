# Jira Team Simulator v2 Backlog

Product authority is [`/docs/v2/high-level-plan.md`](/docs/v2/high-level-plan.md). Pavel asked that
implementation detail be left to the capable implementing model, so this backlog tracks outcomes,
not a fixed microtask sequence.

## Milestones

- [x] M0 — Agree requirements, architecture, and delivery order — completed 2026-08-10
- [ ] M1 — Deliver the persisted Scrum simulation core — **IN PROGRESS**; the reviewed
  persistence-spine and deterministic-kernel plans are complete, Task 5 has added authoritative
  state at revision 015 and passed its first review-fix gate, and Task 6 remains open in
  [`m1-scrum-state.md`](m1-scrum-state.md)
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
business-calendar, fixed-cadence, and review-hardened `US_FEDERAL_V1` horizon primitives. The
starter year is team-zone-derived, only available IANA keys are accepted, canonical horizons are
authenticated before use, stale extensions catch up idempotently in ten-year blocks, and extreme
timezone/local-boundary conversions expose a stable domain range error. M1 remains in progress. The
active [`m1-scrum-state.md`](m1-scrum-state.md) plan freezes exactly two context-sized slices:
Task 5 is complete with review-hardened revision-015 authoritative state persistence, sealed and
blueprint-authenticated timing provenance, and typed semantic-owner constraints; Task 6 remains
open to integrate that state with the existing atomic runtime-CAS/live-ledger unit of work without
a revision 016. Capacity allocation,
live flow, planning, lifecycle mechanics, dependencies, risks, scheduler/external wiring, and UAT
remain deferred.

Before each M1 slice, preserve unrelated work and verify the mandatory Superpowers TDD skill required
by `/AGENTS.md`. Live Jira mutation always requires a designated disposable project/tenant and
explicit authorization.

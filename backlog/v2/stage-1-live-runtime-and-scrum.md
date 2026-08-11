# V2 Stage 1 — Durable Live Runtime and Scrum Kernel

> **DETAILED REFERENCE DRAFT — NOT ACTIVE.** See [`README.md`](README.md) for milestone status.
Status: NOT STARTED

## Tasks
- [ ] V2-S1-T01 — Add isolated blueprint, calendar, policy, and runtime persistence
- [ ] V2-S1-T02 — Add member responsibility and availability persistence
- [ ] V2-S1-T03 — Add canonical route and timing-catalog persistence
- [ ] V2-S1-T04 — Add v2 work, sprint, status-visit, and factor persistence
- [ ] V2-S1-T05 — Add append-only activity and ground-truth ledgers
- [ ] V2-S1-T06 — Add command audit and durable idempotency
- [ ] V2-S1-T07 — Add Jira outbox/resource maps and atomic unit of work
- [ ] V2-S1-T08 — Implement exact deterministic RNG substreams
- [ ] V2-S1-T09 — Implement exact bounded quantile and touch samplers
- [ ] V2-S1-T10 — Implement dual-clock business-calendar primitives
- [ ] V2-S1-T11 — Implement responsibility, proficiency, capacity, and WIP allocation
- [ ] V2-S1-T12 — Implement persistent status entry and live-flow transaction
- [ ] V2-S1-T13 — Implement Scrum planning policy
- [ ] V2-S1-T14 — Implement fixed lifecycle, boundary splitting, and unchanged carryover
- [ ] V2-S1-T15 — Implement deterministic backlog replenishment stub
- [ ] V2-S1-T16 — Implement scheduler ownership, controls, and restart semantics
- [ ] V2-S1-T17 — Prove a Jira-free autonomous two-sprint Scrum run

## UAT Results
(pending Gate G1 evidence and Pavel's review)

## Notes
- Starts only after Gate G0 and Stage 0 UAT.
- V2 is additive; v1 precompute/scheduler behavior remains frozen.
- Active near-term execution is tracked in [`m1-persistence-spine.md`](m1-persistence-spine.md);
  this detailed 17-task draft remains reference-only and is not activated by that plan.

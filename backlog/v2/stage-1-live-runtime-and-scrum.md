# V2 Stage 1 — Durable Live Runtime and Scrum Kernel

> **DETAILED REFERENCE DRAFT — NOT ACTIVE.** See [`README.md`](README.md) for milestone status.
Status: IN PROGRESS

## Tasks
- [x] Coherent live-team read and idempotent Scrum bootstrap — completed 2026-08-11
- [x] Honor initial Scrum boundary, DST cadence, and minimum-capacity bootstrap policy — completed 2026-08-11
- [x] Incrementally advance Scrum ticks and commit each slice atomically — completed 2026-08-11
- [x] Fixed sprint lifecycle, persisted due-team scheduling, and restart without downtime replay — completed 2026-08-11
- [x] First realism behaviors and fake-Jira vertical acceptance — completed 2026-08-11
- [x] First realism and vertical acceptance review fix round 1 — completed 2026-08-11
- [x] First realism continuation-evidence review fix round 2 — completed 2026-08-11
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
- The pragmatic live core now includes coherent reads, idempotent bootstrap, and incremental atomic
  Scrum ticks with one stale-runtime retry.
- Bootstrap remains planned until the first boundary, retains local cadence through DST, and uses
  contiguous ranked scope through configured minimum capacity.
- Fixed lifecycle now activates planned scope before work, rolls active sprints once with unchanged
  carryover ahead of ranked backlog, and emits dependent complete/create/scope/start intents.
- Persisted due-team scheduling uses one sequential team path; restart reconciles first, advances
  elapsed boundaries with zero work, records downtime, and preserves existing pending intents.
- Jira projection delivery and the first fake-Jira vertical are complete; the local observation
  reconciler remains an injected no-op until inbound Jira support is connected.
- Task 3 review fix round 1 drains exclusive due-team keyset pages beyond 100 and commits restart
  downtime evidence before zero-work lifecycle-only transitions and the final scheduling rebase.
- Review fix round 1 preserves minimum-fraction/pre-fraction-cap availability, stops at the earliest
  shared completion boundary, retains residual tick time, and emits causal ground truth.
- The fake-Jira vertical now proves dependency-ordered project/board/issue/sprint delivery, two
  lifecycle boundaries, restart without catch-up, outage recovery, and provider-success/local-
  receipt replay without duplicate resources through production seams.
- Review fix round 1 moves project/board/initial-issue composition into production bootstrap; the
  acceptance now reaches provisioning exclusively through that supported path.
- Review fix round 2 records each accepted external-dependency continuation wait delta atomically
  without redrawing or emitting duplicate activity/projection output.

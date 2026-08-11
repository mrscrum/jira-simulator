# Jira Team Simulator v2 — Verification and Acceptance Matrix

> **OPTIONAL REFERENCE.** This detailed matrix may inspire milestone tests, but the active MVP
> outcome is defined in [`high-level-plan.md`](high-level-plan.md).

Completion requires direct evidence for every row. A model/table/UI presence or a narrow unit test
does not prove an end-to-end requirement.

## Requirement Traceability

| Requirement | Primary tasks | Required direct evidence | Gate |
|---|---|---|---|
| R-TEAM-001 one team/request | V2-S0-T05, V2-S3-T01–V2-S3-T02, V2-S3-T05, V2-S3-T07, V2-S3-T13 | Codex-produced typed draft, zero server OpenAI preview calls, confirmation, lifetime idempotency, exactly one team/project/board. | G3 |
| R-TEAM-002 complete blueprint | V2-S0-T05, V2-S1-T01–V2-S1-T04, V2-S3-T01 | Draft/final schema parity; recommended catalog; full timing grid; availability/route semantics; deterministic names/collision; immutable persisted version/hash. | G3 |
| R-TEAM-003 responsibilities | V2-S1-T02, V2-S1-T11 | Eligibility, availability, labor capacity, proficiency credit, sticky/released ownership and WIP invariants. | G1 |
| R-WORK-001 rich items | V2-S1-T04, V2-S1-T15, V2-S3-T11, V2-S4-T04–V2-S4-T05 | Model/API/Jira-import/content/factor/provenance tests and representative export. | G4 |
| R-WORK-002 routes | V2-S1-T03, V2-S1-T12, V2-S2-T05–V2-S2-T06, V2-S4-T06 | Story/Bug route, exceptional blocker, Blocked-to-Done/Cancelled closure, terminal/rework, and Jira 1:1 transition read-back. | G4 |
| R-TIME-001 dual clocks | V2-S1-T10, V2-S1-T12, V2-S1-T14 | Weekend/holiday/DST fixtures; business dwell/touch, calendar analytics, and rolling holiday-horizon expansion. | G1 |
| R-STAT-001 exact baseline | V2-S0-T05, V2-S1-T03, V2-S1-T09 | Complete starter grid, exact inverse-CDF vectors, validation/bounds, empirical calibration. | G1 |
| R-STAT-002 reproducibility | V2-S1-T05, V2-S1-T08, V2-S1-T17 | Canonical encoding/digest/U53 golden vectors, cross-process independence, identical replay export checksum. | G1 |
| R-SCRUM-001 planning | V2-S1-T13, V2-S4-T05 | Capacity/rank/dependency/availability scenarios, adopted Jira rank, recorded selection/exclusions. | G4 |
| R-SCRUM-002 lifecycle | V2-S1-T14, V2-S2-T07, V2-S4-T03, V2-S4-T08 | Exact boundary/DST split, no early close, unchanged carryover, long-outage rebase, manual topology, Jira read-back. | G4 |
| R-KANBAN-001 flow | V2-S6-T01–V2-S6-T03, V2-S6-T07 | `KANBAN_BALANCED_V1` fixture, exact arrival branches/no-catch-up, total pull order, blocked/status/member WIP, emerging items, and mixed autonomy. | G6 |
| R-KANBAN-002 SLA/SLE | V2-S6-T01, V2-S6-T04, V2-S6-T07 | Every class/start/skipped-start/pause/stop/warning/breach business-clock vector; proof no Jira SLA API call. | G6 |
| R-RISK-001 catalogue | V2-S4-T12–V2-S4-T16, V2-S4-T20 | Natural and forced-cause deterministic scenario for each hazard; derived long-stay/carryover cannot be directly flagged. | G4 |
| R-RISK-002 causality | V2-S0-T05, V2-S4-T10–V2-S4-T17, V2-S4-T20 | Exact profile/trigger vectors, monotonic cohorts, duration effects, forced provenance and LLM exclusion. | G4 |
| R-AUTO-001 autonomy | V2-S1-T15–V2-S1-T17, V2-S5-T12–V2-S5-T13, V2-S7-T05 | Jira-free two-sprint run, five-Scrum-team release soak, later mixed-team regression. | G5 + G7 |
| R-AUTO-002 restart | V2-S1-T14, V2-S1-T16, V2-S4-T08, V2-S5-T12–V2-S5-T13, V2-S7-T02, V2-S7-T04 | Kill/restart at all commit points; startup Jira drain precedes one rebase; no ordinary downtime work/transcript. | G5 + G7 |
| R-JIRA-001 provisioning | V2-S0-T09, V2-S2-T01, V2-S2-T03–V2-S2-T05, V2-S3-T02, V2-S3-T13 | Early target-tenant public-API topology proof; capability/pagination report; exact company-managed project, issue-type/workflow scheme, board/filter/column read-back; partial retry and duplicate prevention. | G0 + G3 |
| R-JIRA-002 projection | V2-S1-T07, V2-S2-T02, V2-S2-T06–V2-S2-T09, V2-S4-T08 | Atomicity, lease-token/epoch CAS and late result, dependencies, create settlement/no blind retry, crash/replay, supersession, 429/outage/freeze/backpressure and read-back. | G2 + G4 |
| R-JIRA-003 identity/comments | V2-S2-T04, V2-S2-T06, V2-S2-T09, V2-S4-T05, V2-S4-T20 | Payload/read-back: simulator never updates real identity, human real identity is preserved, virtual fields work, zero v2 comments. | G4 |
| R-JIRA-004 manual intervention | V2-S4-T01–V2-S4-T09, V2-S4-T20 | Signed registered webhook plus lost-webhook poll; complete sprint/card/field/status/delete/topology policy; event lineage; explicit conflict resolution. | G4 |
| R-CONTENT-001 generation | V2-S4-T17, V2-S4-T20 | Five jobs/cycle, 45s, one retry, 1,200 output tokens, override provenance, safe backfill, structured validation and nonblocking fallback. | G4 |
| R-CONTENT-002 transcripts | V2-S4-T18–V2-S4-T20 | Exactly one eligible processed workday, none for nonworking/missed downtime, source fidelity, idempotency, zero Jira comments. | G4 |
| R-CODEX-001 plugin | V2-S3-T03–V2-S3-T13, V2-S4-T19, V2-S5-T03 | Auth/TLS/scopes, conversation-to-draft-to-team evidence, staged tool registration, audits, server-key separation. | G3 + G5 |
| R-CODEX-002 control parity | V2-S3-T06–V2-S3-T12, V2-S4-T19, V2-S5-T03, V2-S5-T10, V2-S5-T13, V2-S6-T06 | Scrum HTTP/MCP parity at G5, additive Kanban parity at G6, and proof no raw mutation tool exists. | G5 + G6 |
| R-UI-001 dashboard | V2-S5-T01, V2-S5-T04–V2-S5-T09 | Browser/screenshots, filtering/pagination, runtime/work, conflicts/sync, transcript and ground-truth evidence. | G5 |
| R-GT-001 ground truth | V2-S1-T05, V2-S5-T01–V2-S5-T03, V2-S5-T07 | Required records, append pagination, Jira-key lookup, correction lineage, deterministic ZIP/NDJSON manifest/checksums, direct HTTP and MCP-resource retrieval, auth/isolation, artifact expiry without source deletion. | G5 |
| R-SCALE-001 scale | V2-S0-T07–V2-S0-T08, V2-S1-T16, V2-S5-T11–V2-S5-T13, V2-S7-T03, V2-S7-T05–V2-S7-T07 | SQLite/WAL/EBS and one-writer proof, five-Scrum live release, mixed live regression, 14-team fake report, 90-day formula and DB decision. | G5 + G7 |
| R-SEC-001 private auth | V2-S3-T03–V2-S3-T05, V2-S3-T13, V2-S4-T01, V2-S5-T04, V2-S5-T10, V2-S7-T01 | Bearer issuance/digest/rotation/revocation/MCP handoff; dashboard session/CSRF; negative auth/scope/secret/TLS/webhook/public-route tests; versioned surface/tool inventory. | G3 + G5 + G7 |

## Fixed Statistical Tests

### Quantile conformance

- Unit vectors assert the inverse CDF at `u = 0, .25, .50, .99, 1` against all five anchors with
  relative/absolute tolerance `1e-9`.
- A deterministic 200,000-draw cohort per representative baseline must have empirical p25 and p50
  within 2% of configured values and p99 within 5%, unless an anchor is zero; empirical min/max must
  remain within configured bounds.
- Tests cover equal adjacent anchors, all-zero status, very small positive durations, large ratios,
  invalid order, NaN, infinity, and negative input.

### Causal direction

For each risk factor, evaluate a fixed grid of deterministic draws at a low and high adverse input
while holding all other inputs constant. The set of triggered outcomes at the lower risk must be a
subset of the higher-risk set. Formula tests also assert the exact expected probability for fixed
coefficient vectors. This avoids flaky sample-only assertions.

### Replay

Export one completed run, recreate it from the same blueprint/root seed/algorithm versions, and
compare normalized ground-truth checksums. External IDs and recording timestamps may be normalized;
database IDs may differ, while `SEMANTIC_ID_V1` IDs, mechanical decisions, samples, state versions,
and event ordering may not differ.

### Event-time and planning conformance

- One five-minute tick fixture contains dwell completion, touch completion/reallocation, two short
  transitions, and a zero-touch step. Every event is stamped at its exact semantic instant rather
  than the tick end; a loop guard rolls back its current boundary-bounded slice without partial
  credit while any earlier committed sprint/business-date boundary slice remains durable.
- Planner golden vectors cover every discrete target edge, 0/fractional/1 availability, carryover
  below/equal/above target, dependency cycles/closure, all priority/rank/UUID ties, and an oversized
  candidate followed by a fitting candidate. Replay returns the identical ordered include/exclusion
  ledger.

## Jira Acceptance Scenarios

Use a designated disposable Jira tenant/project prefix and retain resource IDs. Do not automatically
delete the projects.

1. Through documented public APIs, provision a company-managed Scrum project, dedicated issue-type
   and workflow schemes, and board twice; second run creates nothing. Read every status/transition
   and board column back, including Blocked External to Done/Cancelled; the board is created only
   after workflow association.
2. Create backlog, sprint, membership and start commands before the Jira sprint ID exists; prove
   initial `CREATE → ADD → START` and boundary graph with both carryover and newly selected scope
   projected before `START_SUCCESSOR`, while carryover precedes `COMPLETE_OLD`. Time out after Jira
   creates a sprint, observe the settlement window/repeated complete scans, and discover exactly one
   without duplication; zero/multiple candidates create a protected conflict and never a blind retry.
3. Create with stable `jira-simulator.item-id` issue property, time out after Jira accepts it, then
   reconcile without a duplicate; update estimate/content/relative rank through typed allowlists.
4. Transition Story and Bug through configured routes, including a backward transition and causal
   predecessor chain; never collapse intermediate history.
5. Complete two sprints with carryover and read every issue/sprint status back.
6. Inspect every simulator create/update payload and Jira changelog: no post-create real assignee/
   reporter update; `sim_assignee`/`sim_reporter` reflect virtual identities; no v2 comments. Change a
   real identity manually and prove the simulator preserves it without treating it as a handoff.
7. Exercise every outbox state, lease loss, 429, eight-failure exhaustion, permanent failure,
   descendant propagation/retry/rebase, timeout-after-create, duplicate delivery and temporary
   outage; recover or expose the exact conflict without duplicate resource/effect or silent divergence.
8. Pause one team, freeze another, and drive a third above outbox high water; prove distinct drain/
   fence/recovery behavior and no lost intent.
9. Manually start/complete/reopen early and late, and start a valid successor; prove the original
   cadence anchor, current-window end, exact work-started predicate, and sole-active/conflict policy.
10. Add/remove/re-add a known card; prove scope/forecast changes, capacity release, and identical
    preserved status/sample/progress on re-add. Add an unknown card and prove Jira author plus visible
    Task/3 default provenance.
11. Resize with ordinary, missing/zero-old, and unsupported-new points; prove completed-work
    preservation, future-visit size, `NO_RATIO_BASELINE`, and item-only quarantine respectively.
12. Edit priority/relative rank/content; prove next planning order changes while established quality/
    complexity does not. Ignore a LexoRank-only rebalance.
13. Move forward/skip/backward/to Blocked External/Done/Cancelled, then attempt to move out of a
    terminal state; prove visit/block/rework provenance, capacity release, and quarantine policy.
14. Delete/archive a card, edit each protected field/resource/topology, then prove tombstone or
    smallest-scope conflict and no automatic recreation/remap.
15. Register the signed webhook, deliver each intervention through it, intentionally lose selected
    deliveries, recover via paginated poll, and prove one semantic application with identity, actor,
    observed/ingested times, before/after, decision, resulting version, and outbox lineage.
16. Resolve a conflict through detect → server choices → explicit confirmation → restore/adopt → Jira
    read-back → same-key repeat; arbitrary correction payload must fail.

## Restart Matrix

Kill and restart after each of these committed/uncommitted points:

- before/after a status sample;
- before/after touch credit;
- before/after a transition and its outbox insertion;
- after Jira call but before delivery result persistence;
- before/after sprint boundary and successor membership;
- while a simulation-duration dependency/member absence is active, during an external absolute
  availability interval, and after a future agent command becomes due;
- before/after transcript job/result;
- with webhook stored but intervention not applied; and
- with team paused and with sync frozen.

Pass criteria: last committed state resumes automatically, failed transaction effects are absent,
startup poll/intervention application precedes boundary reconciliation and outbox delivery, no
ordinary overdue tick queue or downtime progress/transcript/event is created, one passed lifecycle
boundary rebases once into a current successor, simulation timers retain their remaining duration,
external current truth and due agent intent apply once with zero backfill, and no Jira effect
duplicates.

## Soak Definitions and Thresholds

### G5 five-Scrum-team live release soak

- Five heterogeneous Scrum teams cross at least two fixed sprint boundaries under an accelerated
  semantic clock while every Jira call obeys normal wall-clock pacing/rate limits. No Jira delivery
  timing is accelerated.
- After accelerated acceptance, run a separate 60-minute real-time smoke with at least 12 ordinary
  committed ticks per team.
- Across the fleet include one restart spanning multiple semantic boundaries, one 60-second Jira
  outage, one OpenAI failure window, every supported manual intervention, and every required natural
  or forced-cause risk scenario at least once.
- Pass thresholds:
  - zero invariant violations, database integrity failures, lost transitions, duplicate Jira
    resources/effects, unresolved projection divergence, or cross-team leaks;
  - zero unhandled `database is locked` failures after configured bounded retries;
  - real-time tick processing p95 below 25% of its scheduler interval and maximum below 80%;
  - after restart no ordinary overdue tick backlog exists; each next wake is at or before one
    configured interval in the future, while only committed Jira outbox work drains;
  - outbox drains to its pre-outage steady-state depth within five minutes of Jira recovery, subject
    to honored Jira `Retry-After` values;
  - all transcript/content failures use marked fallback without stopping mechanics; and
  - `PRAGMA quick_check` returns `ok` after the run and restored backup.

### G7 five-team mixed-method live regression

- Exactly three Scrum and two Kanban teams run through two Scrum boundaries and at least five Kanban
  target windows, using the same accelerated-semantic/wall-clock-Jira separation and a 60-minute
  real-time smoke.
- Apply every G5 threshold plus zero WIP-limit violations, exact business-clock warning/breach/pause/
  stop behavior, no sprint rows/commands for Kanban, and no methodology/team leakage.
- Include restart, Jira/OpenAI outage, webhook loss/duplication, and manual interventions in both
  methodologies where the policy permits them.

### Fourteen-team target soak

- Fourteen heterogeneous teams on production-class resource limits using a fake Jira adapter that
  enforces configured pacing, 429s, webhook duplication/loss, and read-back latency.
- Run 20 simulated business days and at least two restart/failure cycles; complete within 30 wall
  minutes in accelerated mode.
- Apply the same zero-defect/integrity/isolation thresholds as the five-team soak.
- Tick p95 remains below 50% of the accelerated scheduler interval or the runner demonstrates a
  stable non-growing due-tick backlog; SQLite write-lock retries remain bounded and successful.
- Measure fixed/start/end database, WAL peak, and export bytes. Calculate variable bytes per
  team-business-day from the 20-day run, count each configured team's working dates in the next 90
  calendar days, and record `fixed_end + variable_rate × projected_team_business_days × 1.25`; report
  peak WAL separately rather than treating it as retained database growth.

Passing this fake-Jira soak demonstrates headroom but does not authorize more than five live Jira
projects. Failure triggers an evidence-backed ADR; it does not automatically select PostgreSQL.

## Stage Gate Evidence Checklist

Every gate directory contains:

- immutable plan/contract version and commit;
- commands and exit codes;
- focused RED and GREEN evidence for each task;
- full backend/frontend/lint/build results;
- migration/SQLite integrity results;
- requirement row evidence links;
- external Jira resource/read-back hashes where applicable;
- screenshots/exports/checksums where applicable;
- unresolved defects with backlog IDs;
- deployment/rollback status; and
- Pavel's dated PASS/FAIL UAT note.

An absent, indirect, stale, or skipped artifact is a failed gate, not a presumed pass.

# Jira Team Simulator v2 — Decision Log

> **REFERENCE DRAFT.** Use the confirmed decisions summarized in
> [`high-level-plan.md`](high-level-plan.md). Entries that go beyond them are recommendations, not
> mandatory implementation detail.

These entries capture the detailed planning pass. Only decisions restated in
`high-level-plan.md` are active; the remainder are implementation recommendations that may be
revisited by the implementing model.

## ADR-001 — Scrum first, Kanban next

- Decision: deliver a complete Scrum/Codex vertical slice before Kanban.
- Consequence: shared models include `methodology` and policy seams immediately, but the first
  production gate does not depend on Kanban execution.

## ADR-002 — Additive v2 runtime in an isolated branch/worktree

- Decision: build an additive `v2` runtime beside v1, selected by `Team.runtime_version`.
- Consequence: existing teams and endpoints remain v1 until the five-team v2 soak passes. Do not
  delete or refactor v1 merely to make v2 cleaner. Port only explicitly approved leaf components.

## ADR-003 — Modular monolith and one writer

- Decision: one FastAPI deployable, one APScheduler owner, one application replica, one database.
- Consequence: domain modules are separated in code but do not require queues or microservices.
  Every team has at most one runtime writer.

## ADR-004 — SQLite/WAL on EBS initially

- Decision: production data lives at `/data/simulator.db` on the encrypted EBS volume. Use WAL,
  foreign keys, busy timeout, bounded write transactions, backup, and integrity checks.
- Consequence: PostgreSQL is not an MVP prerequisite. A migration is proposed only if the approved
  11–14-team soak demonstrates persistent lock/throughput failure.

## ADR-005 — Persisted live ticks, not sprint precomputation

- Decision: real operation advances committed issue/runtime state at each live tick.
- Consequence: `precompute.py` may remain for v1, forecasts, fixtures, or calibration, but cannot
  schedule v2 production behavior. Live agent and Jira interventions affect the next committed tick.

## ADR-006 — Ordinary state plus append-only evidence

- Decision: use ordinary authoritative relational tables plus append-only activity/ground-truth
  records. Do not implement full event sourcing.
- Consequence: each mutation transaction updates state, appends evidence, and writes Jira intents.
  State can be queried efficiently while every decision remains auditable.

## ADR-007 — Database authority with controlled Jira-originated commands

- Decision: the database owns committed execution/history. Jira is a convergent projection and an
  allowed source of explicit human interventions.
- Consequence: supported Jira changes are ingested idempotently as commands/events and then become
  committed state; they are not blindly overwritten. Unmapped/invalid changes are quarantined and
  surfaced. Simulator writes are echo-suppressed.

## ADR-008 — New company-managed Jira project per team

- Decision: every team provisions a new company-managed project and matching Scrum or Kanban board.
- Consequence: provisioning requires Jira admin capability checks, stable naming/collision rules,
  asynchronous operation status, idempotency, and explicit cleanup safety.

## ADR-009 — Virtual Jira identities and no v2 comments

- Decision: handoffs use `sim_assignee` and `sim_reporter`; simulator-originated writes never change
  actual Jira assignee/reporter after creation, while direct human Jira changes are preserved. V2
  does not publish transcripts or routine narrative as Jira comments.
- Consequence: every Jira payload is contract-tested. Legacy comment support may remain isolated.

## ADR-010 — Dual clocks and business-time work

- Decision: retain UTC instants, calendar elapsed duration, and team-business elapsed duration.
  Work and Kanban SLA/SLE advance only in business time.
- Consequence: calendars are team-owned and timezone/DST aware. Sprint start/end are fixed planned
  instants, not a count of work completed.

## ADR-011 — Exact bounded quantile sampler

- Decision: full-status duration uses a bounded inverse CDF with anchors at minimum, p25, p50, p99,
  and maximum, interpolated monotonically in `log1p(hours)` space.
- Consequence: `inverse_cdf(.25/.50/.99)` equals the configured anchors within numerical tolerance;
  tails are bounded; the old approximate two-parameter log-normal is not used by v2.

## ADR-012 — Separate dwell and touch requirements

- Decision: a status visit samples a full business-time dwell requirement and a bounded touch-work
  requirement. Capacity controls touch progress; transition requires both to be complete.
- Consequence: queue, touch, business dwell, and calendar dwell are recorded separately and can be
  analyzed without double-counting.

## ADR-013 — Stable canonical statuses with issue-type routes

- Decision: a team owns canonical statuses and each issue type owns an ordered route through them.
- Consequence: routes may skip Analysis, QA, or PO Review, but cannot invent unmapped Jira statuses.
  Manual Jira moves use the same route policy and quarantine invalid statuses.

## ADR-014 — Fixed Scrum boundaries and unchanged carryover

- Decision: the simulator never ends a sprint early. At the planned end, unfinished work carries to
  the next sprint with status and remaining work unchanged and no automatic penalty.
- Consequence: an explicit human Jira completion may override the boundary, and an explicit risk
  may add work, but both are separately attributed events.

## ADR-015 — Internal business-hour Kanban SLA/SLE

- Decision: Kanban SLA/SLE is an internal policy clock with configurable start, pause, warning,
  target, and stop states.
- Consequence: Jira Service Management SLA configuration is out of scope.

## ADR-016 — Versioned causal risk model

- Decision: initial risk hazards use bounded logistic probabilities and versioned coefficients;
  duration effects use bounded explicit multipliers or paused clocks.
- Consequence: factors are monotonic where configured, seeds are reproducible, and every decision
  retains base probability, coefficients, factor values, final probability, draw, and outcome.

## ADR-017 — Mechanics choose content quality, not the LLM

- Decision: description-quality and latent-complexity factors are deterministic domain samples.
  The OpenAI content job is instructed to generate prose consistent with them.
- Consequence: model output can narrate but cannot silently decide simulation mechanics.

## ADR-018 — Codex conversation separated from server content generation

- Decision: Codex plus a private scoped MCP plugin handles user conversation/control. The server's
  OpenAI API key handles autonomous internal content jobs only.
- Consequence: no server-key proxy chat endpoint is built. MCP responses are structured simulator
  data, and the server key is never returned to the plugin.

## ADR-019 — Internal transcript documents

- Decision: create one idempotent team transcript per working business date after workday end,
  stored and rendered internally.
- Consequence: no Jira transcript comments; deterministic fallback content preserves operation when
  OpenAI is unavailable.

## ADR-020 — Resume without ordinary downtime catch-up

- Decision: restart automatically from the last transaction, grant no downtime progress, and replay
  no missed ordinary events or transcripts. Reconcile at most one already-passed lifecycle boundary.
- Consequence: complete historical continuity/catch-up is deferred. After a long outage, one
  successor is placed in the current window from the original local cadence anchor; skipped empty
  windows are counted but not materialized.

## ADR-021 — Synthetic dependencies before true cross-team dependencies

- Decision: MVP external dependencies are deterministic synthetic blockers. True work-item links
  across simulated teams are post-MVP.
- Consequence: the data model retains blocker provenance and can be extended without changing the
  basic pause/release/resume mechanics.

## ADR-022 — Observation-first UI

- Decision: replace configuration-first navigation with global/team event feeds, runtime health,
  current work, risks, Jira sync, transcripts, ground truth, and emergency controls.
- Consequence: polling is sufficient initially; a rich team builder and WebSockets are deferred.

## ADR-023 — Ground truth retained for calibration

- Decision: retain complete ground truth for the life of an MVP run and expose authenticated APIs
  and deterministic exports correlated to Jira IDs. A derived private download archive expires
  after 24 hours; source rows and export metadata/checksums do not.
- Consequence: no automatic source-ledger deletion is enabled initially. Storage growth is monitored
  at soak and a later retention policy must preserve exportability and audit lineage.

## ADR-024 — Five-team start and measured 11–14-team gate

- Decision: accept the first rollout at five teams. Test 14 teams with a fake Jira adapter before
  authorizing live expansion.
- Consequence: database or deployment changes require measured evidence, not speculative scaling.

## ADR-025 — Human intervention conflict policy

- Authority: Pavel explicitly added on 2026-08-10 that simulator-managed projects must survive
  manual Jira sprint stops/restarts and card addition, removal, resize, and status moves.
- Decision: human-writable Jira fields and lifecycle actions use a human-wins-after-ingestion policy;
  simulator integration/provenance fields remain protected. Unsupported changes isolate the
  affected issue or lifecycle, never the global scheduler.
- Consequence: webhook and poll observations enter one idempotent inbox, every intervention is
  attributed, and outbox reconciliation must distinguish human changes from delivery failure.

## ADR-026 — Versioned recommended starter catalogs

- Decision: omitted choices resolve from immutable `SCRUM_BALANCED_V1` or, after G5,
  `KANBAN_BALANCED_V1`, including complete timing/risk/routes/role/calendar/backlog values and exact
  Kanban arrival/class/WIP/SLE policy defined in `contracts/starter-catalog.md`.
- Consequence: Codex can honor “use recommended” without a clarification loop, and implementation
  agents may not invent missing statistical or risk values. Calibration changes create a new catalog
  version.

## ADR-027 — Exact deterministic random algorithm

- Decision: v2 starts with `HMAC_SHA256_U53_V1`, RFC 8785 canonical decision keys, semantic
  occurrence sequences, and fixed big-endian 53-bit conversion described in `architecture.md`.
- Consequence: replay is cross-process/language stable and independent of processing order or
  database autoincrement IDs.

## ADR-028 — Semantic replay identities and event-time ticks

- Decision: derive RNG entity identities with fixed-namespace `SEMANTIC_ID_V1` from the resolved
  blueprint and persisted semantic ordinals. Within each scheduler interval, use
  `EVENT_TIME_LOOP_V1` to advance to exact modeled completions/boundaries and reallocate remaining
  labor instead of timestamping all effects at the tick end.
- Consequence: a fresh-database replay can differ in storage IDs but not draws/event order, and a
  five-minute wake interval does not quantize modeled dwell or touch transitions.

## ADR-029 — Exact Scrum planner

- Decision: use `SCRUM_PLANNER_V1`: an inclusive discrete raw target scaled by scheduled
  availability, mandatory unchanged carryover, priority/rank/semantic-ID ordering, dependency-frontier
  eligibility, and continuing first-fit packing.
- Consequence: carryover may exceed the sampled target without being dropped or penalized, while
  every new-scope inclusion/exclusion is replayable and explainable.

## ADR-030 — Durable outbound state and original-anchor manual cadence

- Decision: use the complete typed Jira outbox state machine and threshold transaction in
  `contracts/jira-operations.md`. Manual sprint boundaries create/adopt a current-window successor
  whose end comes from the original cadence anchor; they never silently re-anchor future sprints.
- Consequence: unknown outcomes, terminal descendants, fleet backpressure, sprint-create timeouts,
  and Jira-side early/late/reopen behavior have deterministic recovery/conflict paths.

## ADR-031 — Official-API project topology with an early tenant proof

- Decision: `OFFICIAL_PROJECT_SCOPED_V1` provisions a dedicated company-managed project, dedicated
  issue types and issue-type scheme, canonical statuses/workflow/workflow scheme, and only then its
  Scrum or Kanban board, using documented public Jira Cloud APIs. Required board columns are verified
  by complete configuration read-back; no private endpoint or browser automation is used to edit
  columns.
- Consequence: Gate G0 includes a disposable target-tenant mutation spike. If a newly created board
  does not map all canonical statuses exactly once by their status categories, implementation stops
  before the simulation kernel until Pavel approves a supported topology alternative.

## ADR-032 — Opaque API credentials and same-origin dashboard sessions

- Decision: private API/MCP clients use distinct 256-bit opaque bearer credentials stored only as
  SHA-256 digests; the MCP receives its credential from deployment secrets. The dashboard exchanges
  a dashboard-kind credential once for a bounded Secure/HttpOnly/SameSite=Strict same-origin session
  and uses strict Origin plus session-bound CSRF protection for mutations.
- Consequence: no long-lived MCP bearer is embedded in frontend code/browser storage. Issuance,
  rotation with a 24-hour overlap, revocation, session expiry, and actor/scope audits are required
  before remote Codex alpha or dashboard release.

## ADR-033 — Deterministic private calibration archives

- Decision: ground-truth export produces a deterministic ZIP containing canonical NDJSON plus a
  manifest, retrieved only through scoped HTTP or an MCP resource. Archive bytes expire after 24
  hours while metadata/checksums and the append-only source ledger remain.
- Consequence: calibration consumers can verify repeatable checksums without raw database/file paths,
  public signed URLs, or indefinite accumulation of derived archives.

## ADR-034 — Restrictive availability overlays and paused commands

- Decision: confirmed blueprint availability intervals do not overlap. Independently sourced
  runtime risk/operator overlays may overlap and compose using the minimum active fraction and
  capacity cap. Operator commands accepted while paused remain durable but apply mechanics only in
  the first eligible running transaction after resume; Jira observations may still be ingested with
  zero time credit while paused.
- Consequence: a pause is a real mechanics/Jira-intent fence without losing operator intent or
  external truth, and concurrent absence causes never increase capacity or erase one another.

## Deferred Decisions

The following are deliberately not executable work in the Scrum MVP:

- HA leader election and multi-replica writers;
- multi-Jira tenancy and enterprise identity provider selection for a public plugin;
- exact cross-team dependency topology and propagation;
- learned calibration from historical Jira datasets;
- general downtime replay/catch-up;
- retention/deletion after the initial calibration period; and
- live expansion from five to 11–14 Jira projects, which requires a post-soak approval.

# Jira Team Simulator v2 — Product Requirements

> **DETAILED REFERENCE DRAFT.** The concise active requirements are in
> [`high-level-plan.md`](high-level-plan.md). Details here are suggestions unless they restate an
> explicit confirmed decision from that plan.

Status: **REFERENCE DRAFT — ACTIVE SUMMARY IN `high-level-plan.md`**
Version: **1.1**
Approved: **2026-08-10**

## 1. Purpose

The system creates and operates multiple realistic software-delivery teams whose activity is
projected into Jira. Its primary output is believable Jira history plus complete internal ground
truth for testing Jira plugins, risk analyzers, and analytical software.

The simulator must continue operating without daily user input. Codex is the principal control
surface; the web UI is primarily an observation, transcript, and emergency-control surface.

## 2. Release Boundary

### Scrum MVP

The first usable release is a complete vertical slice that can:

- create one Scrum team from one confirmed Codex request;
- provision a new company-managed Jira project and Scrum board for that team;
- generate members, responsibilities, a statistically configured backlog, and a first sprint;
- operate through at least two fixed sprint boundaries without daily user input;
- move Jira items through configured statuses at modeled times;
- produce the five required risk/event behaviors;
- retain daily transcripts and complete calibration ground truth internally;
- survive a process restart by resuming committed state without replaying missed work;
- expose global and per-team activity through a minimal dashboard; and
- run five teams concurrently before the initial live rollout is accepted.

### Kanban follow-on

Kanban uses the same team, flow, capacity, risk, Jira projection, Codex, activity, and ground-truth
components. It adds continuous replenishment, emerging work, pull/WIP policies, classes of service,
and internal business-hour SLA/SLE clocks. It is the next increment after Scrum MVP sign-off.

### Later releases

True cross-team issue dependencies, learned historical calibration, rich configuration UI,
high-availability/multi-replica execution, multiple Jira instances, and sophisticated downtime
catch-up require separate approved specifications.

## 3. Functional Requirements

### R-TEAM-001 — One team per confirmed request

The Codex skill must convert one natural-language request into a complete structured versioned
`TeamBlueprintDraft` conforming to `contracts/team-blueprint-draft.schema.json`. When the user omits
a choice, the skill fills it from the approved versioned starter catalog; the user need not answer
again. The server accepts no raw prompt on the preview endpoint. It applies only deterministic
contract defaults/normalization, semantic validation, and Jira collision discovery to produce a
previewed `TeamBlueprint`; it does not call the server-side OpenAI content service to interpret the
request. Creation uses preview → confirmation → asynchronous provisioning. Repeating the same
confirmed request with the same idempotency key must not create a second team or Jira project.

### R-TEAM-002 — Complete team description

A blueprint must contain:

- name, concise summary, detailed domain description, methodology, archetype, timezone, and locale;
- business calendar, holidays, working hours, and simulation seed;
- Jira project name/key, board name, and company-managed template;
- members with names, roles, daily capacity, WIP limit, availability, and responsibility profile;
- canonical statuses, issue-type routes, role eligibility, and timing baselines;
- backlog mix, size/priority distributions, target depth, and replenishment policy;
- Scrum cadence/capacity or Kanban WIP/class-of-service/SLA policy;
- risk profile and content/transcript policy.

Validation must reject an incomplete or internally inconsistent blueprint before Jira changes.
When a prompt omits Jira naming, normalize the team name to NFC. Use project name `SIM - ` plus its
first 74 Unicode scalar values and board name `SIM - ` plus its first 68 Unicode scalar values plus
` Board`; both therefore satisfy the 80-character schema limit without splitting UTF-8 bytes. Use
key `SIM` plus the first six upper-case ASCII alphanumeric team-name characters (`TEAM` when none
remain). On collision, append one base-36 character derived from the first byte of
`SHA-256(NFC(team name) + "|" + seed)` modulo 36; if occupied, probe the remaining characters in
base-36 order and fail with `PROJECT_KEY_SPACE_EXHAUSTED` after 36 candidates. The resolved names
and suffix are shown in preview; creation never attaches to an existing project implicitly.

The versioned starter catalog must contain at least one complete Scrum timing baseline, one complete
risk profile, canonical workflow/routes, recommended role mix, backlog distributions, business
calendar, and content policy. Its timing entries must resolve the full active route/status × issue
type × Fibonacci story-point grid. Catalog values and any imported v1 template source/version are
visible in the preview and persisted in ground truth; an implementation agent may not invent missing
coefficients or timing cells while provisioning a team.

Semantic validation must prove member availability intervals are ordered/non-overlapping, all
weights contain a positive total, calendar and capacity ranges are valid, every route references
known statuses/responsibilities, every ordinary route step has exactly one required activity (or
null for a zero-touch step), exceptional blocker statuses are excluded from ordinary routes, and
exactly one timing baseline resolves for every applicable route-status × issue-type × story-point
combination. Before the Kanban stage is accepted, Kanban
blueprints may be previewed but creation returns a stable `METHODOLOGY_NOT_ENABLED` error.

### R-TEAM-003 — Members and responsibilities affect mechanics

Members are virtual people with persistent identity and one or more responsibilities. A
responsibility profile states which activities or workflow steps the person may perform and a
bounded proficiency factor. Availability, daily capacity, and WIP limits must mechanically control
work progress. Work cannot be credited to an ineligible or unavailable person.

For the initial algorithm, labor capacity is consumed in actual available business hours. Effective
touch credit for one allocation is `labor_hours * proficiency_for_activity`; it is capped by the
visit's remaining touch demand, while the member ledger consumes the unmultiplied `labor_hours`.
Availability fraction bounds allocatable labor before proficiency is applied. Ground truth records
both labor consumed and effective touch credit. Proficiency does not accelerate the independent
status-dwell clock.

Confirmed schedule intervals are ordered and non-overlapping. Risk- and operator-created runtime
availability restrictions are independent, may overlap across sources, and can only reduce the
configured result: effective fraction and pre-fraction capacity cap are the minimum active values.
Natural absence durations persist remaining scheduled business time and decrement only during
newly processed running business intervals; pause/restart downtime consumes none.

Default workflow responsibilities include product ownership/acceptance, analysis, development,
code review, and quality assurance. The default role mix also includes a Scrum facilitator, whose
starter backup workflow responsibility is analysis; facilitation itself is a role, not a
capacity-consuming canonical activity. A person may cover more than one responsibility.

### R-WORK-001 — Rich work items

Every work item must retain type, Fibonacci story points (`1, 2, 3, 5, 8, 13`), priority, rank,
summary, description, acceptance criteria, persistent description-quality and latent-complexity
factors, current route/status, current worker, dependencies, risk state, Jira mapping, content
provenance, and simulation provenance. Kanban items additionally retain class of service and an
optional due instant; Scrum keeps both null.

Supported initial types are Story, Bug, Task, Spike, and Enabler. Epics may group items but do not
consume ordinary sprint capacity unless a later contract explicitly enables it.

An unknown Jira card manually added to a managed board/sprint uses the team's explicit import
defaults when Jira omits simulator metadata. The MVP default issue type is Task and default story
points is 3; both values and their default provenance are visible and configurable in the blueprint.

### R-WORK-002 — Shared statuses with type-specific routes

Teams use a shared canonical status vocabulary. Each issue type may select and order a valid subset
of those statuses and may override timing and eligible responsibilities. Default Scrum statuses are:

`To Do`, `Analysis`, `Development`, `Code Review`, `QA`, `PO Review`, `Blocked External`, `Done`, and
`Cancelled`.

`Blocked External` is a paused exceptional overlay, not an ordinary ordered route step: it suspends
the current visit and resumes that same sample/progress after resolution. `Cancelled` is terminal.
Jira status names may be mapped to canonical keys, but the mapping must be 1:1 and validated before
activation. The Jira workflow exposes every required forward and rejection-return edge, every
ordinary nonterminal status to Cancelled, ordinary status enter/return edges for Blocked External,
and Blocked External to each ordinary target plus Done and Cancelled. A terminal move from a block
closes both the blocking episode and suspended visit exactly once.

### R-TIME-001 — Dual time accounting

Each team has an IANA timezone, working weekdays, one daily work interval for MVP, and explicit
holiday dates. Defaults, when a prompt supplies none, are Monday–Friday, 09:00–17:00 local time,
the locale's configured holiday calendar (US federal for the initial deployment), and no partial
holiday work.

The system must retain both calendar elapsed time and business elapsed time. Touch/work progress and
Kanban SLA/SLE clocks advance only in business time. Queue/status analytics expose both clocks.
All persisted instants are UTC; local rendering and calendar arithmetic use the team's timezone and
must handle daylight-saving transitions.

### R-STAT-001 — Quantile-preserving dwell baseline

For every applicable `(baseline version, team/archetype, canonical status, issue type, story
points)` key, configure bounded duration anchors:

`minimum <= p25 <= p50 <= p99 <= maximum`.

The inverse CDF must pass exactly through the configured p25, p50, and p99 anchors. V2 must not use
the old averaged two-parameter log-normal fit. Zero-duration terminal statuses are permitted.

The baseline is sampled once when a status visit begins. Its dwell readiness clock advances in team
business time, not raw calendar time; calendar dwell remains an observed analytical duration.
Required touch time is separately sampled from a bounded work-demand configuration. An item may
leave a status only when its business-time dwell requirement and touch-work requirement are both
complete, unless an explicit terminal event cancels it.

### R-STAT-002 — Reproducibility and provenance

All stochastic decisions use deterministic, stable substream keys derived from a persisted root
seed and domain identifiers; Python's process-randomized `hash()` must not be used. Replaying the
same committed state and draw keys must produce identical results across restarts.

Semantic RNG identities use `SEMANTIC_ID_V1` from `architecture.md` and are persisted separately
from database/Jira IDs. A natural occurrence advances only with its committed eligible evaluation;
forced, disabled, duplicate, ineligible, and rolled-back decisions cannot perturb that sequence.

Each sample and probability decision records its baseline version, inputs, substream key, draw,
modifiers, result, and algorithm version.

### R-SCRUM-001 — Capacity-based planning

At a fixed sprint start boundary, plan from ranked carryover followed by ranked backlog. Sample a
capacity target from the team's configured story-point range, respect dependencies and member
availability, and commit a coherent scope. The plan, exclusions, sampled target, and seed must be
recorded as ground truth. The exact discrete sampler, availability ratio, mandatory carryover,
dependency-frontier, first-fit packing, priority/rank/UUID tie-breaks, and over-target behavior are
the versioned `SCRUM_PLANNER_V1` contract in `architecture.md`.

### R-SCRUM-002 — Fixed sprint lifecycle

Every Scrum sprint has immutable planned start and end instants in the team calendar. In the MVP,
`cadence_days` means local calendar days (default 14): each successor boundary is derived by adding
that number of local dates at the same local clock time, then converted to and persisted as UTC.
This preserves local boundary time across DST even when elapsed UTC hours differ. The simulator
may not close it early because work finished. Jira sprint create, fill, start, and complete
operations must occur in dependency-safe order and converge with the internal lifecycle. An
explicit human Jira lifecycle change may override the planned boundary; that override is ingested
as a manual intervention and never confused with normal autonomous completion.

An agent/settings update cannot reschedule an already created active sprint. Approved cadence or
calendar changes apply to the next not-yet-created sprint unless a later specification adds a
separate explicit boundary-override event.

At the end boundary, incomplete work moves to the next sprint, keeps its workflow status, worker
eligibility, sampled timing, accumulated progress, remaining work, dependencies, and risks. No
automatic carryover or context-loss penalty is applied. Carryover itself is recorded as an outcome.

### R-KANBAN-001 — Continuous flow

A Kanban team has no sprint dependency. Work arrives from configured reproducible arrival patterns
and agent-injected emerging items. Items are pulled in priority/class-of-service order only when the
next status and responsible member have available WIP capacity.

The initial executable policy is `KANBAN_BALANCED_V1` in `contracts/starter-catalog.md`, including
exact shifted-exponential/on-demand/batch semantics, class weights/priority, total pull tie-breaks,
status limits, and the rule that blocked work retains suspended-status WIP while releasing member
capacity. Stage 6 may activate but not invent or silently alter those defaults.

Natural/manual Kanban cards with no class use the blueprint's explicit default class. A Fixed Date
card without a supplied due instant receives `arrival_at + target_business_hours` using the team
calendar. Within Fixed Date, earlier due instant precedes item priority/rank/semantic UUID; all other
classes use item priority/rank/semantic UUID.

### R-KANBAN-002 — Internal business-hour SLA/SLE

Kanban policies define classes of service, a configurable clock start status, terminal stop statuses,
paused statuses, warning threshold, and target duration. SLA/SLE clocks advance only during team
business hours, are stored internally, and generate warning/breach activity and ground truth. V2
does not configure Jira Service Management SLA features.

### R-RISK-001 — Required event catalogue

The Scrum MVP must support these outcomes:

1. a status visit lasting longer than its configured expectation;
2. carryover at a sprint boundary;
3. a synthetic external dependency that pauses work and frees member capacity;
4. sudden cancellation into a terminal state; and
5. failed code review, QA, or PO review that returns work to a valid earlier route step and adds
   rework demand.

External dependency, cancellation, rejection/rework, and member unavailability are directly
injectable. Long stay and carryover remain derived outcomes: an agent can induce them through a
bounded dwell extension/dependency/availability/scope command, but cannot write the outcome flag
directly.
An aging warning is emitted once at p50; `LONG_STAY_DETECTED` is emitted once when business dwell
crosses p99 by default, with a versioned team policy allowed to select another configured quantile.

### R-RISK-002 — Transparent causal correlation

Risk occurrence must not be unexplained uniform randomness. The initial version uses a versioned,
bounded logistic probability model whose inputs include story size, description quality, latent
complexity, member availability, dependency state, and prior rework where relevant. Increasing a
configured adverse factor must not reduce the associated risk probability.

Duration effects are explicit bounded multipliers or paused clocks. Every decision records base
probability, factor values, coefficients, final probability, deterministic draw, outcome, and
mechanical effect. The LLM may narrate an event but may not choose whether it occurs.

### R-AUTO-001 — Autonomous persisted runtime

After activation, one scheduler owner advances each active team, creates daily rituals, maintains
backlog, manages lifecycle boundaries, produces state changes, and queues Jira projection without
daily input. A team has independently persisted running/paused state, simulation cursor, next wake,
seed state, and sync state.

Pause must stop autonomous simulated time/transitions and their new Jira intents for that team before
the command returns. Accepted human Jira interventions and explicit operator commands may still be
persisted with zero time credit while paused; already committed outbox work may drain unless the
separate emergency sync-freeze control is set.

If a configured outbox safety limit is reached, the team enters visible
`PROJECTION_BACKPRESSURED`: new autonomous ticks/intents are fenced until reconciliation drains the
queue below a low-water mark and an operator clears the condition. Intents are never discarded.

### R-AUTO-002 — MVP restart behavior

A restart resumes the last fully committed state automatically without a user start call. It does
not replay ordinary work ticks, content, or daily rituals for the outage interval and does not grant
work progress for downtime. Before advancing lifecycle or emitting new Jira intents, startup polls
Jira from the persisted high-water mark and drains applicable intervention observations so a manual
change made during downtime wins according to `R-JIRA-004`.

If that initial poll cannot complete for a `JIRA_READY` team, only that team remains visibly
`RECONCILIATION_PENDING` with ticks/outbox fenced until retry succeeds; other teams continue.

If a fixed lifecycle boundary is already past and Jira did not supply a newer boundary, the first
tick performs one idempotent boundary reconciliation; it never synthesizes multiple missed sprints.
It closes the previously active sprint once, skips materializing missed empty sprint windows, and
places carryover into one successor whose start is the latest cadence boundary at or before the
resume instant and whose end is the next boundary after it, derived from the original local-time
cadence anchor. The next wake is therefore in the future and cannot cascade through missed
boundaries. Richer continuity behavior is deferred.

Natural dependency and absence durations are simulation-duration timers: their persisted remaining
business hours/workdays freeze during downtime and resume only over newly processed intervals.
Explicit human absolute availability/Jira intervals are external truth: startup records them once
and applies only their state at resume with zero missed work credit. A durable future agent command
that became due during downtime or pause applies once in the first eligible running transaction
after startup reconciliation/resume, records its calendar lateness, and creates no backdated
mechanics. Sprint-boundary reconciliation is the only automatic calendar-time catch-up exception.

### R-JIRA-001 — One company-managed project per team

Each team owns one newly provisioned Jira company-managed project and one matching Scrum or Kanban
board. Provisioning must be asynchronous, observable, idempotent, and capability-checked before
mutation. A failed partial operation must be resumable without duplicate projects, boards, fields,
sprints, or issues.

The initial topology policy is `OFFICIAL_PROJECT_SCOPED_V1`. It uses only documented public Jira
Cloud APIs: create the project; ensure the dedicated standard issue types and associate their issue
type scheme only with that project; ensure the canonical statuses/workflow/transitions and associate
their workflow scheme with that project; then create the board/filter and read its configuration
back. The required board mapping is category based: `To Do` in the To Do column; Analysis,
Development, Code Review, QA, PO Review, and Blocked External in In Progress; Done and Cancelled in
Done. The public board API exposes configuration read-back but no supported column-configuration
write operation. Therefore a target-tenant Gate G0 spike must prove that a board created after the
workflow association maps every canonical status exactly once as required. If it does not, stop
before the engine build and obtain an approved supported topology mechanism; private endpoints and
browser/UI automation are not an allowed fallback.

### R-JIRA-002 — Jira is a convergent projection

The simulator database is authoritative for committed history and execution. Jira is both a
projection target and an allowed source of explicit human interventions under `R-JIRA-004`. A
transactional outbox projects committed state to Jira with explicit dependencies, stable
idempotency keys, pacing, retry/backoff, and read-back reconciliation. Outbox commands reference
local resource IDs and resolve Jira IDs only at dispatch. No unresolved external ID may be embedded
in a future command.

Internal state transitions are exactly-once. Jira delivery is at-least-once and must be made
effectively idempotent. A discrepancy is recorded and retried or surfaced; Jira must not silently
overwrite internal ground truth.

### R-JIRA-003 — Virtual identity only

The service account may create Jira issues, but simulation handoffs update only `sim_assignee` and
`sim_reporter` custom text fields. No simulator-originated write may change the actual Jira assignee
or reporter after issue creation. A direct human change to either real Jira field is preserved as a
human-owned Jira value and is never copied into virtual simulation identity or overwritten by the
simulator. Contract tests must inspect every Jira create/update payload.

No simulated daily transcript, risk narrative, or routine event comment is written to Jira in the
initial release. Existing `ADD_COMMENT` support may remain for v1 but is not used by v2.

### R-JIRA-004 — Survive and adopt manual Jira intervention

Projects managed by the simulator must remain operable when a person changes Jira directly. Jira
webhooks are the preferred low-latency signal and a periodic changelog/read-back poll is the recovery
path. Both feed one persistent, idempotent external-intervention inbox. Simulator-originated writes
must be echo-suppressed so they are not re-applied as human changes.

The initial supported intervention policy is:

- **Sprint started, completed, or restarted manually:** adopt the observed lifecycle once. Manual
  early completion closes the internal sprint at the observed instant and carries unfinished work.
  A valid manually started successor becomes the active sprint. If the same completed sprint is
  reactivated by Jira/plugin behavior, reopen it only when no successor work has started; otherwise
  create a visible lifecycle conflict. Jira states that cannot be reconciled to one active sprint
  pause autonomous lifecycle changes without crashing other work.
- **Known card added to a sprint:** adopt sprint membership, record scope addition, and recalculate
  forecast/capacity without changing the fixed planned end.
- **Unknown Jira card added:** import it as `origin=JIRA_MANUAL`, retain its Jira author, use mapped
  type/status/points, and apply explicit team defaults for missing simulator metadata.
- **Card removed from a sprint:** adopt backlog membership, stop simulated work on the card, release
  its worker capacity, and retain its status/progress. Re-adding it resumes the preserved status and
  remaining work without resampling the current visit.
- **Story points changed:** record re-estimation, retain completed work, and scale only remaining
  touch demand by `new_points / old_points`; resample future status visits from the new size. Missing
  or unsupported new values put only that item into a visible validation-conflict state. If the old
  value is missing or zero, preserve the current visit's completed/remaining work unchanged, use the
  new supported size only for future visits, and record `NO_RATIO_BASELINE` rather than dividing.
- **Status changed:** if Jira enters `Blocked External`, create an open-ended exceptional dependency
  episode that suspends the current ordinary visit/sample/progress and freezes its ordinary clocks;
  no blocker visit is sampled. Returning to the suspended status resolves the episode and resumes
  that visit. Moving from the blocker to another mapped status resolves the episode, closes the
  suspended visit as a manual transition, and samples only the selected target. Other mapped status
  moves close the prior visit and enter the observed status with a new deterministic visit sample.
  Skipped steps are recorded as manually skipped; backward moves create rework provenance. `Done`
  and `Cancelled` remain terminal and release worker capacity. A move out of a terminal status is
  rejected/quarantined until explicitly reconciled. An unmapped status quarantines only the item.
- **Priority, rank, summary, description, or acceptance criteria changed:** adopt the Jira value,
  record before/after values and actor, and use it on future planning/content decisions. Existing
  sampled quality/complexity mechanics do not change unless the intervention explicitly includes a
  supported recalibration command.
- **Card deleted or archived:** retain an internal tombstone and all ground truth, stop work, release
  capacity, and never silently recreate it. Explicit reconciliation is required to restore/project
  a replacement.
- **Project, board, workflow, status scheme, or virtual field changed/deleted:** freeze Jira sync for
  the affected team, retain internal simulation state, and expose a protected topology conflict.
  Never create a replacement or remap statuses automatically without confirmed reconciliation.

Protected integration fields (`sim_assignee`, `sim_reporter`, internal IDs, seeds, provenance, and
outbox correlation fields) remain simulator-owned. A manual edit to a protected field is recorded as
a conflict and restored only through an explicit reconciliation command.

Every accepted or rejected Jira-side change must record Jira changelog/webhook identity, actor when
available, observed time, ingestion time, before/after values, policy decision, resulting internal
state, and any new outbox intent. Processing the same Jira change twice must be a no-op.

### R-CONTENT-001 — Internal content generation

The server-side OpenAI API key is used only for autonomous internal content jobs: backlog prose,
acceptance criteria, sprint goals, event narration, and daily transcripts. Jobs use versioned
structured output, validation, bounded retries, configurable model/token limits, provenance, and a
deterministic template fallback. Content failure must never stop simulation mechanics.

MVP worker defaults are at most five content jobs claimed per worker cycle, a 45-second request
timeout, one retry, and 1,200 output tokens per job. These limits are configurable and recorded with
provenance; absence of a configured model/key selects fallback rather than blocking a tick.

Description-quality and latent-complexity scores are sampled by the deterministic domain model.
The generator receives those scores as instructions so prose matches the ground truth; it does not
infer or change mechanical scores.

When content generation is enabled for an already running v2 team, it may backfill only nonterminal
items whose relevant fields still have template provenance. It must not overwrite a field with human
Jira/agent provenance. A validated backfill commits the new content/provenance and typed Jira field
intent atomically.

### R-CONTENT-002 — Daily transcript documents

Every active team produces exactly one daily transcript when a committed running tick processes that
working business date's end boundary. It produces none for non-working dates and none retroactively
for a workday-end boundary skipped during process downtime under `R-AUTO-002`. It must summarize
actual participants, work, transitions, blockers, risks, and next actions from structured committed
events. The uniqueness key is
`(team_id, business_date, document_type, schema_version)`.

Transcripts are stored internally, retained with the simulation run, and accessible through the
dashboard and authenticated read API. They are not Jira comments.

### R-CODEX-001 — Codex control plane

The private first release consists of a Codex skill plus a thin authenticated MCP server. Codex
handles user conversation and produces the structured blueprint draft under the user's Codex
access; the MCP server invokes simulator validation/control/read APIs and does not expose or use the
server OpenAI key for user conversation or team-preview interpretation.

Required tools are defined in `contracts/mcp-tools.md`. Mutations require scopes, actor/correlation
metadata, idempotency keys, audit records, and confirmation according to the tool contract.

### R-CODEX-002 — Typed operator-control parity

Every supported v2 operator action must be available either as a dedicated MCP tool or as a
documented safe composition of tools. This includes provisioning, team settings, start/pause/resume,
sync freeze, work-item addition/update, member availability, risk-policy/event control, transcript/
ground-truth access, and Jira-conflict resolution. V2 must not expose a generic raw database, Jira
payload, or arbitrary mutation tool merely to achieve parity.

The complete Scrum operator surface must have HTTP/MCP parity by G5. Kanban-specific parity is an
additive G6 acceptance condition; it must not delay the first production-capable Scrum release.

### R-UI-001 — Observation-first dashboard

The default UI is a global chronological activity feed with team filtering. It must expose team/run
state, current sprint or Kanban state, transitions, long stays, carryover, dependencies,
cancellations, rework, availability, transcripts, Jira success/failure/retry, and links to ground
truth. A team-specific view uses the same source.

The MVP may poll; WebSockets and a complex visual team builder are not required. Emergency pause,
resume, and sync-freeze controls must clearly show their persisted result.

### R-GT-001 — Calibration ground truth

Authenticated APIs and exports must correlate Jira project/board/sprint/issue IDs with internal run,
team, item, status-visit, baseline, sample, queue/touch time, causal factor, risk, member, event,
content, command, and seed identifiers. Ground truth is append-only except for explicit correction
records and is retained indefinitely in MVP; no automatic source-ledger deletion job is enabled.
Derived authenticated download archives may expire after 24 hours and be removed, provided their
metadata/checksums remain and a new archive can be produced from the retained rows.

### R-SCALE-001 — Initial and target scale

The initial rollout supports five simultaneously active teams on one application/scheduler replica
and SQLite/WAL on the EBS volume. A disposable 11–14-team soak is required before production expands
beyond five. A PostgreSQL migration is triggered only by measured failure of the approved SQLite
gate; it is not part of the default MVP.

### R-SEC-001 — Private but authenticated

All control and ground-truth endpoints require authentication. The private MCP release uses a
dedicated secret per client with explicit read/control/provision scopes, stored outside the
repository, transmitted only over TLS, and auditable by client/actor. Anonymous mutation, public
E2E helpers, secrets in evidence, and arbitrary destructive Jira operations are forbidden.

The concrete private-auth contract is in `contracts/http-api.md`: opaque 256-bit bearer credentials
stored only by digest, explicit API/MCP/dashboard client kinds, offline issue/rotate/revoke, and a
24-hour rotation overlap. MCP receives its secret only through deployment environment. The
same-origin dashboard exchanges a dashboard-kind bearer for a Secure/HttpOnly/SameSite=Strict
bounded server session and uses strict Origin plus a session-bound CSRF token for mutations; it
never embeds or persists the MCP credential in browser code/storage.

## 4. System Invariants

These invariants are release blockers:

1. The database is authoritative for committed history and execution; allowed Jira human changes
   become authoritative only after idempotent ingestion as external interventions.
2. Every domain mutation, activity/ground-truth event, and Jira intent commits atomically.
3. One runtime writer owns a team at a time; one scheduler owner runs in the initial deployment.
4. No member exceeds capacity, availability, responsibility, or WIP limits.
5. No issue receives duplicate work credit for the same interval.
6. Sprint dates never change because simulated work finishes early; human Jira lifecycle overrides
   are explicit, attributed exceptions.
7. Carryover never changes remaining work unless a separately recorded event does so.
8. Paused or inactive teams produce no autonomous simulated transitions or their Jira intents.
   Explicit operator commands may be accepted and persisted but apply mechanics only in the first
   eligible running transaction after resume; accepted Jira interventions remain the auditable
   paused-team exception and receive zero time credit.
9. LLM output cannot decide mechanics or mutate authoritative state without validation.
10. Simulator-originated writes never change actual Jira assignee/reporter fields after creation;
    direct human changes are preserved and do not become virtual simulation handoffs.
11. V2 emits no Jira comments.
12. Every stochastic outcome is reproducible and explainable from retained ground truth.
13. Team-scoped reads, writes, events, and commands cannot cross team boundaries.
14. Restart does not create work, transcript, or ordinary event history for downtime.
15. No stage is complete without the evidence named in `verification-matrix.md` and Pavel's UAT.
16. Valid supported human Jira changes are adopted, not silently overwritten; invalid changes are
   isolated and visible rather than crashing a team or the global scheduler.

## 5. Explicit Non-Goals for the First Scrum Release

- Rich configuration UI or drag-and-drop workflow design.
- Jira Service Management SLA configuration.
- Real Jira user impersonation or handoff through actual assignee changes.
- Routine Jira comments or transcript publication to Jira.
- True cross-team blocker propagation.
- Historical-model learning or automated tuning from production Jira data.
- Multi-Jira, multi-tenant, HA, or multi-writer deployment.
- Replaying missed work during downtime.
- Deleting existing v1 data or rewriting Alembic migrations `001`–`012`.

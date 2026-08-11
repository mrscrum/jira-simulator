# Pragmatic v2 Live Simulator Design

Status: **APPROVED by Pavel on 2026-08-11**

This is the active implementation design for the next v2 work. It refines the product and
architecture direction in [`docs/v2/high-level-plan.md`](../../v2/high-level-plan.md) without
replacing it. It supersedes the low-level capacity-credit Tasks 7/8 in
[`backlog/v2/m1-capacity-credit.md`](../../../backlog/v2/m1-capacity-credit.md).

## Objective

Build the planned v2 simulator as an internal test-data generator that produces plausible,
explainable Jira activity. Optimize engineering effort for simulation usefulness and realistic
behavior. Do not apply financial-system, defense-system, or high-availability engineering standards
to ordinary simulator decisions.

The required reliability boundary is deliberately narrow:

- a committed team tick is internally consistent;
- its Jira intents are durable before any Jira call;
- a failed transaction changes nothing;
- after a process crash or server reboot, the simulator reloads committed state and continues; and
- downtime does not manufacture missed daily work.

High availability, multi-writer execution, lossless reconstruction of uncommitted computation, and
proof-grade replay are not requirements.

## Decisions

### V2 remains authoritative

The v2 blueprint, runtime, Scrum state, activity, ground-truth, and projection-intent records are the
source of truth for v2 teams. The live path must not mirror authoritative state into the v1 team,
sprint, issue, or scheduled-event tables.

Accepted Tasks 1–6 are frozen as working infrastructure. New work may call their public interfaces
and make a narrowly tested integration fix when a real live-loop requirement exposes a defect. It
must not redesign them, expand their hardening model, or require their internal precision and
provenance machinery to spread into ordinary engine code.

### Team count is configuration

There is one functional path for every active team. The scheduler obtains due team identifiers and
applies the same independent operation to each one. Zero, one, five, or more configured teams do not
select different domain logic or architecture.

Five heterogeneous teams are a planned UAT/load fixture. They are not a minimum, maximum, hard
parameter, functional acceptance branch, or reason to introduce coordination or concurrency.
Sequential processing is sufficient until measured scheduler duration or Jira throughput shows a
real need for bounded parallelism.

### Use a pragmatic statistical kernel

The simulator retains the distinctions that make the generated Jira history useful:

- status dwell/waiting is separate from active touch work;
- responsibility, availability, daily capacity, proficiency, and WIP mechanically constrain work;
- an assigned member normally retains an item until release, blockage, or completion;
- status durations and outcomes are sampled from versioned team configuration;
- work follows configured, type-specific routes and may reject or rework;
- Scrum uses fixed boundaries and carries unfinished work forward without resetting progress or
  applying a penalty; and
- language models may write realistic content but never decide mechanical outcomes.

Use persisted seeded randomness for reproducible logical decisions. The accepted Task 3 generator
may remain behind a small draw interface, but new mechanics do not add HMAC proof, canonical hashes,
or adversarial reconstruction defenses for each decision.

Existing integer-microsecond fields remain a storage representation. New behavior uses ordinary
UTC `datetime`, `timedelta`, and duration arithmetic, converting only at established persistence
boundaries. Exact half-even conversions or sub-microsecond boundary algorithms require a separate
user-visible need before they are added.

## Selective reuse

### Accepted v2 Tasks 1–6

| Existing capability | Use in the live path |
|---|---|
| Resolved team blueprint and persisted runtime | Configuration authority and restart cursor |
| Activity, ground-truth, and projection drafts | Explain behavior and create durable external intent |
| Seeded decision/sampling primitives | Source logical random draws through a narrow adapter |
| Business calendar | Determine working intervals and fixed local-time boundaries |
| Persisted Scrum snapshot and mapper | Authoritative member, work, sprint, scope, and visit state |
| Authoritative unit of work | Atomically commit runtime, state, evidence, and projection intents |

These components are usable infrastructure, not a mandate to reproduce every internal validation
pattern in the live engine.

### V1

Reuse only sound leaves and proven behavior:

- calibrated statistical distributions and configuration ideas;
- workflow, capacity, planning, and carryover behavior where it matches the v2 product decisions;
- APScheduler hosting and application lifecycle patterns;
- Jira HTTP transport, rate-limit handling, retry behavior, and queue pacing concepts;
- FastAPI, SQLAlchemy, migration, deployment, and React foundations; and
- focused test fixtures that describe useful simulator behavior.

Do not reuse the v1 authoritative tables, whole-sprint precomputation, in-memory simulation clock,
scheduled-event completion model, or automatic carryover penalty. V1 source can be adapted or its
small algorithms copied into focused v2 modules when that is clearer than coupling the two runtimes.

## Live architecture

```text
persisted scheduler
  -> find due active v2 teams
  -> for each team, independently
       -> load blueprint + runtime + complete Scrum state
       -> calculate one bounded incremental tick
       -> commit state + activity + ground truth + Jira intents atomically
  -> Jira worker drains committed intents asynchronously
```

### Coherent load and bootstrap

A reader returns one detached, complete view containing the resolved blueprint, runtime version and
cursor, members and availability, active sprint and scope, backlog items, open status visits, and
the samples needed to continue them. It never assembles a team from observations taken in different
transactions.

Creating or first starting a team bootstraps the minimum persisted Scrum state: member execution
state, a ranked backlog, a fixed-boundary sprint, selected scope, initial visits, their timing
samples, and the next scheduler wake. Repeating bootstrap after a partial failure is safe and does
not duplicate state.

### Incremental team tick

One application service advances one team from its committed cursor toward a bounded scheduler
wake. Its pure mechanics:

1. determine the usable business-time interval;
2. resolve member availability, current ownership, WIP, and remaining daily capacity;
3. assign eligible work and credit touch progress while accumulating plausible waiting/dwell;
4. complete eligible visits and open the next configured route step;
5. evaluate only the risk or lifecycle decisions due in that interval; and
6. return after-images plus human-readable activity, causal ground truth, and Jira projection
   intents.

The tick may stop at a meaningful visible boundary such as sprint end or workday close. It does not
need to split at every theoretical microsecond. A subsequent transaction continues from that
committed boundary.

For a single-writer scheduler, an optimistic runtime-version conflict is handled with one reload and
retry. Repeated failure is recorded against that team and does not stop unrelated teams.

### Sprint lifecycle

At each fixed sprint end, close the sprint once, retain every unfinished item's status, owner,
sample, and accumulated progress, and place that item into the next sprint ahead of newly selected
backlog work. There is no carryover multiplier or reset. Jira sprint-complete, create, scope, and
start intents are ordered through outbox dependencies rather than issued inside the tick.

### Atomic persistence and Jira delivery

The existing v2 authoritative unit of work is the transaction boundary. One successful commit
contains the runtime cursor/version change, Scrum after-images, activity, ground truth, and pending
projection intents. Network calls never occur in that transaction.

A small v2 delivery adapter reads committed pending intents, maps v2 semantic resources to Jira
resources, and invokes the reusable Jira transport. Delivery is idempotent, respects rate limits,
and leaves failed work retryable. Jira availability affects projection lag, not committed simulation
state. Inbound Jira reconciliation remains a separate path and runs before new progress after
startup, as required by the high-level plan.

### Restart behavior

Startup reloads persisted runtime and Scrum state rather than reconstructing them from Jira or an
in-memory schedule. It reconciles supported Jira observations first, records the wall-clock gap as
downtime, and resumes from the current scheduling point without crediting missed work. Pending
projection intents remain available to the Jira worker. The next successful tick uses only the last
committed state and cursor.

## Ground truth and realism

Ground truth should answer practical calibration questions: which configuration and draw affected
an outcome, who could work, why an item waited, what progress changed, why a transition or risk
occurred, and which Jira intent represents it. It does not need to serve as a cryptographic proof of
every in-memory operation.

The initial live slice must support ordinary forward progress before adding realism behaviors.
Then add long stays, review/QA/PO rejection and rework, cancellation, external dependency, member
unavailability, and causal risk decisions. Generated summaries, descriptions, acceptance criteria,
and transcripts are asynchronous enhancements; deterministic fallback content keeps mechanics
running when OpenAI is unavailable.

## Explicit cuts

Do not add the following without a new demonstrated requirement:

- hostile Python subclass, pickle, equality-spoof, or reconstruction hardening;
- a new HMAC/canonical-hash proof for each simulator decision or payload;
- exact half-even or microsecond boundary machinery beyond existing persistence adapters;
- semantic counters, receipts, or after-image protocols used only for theoretical replay;
- arbitrary scheduler partition invariance or fractional-credit residue protocols;
- exhaustive per-table fault-injection matrices;
- exact internal error-string, import-order, or full-payload golden contracts;
- a separate single-team, five-team, or multi-team execution architecture;
- parallel team execution before measurement demonstrates a need;
- replay of work missed during downtime;
- multi-writer, high-availability, or distributed-service infrastructure; or
- production Jira, deployment, or UAT actions without separate authorization.

The uncommitted Task 7 tests and evidence remain preserved while the approved design is adopted.
They are not acceptance requirements. Simple capacity, WIP, ownership, waiting, progress, and
completion examples may be rewritten later as focused behavioral tests. Exact arithmetic,
adversarial-object, exhaustive provenance, and invalid historical-green evidence are abandoned.

## Proportional verification standard

Every production behavior still follows RED -> GREEN -> REFACTOR. Tests should protect observable
simulation behavior, restart/data-loss boundaries, and Jira convergence rather than internal proof
machinery.

The core verification set covers:

- bootstrap and a complete authoritative reload after process restart;
- reproducible logical choices from the same committed seed and state;
- responsibility, availability, WIP, capacity, waiting/dwell, and touch progression;
- workflow completion and representative rejection/rework;
- a fixed sprint boundary with unchanged carryover;
- one successful atomic tick and one injected whole-transaction rollback;
- durable retryable Jira intent when delivery fails after commit;
- scheduler discovery of all active teams, independent failure isolation, and identical behavior
  regardless of configured team count; and
- a fake-Jira vertical run across multiple ticks, two sprint boundaries, restart, and provider
  outage recovery.

Use one team for ordinary functional tests and two differently configured teams for isolation. A
five-team run is a UAT/load exercise only. Broader team-count performance testing is measurement,
not a functional correctness matrix.

## Implementation slices

Each slice must leave a usable, reviewed capability and update the required project documents.

1. **Coherent state and bootstrap** — add the application reader and idempotent initial Scrum-state
   creation, then prove restart reload.
2. **Incremental Scrum tick** — add pragmatic capacity/WIP allocation, dwell/touch progress,
   ownership, route transitions, and one atomic state/evidence/intent commit.
3. **Sprint lifecycle and scheduler** — add fixed-boundary completion, unchanged carryover,
   persisted wake/cursor handling, active-team discovery, per-team isolation, and restart behavior.
4. **Jira delivery** — adapt committed v2 intents to the existing Jira transport with resource
   mapping, dependency order, idempotency, pacing, and retry.
5. **Vertical proof and realism** — run the fake-Jira multi-sprint scenario, then add the required
   causal risks, asynchronous content, and transcripts in focused increments.

Kanban, dashboard expansion, manual Jira intervention breadth, live Jira UAT, and measured scaling
remain ordered by the high-level roadmap; they are not pulled into the first live-loop slice.

## Done condition for the first live Scrum loop

The first loop is complete when a configured v2 Scrum team can bootstrap, advance plausible work
over repeated scheduler wakes, cross a fixed sprint boundary with unchanged carryover, commit every
tick atomically with activity/ground truth/Jira intent, survive a process restart without replaying
downtime, and recover projection after a fake Jira outage. No v1 precomputed schedule participates.

This proves the functional architecture. Running five heterogeneous teams remains a later configured
UAT/load scenario, not another implementation path.

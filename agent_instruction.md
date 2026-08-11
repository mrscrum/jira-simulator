# Agent Instruction — Jira Team Simulator

## Current Stage and Baseline

Stage labels in `backlog/` are not a reliable description of the code. The repository contains
configuration UI, Jira integration, a distribution-based simulation rewrite, precomputed sprint
schedules, and scheduled-event dispatch. The north-star end-to-end workflow is still partial and
has not been verified against the live `mrscrum` Jira instance in the latest assessment.

Read `docs/requirements-functionality-map.md` before planning implementation. It is the
evidence-backed baseline as of 2026-08-10 (`main` at `b65b133`).

The approved additive v2 specification and execution plan now begin at `docs/v2/README.md`. M1 is
tracked under `backlog/v2/`; the completed persistence/deterministic-kernel slices are recorded in
`backlog/v2/`, and `backlog/v2/m1-scrum-state.md` is the active reviewable two-task implementation
plan. Historical Stage 4/5 plans are not executable for v2.

## Product Boundary

- Connect exactly one Jira instance: `mrscrum`.
- Use one global Jira credential set and Jira client.
- Support multiple teams; each team maps to a distinct Jira project and is configured separately.
- Keep all Jira writes behind the persistent write queue.
- Never use a simulator-originated update to change Jira's actual assignee or reporter after issue
  creation. Preserve direct human changes; use virtual ownership fields and internal state.
- Simulation timing is statistical and Jira statuses map 1:1 to configured workflow statuses.

## What Is Implemented

- FastAPI backend with 76 OpenAPI operations and 43 SQLAlchemy tables.
- React UI for teams, members, workflows, timing templates, move-left configuration,
  dependencies, simulation controls, and sprint/event schedules.
- Per-team project key/board, members, workflow, timing, sprint, calendar, and backlog settings.
- Log-normal full-time and uniform work-time distributions.
- Sprint planning, move-left rolls, working-calendar calculations, and deterministic precompute.
- Persistent scheduled events, Jira write queue, rate-limit handling, Jira client, bootstrapper,
  health monitor, and queue-status auditor.
- Pure v2 deterministic semantic identities, `HMAC_SHA256_U53_V1` decision draws, and bounded
  dwell/touch sampling with slotted, reconstruction-resistant, formula-bound provenance and no
  persistence/external dependency.
- Pure v2 aware-UTC/business-time arithmetic, DST-safe IANA local-boundary resolution, fixed local
  sprint cadence, and bounded `US_FEDERAL_V1` holiday-horizon materialization/extension.
- Immutable detached authoritative Scrum state across member execution, work/factors,
  sprints/scope, status visits/samples, semantic counters, and natural evaluations at reversible
  Alembic revision 015, with a caller-owned-session mapper and composite ownership constraints.
- Terraform, Docker Compose, Nginx, and GitHub Actions deployment assets.

## Most Recent Change

On 2026-08-11, Task 5 review fix round 3 made both caller-session mapper entry points reject
non-empty ORM `new`, `dirty`, or `deleted` state before authority/candidate SQL, preserving rollback
ownership and preventing implicit flushes or identity-map leakage into detached snapshots. Empty,
coordinate-free write sets now reject before SQL instead of returning a false complete snapshot;
Task 6 must skip the mapper when it has no Task 5 after-images. Trusted sample creation now exactly
revalidates every nested deterministic draw scalar and the full keyed HMAC, and retained dwell/touch
units require exact finite built-in floats in `[0, 1]`. Low-bit HMAC equality forgeries,
low-level reconstructed inputs, and stateful float subclasses reject before persistence. Revision
015 remains unchanged; no generalized Task 6 upsert, revision 016, external call, deployment, UAT,
or M1 completion was added.

On 2026-08-11, Task 5 review fix round 2 made the caller-owned mapper accept sparse touched-row
after-images without weakening complete restart state. It resolves omitted persisted member/work
owners and unchanged visit samples under `no_autoflush`, validates a complete merged snapshot
before Task 5 DML, and returns that complete detached aggregate. Approved null-activity route steps
persist and restart as exact `activity_key=None`, no-member, zero-touch visits with one authenticated
sample. Every complete snapshot and new visit requires exactly one authenticated sample, and only
existing visit rows receive the narrow reviewed after-image update.

On 2026-08-11, Task 5 review fix round 1 bound authoritative Scrum state to its complete trusted
authority. Task 5 values now reject runtime and scalar subclasses; status samples can be created
only from exact authenticated Task 3 draws and are revalidated after restart against the persisted
blueprint seed, team/run/visit coordinate, timing cell, sampler versions, formulas, and exact
half-even microseconds. Revision 015 now gives visit/natural counters and natural evaluations typed
work-item/member owner columns with composite foreign keys and exact owner-shape checks. The mapper
loads the exact team/blueprint/run in the caller session, validates blueprint graph/reference and
partial/semantic uniqueness before DML, and rejects persisted sample corruption on load. Task 6,
revision 016, lifecycle/allocation behavior, external calls, deployment, UAT, and M1 completion
remain open or untouched.

On 2026-08-11, M1 Scrum-state Task 5 added immutable, slotted authoritative state values and the
third isolated v2 mapping module. Revision 015 creates 11 constrained tables for semantic member
identity, runtime availability/consumption, work/factors, sprints/scope, status visits/samples,
counters, and natural-decision eligibility; it adds no transition or allocation behavior. Every
run-derived reference is composite team/run owned, duration state is exact signed-range integer
microseconds, and timing provenance is canonical and bound to its visit/sample coordinates. The
caller-owned mapper validates before inserts, flushes without transaction ownership, returns
detached semantic ordering, and reloads exactly after engine disposal. Populated revision 014
survives 014→015→014→015 unchanged. Task 6 remains open; Jira/OpenAI, deployment, UAT, and M1
completion were not touched.

On 2026-08-11, Task 4 review fix round 2 centralized business-calendar timezone conversion and
local-boundary range handling. `business_date`, `working_interval`, nested next-working/addition,
fixed cadence, and aware-UTC normalization now expose one stable domain `ValueError` when an
otherwise valid extreme instant cannot be represented after conversion; raw `OverflowError` no
longer crosses the public pure-domain boundary. Minimum/maximum tests cover Kiritimati and Los
Angeles without changing ordinary DST, horizon, federal, cadence, schema, persistence, external,
deployment, UAT, or M1 state.

On 2026-08-11, Task 4 review fix round 1 hardened the pure calendar/horizon boundary. Federal
starter materialization now requires the resolved team IANA timezone, so UTC-normalized blueprint
instants still select the correct team-local year and equivalent offset representations agree.
Only keys exposed by `zoneinfo.available_timezones()` are accepted after pseudo-zone exclusion.
Extension authenticates full-year bounds and the exact generated `US_FEDERAL_V1` holiday tuple,
then catches far-stale requests up in ten-year blocks; replay preserves identity. Business-calendar
`Etc/UTC` horizon exhaustion, including `date.max`, raises a stable domain `ValueError`; review fix
round 2 added the cross-zone extreme-conversion boundary. Round 1 added no schema, persistence,
scheduler, engine, external call, deployment, UAT, or M1 completion.

On 2026-08-11, deterministic-kernel Task 4 added the pure dual-clock calendar boundary.
`BusinessCalendar` is constructed only from a resolved `CalendarBlueprint` and explicit IANA zone;
it provides exact UTC/calendar and business elapsed time, business-duration addition, working
interval/date/end queries, and next-working resolution. Local boundaries reject nonexistent or
ambiguous DST wall times by UTC round trip. Fixed cadence preserves the anchor's local clock across
DST and never shifts for weekends or holidays. `US_FEDERAL_V1` materialization contains the exact
observed federal rules, excludes Inauguration Day, and extends its immutable horizon by ten years
only when fewer than two complete local years remain. This task added no schema, persistence,
scheduler, engine, external call, deployment, UAT, or M1 completion.

On 2026-08-11, Task 3 review fix round 2 moved all six deterministic decision/sampling value
dataclasses onto one frozen/slotted policy. They expose no instance `__dict__`, shallow/deep copy
returns the same immutable value, and pickle/reduce plus injected pickle state reject. Tests cover
ordinary field and mapping mutation of stream seeds, decisions, digests, unit values, duration
parameters, and samples. This is an ordinary Python immutability guarantee and deliberately does
not claim defense against explicit low-level `object.__setattr__`. Algorithms, public provenance
fields, persistence, migrations, external boundaries, and Task 4 are unchanged.

On 2026-08-11, Task 3 review fix round 1 sealed `UniformDraw` construction behind
`DeterministicRandomStream.draw`, restricted every current decision entity to a semantic UUID,
enforced the documented zero/nonzero occurrence scopes, and bounded every semantic
ordinal/index/sequence plus occurrence/draw index to `0..2^53-1`. `DurationSample` construction and
replacement now re-evaluate the exact retained dwell/touch formula. Corrected cancellation and
maximum-safe-integer literals were independently re-encoded with Node.js. This added no state,
allocator, migration, external dependency, Jira/OpenAI call, deployment, UAT, or M1 completion.

On 2026-08-10, M1 deterministic-kernel Task 3 added the pure decision and timing-sampling boundary.
`backend/app/v2/domain/deterministic_rng.py` owns the exact closed creation/decision enums, eight
fixed-namespace semantic UUIDv5 paths, NFC-seeded HMAC-SHA-256 canonical messages, high-53-bit
conversion, and frozen draw provenance. `backend/app/v2/domain/sampling.py` owns exact-anchor
log1p-space dwell interpolation and bounded linear touch sampling from explicit unit draws. Literal
vectors, fresh-process/reversed/interleaved replay, every starter timing cell, invalid booleans and
finite/order boundaries, and AST isolation are covered. No occurrence allocation, persistence,
migration, clock, scheduler, engine, Jira/OpenAI call, deployment, UAT, or M1 completion was added.

On 2026-08-10, the reviewed two-task persistence spine was closed without completing M1, and the
next active plan was defined as two pure-domain deterministic-kernel slices: exact HMAC-U53 plus
bounded dwell/touch sampling, followed by dual-clock/DST-safe calendar primitives. This was a
planning-only change; it added no migration, production behavior, Jira access, or M1 sign-off.

On 2026-08-10, M1 Task 2 review fix round 2 made the live-slice JSON boundary strict about object
keys. `DraftEnvelope` and all three draft factories now reject integer, boolean, `None`, mixed, and
nested non-string mapping keys before canonical encoding or session creation, preventing silent
`json.dumps` coercion. Valid strict JSON retains the same canonical bytes/hash and deep immutability.

On 2026-08-10, M1 Task 2 review fix round 1 hardened revision-014 contracts without changing its
schema. Direct construction, `dataclasses.replace`, and the UOW boundary now revalidate semantic
UUIDs, canonical JSON/digests, non-empty type fields, non-negative versions, pending status, and
aware instants before opening a session. Semantic-key insert races recover through a savepoint:
identical content resolves to the winner, while differing content raises the typed conflict and
rolls back the runtime plus all ledgers. Deep payload aliases reject `|=` and nested mutation. Every
fresh public v2 model/UOW import order registers all seven v2 tables and can create the SQLite
schema. Adapter-failure coverage now reloads ground truth explicitly as well as runtime, activity,
and projection state.

M1 Task 2 originally added revision 014 above the reviewed revision-013 team shell. Runtime rows
expose an explicit optimistic version, and `backend/app/v2/persistence/unit_of_work.py` uses one
compare-and-swap plus one database transaction to advance runtime and append ordered activity,
immutable ground truth, and generic pending projection intent. Deterministic semantic UUIDs,
canonical payload hashes, stable append cursors, stale-writer rollback, disposed-engine restart,
and post-commit adapter failure are covered by focused tests.
`backend/alembic/versions/014_add_v2_live_slice_ledgers.py` backfills version zero without retaining
a server default, owns all three new tables, and returns exactly to populated revision 013 on
downgrade. V2 remains isolated from the legacy runtime and invokes no Jira/OpenAI adapter.

On 2026-08-10, Pavel approved the v2 product direction and then asked to keep the plan high level,
leaving implementation detail to the capable model that builds it. The active requirements,
architecture, roadmap, and MVP outcome now live in `docs/v2/high-level-plan.md`; milestone status is
in `backlog/v2/README.md`. Earlier detailed v2 contracts and the 96-task decomposition are retained
only as optional design exploration. Pavel additionally required managed projects to survive direct
Jira sprint/card intervention, which remains an explicit active requirement. No source-code fixes or
runtime changes were made.

Current local evidence after Task 5 review fix round 3:

- Backend: 1367 passed, 43 skipped, 15 baseline warnings.
- V2: 849 passed, 1 baseline warning.
- Task 5 focused: 311 passed.
- Task 4 focused: 146 passed.
- Task 3 focused: 251 passed.
- Task 1 focused: 56 passed, 1 baseline warning.
- Task 2 focused: 186 passed.
- Ruff: passed.
- Alembic: sole revision 015 head, no branches; populated round trip and ORM parity passed.
- Real Jira integration tests were not run and remain skipped in normal CI.

## Key Files

- `AGENTS.md` — mandatory development flow and highest-priority repository rules.
- `docs/requirements-functionality-map.md` — current requirements/functionality baseline.
- `docs/v2/high-level-plan.md` — active v2 requirements, architecture, roadmap, and MVP acceptance.
- `docs/v2/implementation-prompt.md` — ready-to-paste mandate for a long independent implementation
  run, including autonomy, safety, priorities, verification, and morning handoff.
- `docs/v2/README.md` — authority and resumption instructions.
- `backlog/v2/README.md` — active milestone status.
- `backlog/v2/m1-deterministic-kernel.md` — completed Tasks 3/4 requirements, TDD commands,
  evidence, and completion gates.
- `backlog/v2/m1-scrum-state.md` — active Tasks 5/6 requirements: revision-015 authoritative Scrum
  state followed by atomic runtime-CAS/UOW integration.
- Other files under `docs/v2/` and `backlog/v2/stage-*.md` — optional detailed planning reference,
  not the active contract or mandatory task sequence.
- `docs/simulation-engine-rewrite-requirements.md` — superseded v1 requirements; historical only.
- `backend/app/main.py` — application/service/scheduler wiring.
- `backend/app/engine/simulation.py` — lifecycle tick and sprint precompute persistence.
- `backend/app/engine/precompute.py` — in-memory sprint simulation and event generation.
- `backend/app/engine/workflow_engine.py` — per-item distribution/capacity/status logic.
- `backend/app/engine/event_dispatcher.py` — moves due scheduled events to the Jira queue.
- `backend/app/integrations/jira_write_queue.py` — external-write boundary and operation routing.
- `backend/app/integrations/jira_client.py` — Jira REST/Agile API client.
- `backend/app/integrations/scheduler.py` — background jobs and paused startup behavior.
- `backend/app/api/routers/scheduled_events.py` — sprint/schedule management and diagnostics.
- `backend/app/v2/domain/live_slice.py` — immutable live-slice drafts, stored records, runtime
  advance, transaction command/result, and page contracts.
- `backend/app/v2/domain/deterministic_rng.py` — closed semantic ID/decision enums, exact UUIDv5
  paths, scoped safe-integer coordinates, and sealed stateless HMAC-U53 draws.
- `backend/app/v2/domain/immutable_value.py` — shared frozen/slotted Task 3/5 copy, reconstruction,
  and runtime-subclass policy; it covers ordinary mutation paths, not explicit
  `object.__setattr__` misuse.
- `backend/app/v2/domain/sampling.py` — validated dwell/touch parameters and pure explicit-draw
  bounded duration samples whose retained result is formula-validated.
- `backend/app/v2/domain/business_calendar.py` — resolved immutable business calendar, strict
  aware-UTC inputs, dual elapsed/addition queries, and fixed unadjusted local cadence.
- `backend/app/v2/domain/iana_timezone.py` — shared available-IANA-key boundary that excludes
  loadable pseudo-zones before resolving a pure domain timezone.
- `backend/app/v2/domain/us_federal_calendar.py` — exact observed `US_FEDERAL_V1` rules plus pure
  team-zone-derived starter materialization, canonical-horizon authentication, and idempotent
  ten-year-block catch-up.
- `backend/app/v2/domain/scrum_state.py` — sealed Task 5 lifecycle/state, trusted blueprint-bound
  timing samples, exact clocks/provenance, simulator rank, semantic counter, evaluation, write-set,
  query, and detached snapshot contracts.
- `backend/app/v2/persistence/scrum_state_models.py` — the 11 revision-015 Task 5 mappings and their
  exact composite ownership, check, unique, and partial-index constraints.
- `backend/app/v2/persistence/scrum_state_mapper.py` — caller-owned-session add/load mapping; it
  resolves sparse omitted owners, validates a complete merged snapshot before DML, narrowly updates
  existing visits, and flushes but never opens, commits, or rolls back a transaction.
- `backend/alembic/versions/015_add_v2_authoritative_scrum_state.py` — reversible Task 5 schema above
  populated revision 014.
- `backend/tests/v2/fixtures/hmac_sha256_u53_v1_vectors.json` — independently fixed canonical
  message/digest/U53/unit literals, including Unicode NFC equivalence.
- `evidence/v2/M1-T03/README.md` — Task 3 TDD, replay, sampler, architecture, and regression proof.
- `evidence/v2/M1-T04/README.md` — Task 4 TDD, DST/cadence/holiday, regression, and isolation proof.
- `backend/app/v2/persistence/unit_of_work.py` — the v2 persistence port and atomic SQLAlchemy
  compare-and-swap implementation; it must not import or call an external adapter.
- `backend/app/v2/persistence/live_models.py` — the three append-oriented ledger mappings.
- `backend/alembic/versions/014_add_v2_live_slice_ledgers.py` — reversible runtime-version and
  live-ledger migration above revision 013.
- `frontend/src/App.tsx` — top-level UI section routing.
- `docker-compose.yml` — current PostgreSQL deployment, conflicting with SQLite-on-EBS rules.

## Next Task

After the pending exact Task 5 review-fix round 3 commit, execute Task 6 from
`backlog/v2/m1-scrum-state.md` through a new strict RED -> GREEN -> REFACTOR cycle. Task 6 must keep
revision 015 unchanged while atomically combining runtime CAS, sparse Task 5 after-images, semantic
counter/eligible occurrence claims, and the existing ledgers. Do not add revision 016,
allocator/live-flow/lifecycle/planning, dependencies, risks, scheduler/engine wiring, Jira/OpenAI
calls, deployment, UAT, or M1 completion.

## Active Decisions and External Gates

1. Build an additive persisted-live v2 modular monolith, initially using SQLite/WAL on EBS and one
   scheduler owner.
2. Deliver Scrum and Codex first, accept five teams, then add Kanban and validate 11–14-team load.
3. Use fixed sprint boundaries, unchanged carryover, team business-time mechanics, and both
   business/calendar analytics.
4. Use one company-managed project/board per team, virtual identity fields, internal transcripts,
   and no v2 Jira comments.
5. Treat supported manual Jira sprint/card edits as attributed inputs and reconcile Jira before
   advancing after restart; incompatible/protected changes surface a scoped conflict.
6. Keep Codex conversation/control separate from server-key OpenAI content generation and expose
   complete calibration ground truth.
7. Live Jira work requires a designated disposable target and authorization. Code work requires the
   mandatory TDD skill from `AGENTS.md`.

## Critical Gotchas

- Precomputed final issue states are not applied to persistent `Issue` rows.
- A newly generated schedule usually lacks the Jira sprint ID needed for add/start/complete events.
- Event dispatch ignores sprint activation and per-team pause/deactivation.
- Per-team start/resume does not start the global scheduler.
- SimClock speed and tick-interval API changes do not accelerate/reconfigure scheduled dispatch.
- Health recovery can remain stuck in `RECOVERING` because queue recovery is not wired.
- Jira-synchronized sprint edit/delete paths use `app.state.jira_write_queue`, but startup stores
  `app.state.write_queue`.
- Dysfunction and cross-team dependency models do not affect the active simulation.
- Historical documentation claims event-handler modules that no longer exist.
- The API is unauthenticated, and the public deployment has no configured TLS listener.
- V1 has no durable webhook/poll inbox for Jira-side manual sprint/card changes; v2 must not build
  reconciliation on the current one-way dispatcher alone.
- Restart must reconcile supported Jira interventions before boundary handling or new outbound
  delivery, and must not manufacture missed daily work.
- Jira provisioning and sprint creation need explicit idempotency/read-back tests before relying on
  them in autonomous operation.
- Never place simulator/Jira/OpenAI credentials in source, browser bundles, URLs, logs, or evidence.
- V2 projection delivery must consume only committed/read `PENDING` intents after the unit of work;
  never import or invoke an adapter inside `commit_tick_slice`.
- Treat `append_sequence` as the only pagination order. `occurred_at` may be equal or late, and
  semantic replay must not allocate another row when canonical immutable content is identical.
- Existing dirty documentation and untracked assessment/skill files belong to the current owner;
  do not stash, reset, clean, or overwrite them during worktree setup.
- `DraftEnvelope` cyclic Python containers currently fail before session/state mutation with a raw
  `RecursionError`; this deferred non-blocking validation Minor is outside deterministic Tasks 3/4
  and should be fixed separately before an API accepts arbitrary v2 payload objects.
- Task 3 validates caller-supplied occurrences only. It deliberately has no counter or allocation;
  future authoritative state transactions must allocate eligible occurrences on commit without
  deriving them from ledger counts or call order.
- Task 5 write sets may be sparse, but every returned/reloaded snapshot and every new visit must be
  sample-complete. Reuse of an omitted sample is valid only for an already persisted visit after
  the mapper loads and authenticates it in the caller's session.
- Task 5 mapper `add` and `load` require clean caller ORM `new`/`dirty`/`deleted` collections before
  authority SQL. Task 6 must flush or otherwise finish its ORM work before calling them and must
  skip `add` entirely when the Task 5 write set is empty.

## Mandatory Development Flow

For every future change: plan and obtain approval, split and record tasks in `backlog/`, use strict
RED → GREEN → REFACTOR TDD, apply Python clean-code skills, update all mandatory documents, verify
all tests, deploy, and wait for Pavel's UAT/sign-off.

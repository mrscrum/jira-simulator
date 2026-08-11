# M1 Durable Scrum State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add restart-safe authoritative Scrum work, sprint, member-execution, and status-visit state,
then extend the reviewed live-slice unit of work so that state, semantic counters, eligible natural
decision occurrences, evidence, and projection intent commit atomically.

**Architecture:** Task 5 adds immutable domain snapshots, a third isolated v2 SQLAlchemy model
module, caller-owned-session mapping, and reversible revision 015 without exposing a live mutation
service. Task 6 wraps the existing `TickSliceCommit` and extends the current runtime-version CAS
transaction; it adds no schema and performs no mechanical transition, allocation, scheduling, or
external delivery.

**Tech Stack:** Python 3.12, immutable dataclasses and Pydantic v2 inputs, SQLAlchemy 2, Alembic,
SQLite/WAL with foreign keys enabled, pytest, Ruff.

## Authority and Global Constraints

- Later explicit instructions, `AGENTS.md`, and `docs/v2/high-level-plan.md` are authoritative in
  that order. The detailed Stage 1 draft is reference material only.
- Begin from clean reviewed head `11f3663` with sole Alembic head `014`. Preserve the reviewed Task
  1-4 canonical blueprint bytes/hash, team/run/runtime identities, live ledgers, deterministic
  decision coordinates, samples, calendar semantics, and public behavior.
- Follow strict RED -> GREEN -> REFACTOR. Write and run each task's complete focused test selection
  before production code, retain the expected failure with pipeline propagation, implement only that
  task, rerun the identical selection to GREEN, and refactor only while it stays GREEN.
- Apply the installed Superpowers TDD skill and project Python clean-code skills. Public interfaces
  are typed, functions are at most 30 lines, functions accept at most three arguments, dependencies
  are injected, and modules have one responsibility.
- The immutable canonical `ResolvedTeamBlueprint` remains the sole configuration authority. Do not
  normalize or duplicate member names, roles, capacities, WIP limits, responsibilities,
  proficiencies, configured availability, routes, statuses, timing cells, risk policy, calendar, or
  Scrum policy into new relational configuration tables.
- Persist only semantic member identity plus mutable runtime availability overlays, business-date
  consumption, work/sprint/visit execution state, immutable factor/sample provenance, and explicit
  semantic counter/evaluation state.
- Every domain identity uses the reviewed `SEMANTIC_ID_V1` helpers and every coordinate is a true
  integer in `0..2^53-1`. Database/autoincrement IDs, ledger counts, `MAX(...)`, insertion order,
  timestamps, scheduler order, Python `hash()`, random UUIDs, and Jira IDs never allocate replay
  identity or occurrence.
- Internal rank is exactly `(priority_order, relative_rank, semantic_work_item_uuid)`. Priority is
  the closed `HIGHEST`, `HIGH`, `MEDIUM`, `LOW`, `LOWEST` order; `relative_rank` is a non-negative
  safe integer. Never store or compare raw Jira LexoRank as simulator rank.
- Persist elapsed, remaining, required, credited, queue, pause, and consumed duration as exact
  non-negative integer microseconds within signed SQLite 64-bit range. Retain Task 3's finite sample
  floats and complete canonical draw/parameter provenance separately; never recompute a persisted
  duration requirement after restart.
- Persisted instants use `UTCDateTime`, reject naive values, normalize aware offsets to UTC, and
  reload aware UTC. Business dates use exact date values, not UTC-date approximations.
- Every run-derived table carries `team_id` and `run_id`. Child ownership uses composite
  `(team_id, run_id, id)` foreign keys so separately valid identifiers from different teams/runs
  cannot be combined.
- Task 5 owns revision 015. Task 6 adds no migration and must not create revision 016. A schema defect
  discovered during Task 6 returns to a reviewed Task 5 fix round before Task 6 continues.
- No task in this plan implements capacity allocation, event-time/live flow, backlog generation,
  planning, lifecycle transitions, carryover, dependencies/blocking, risk mechanics, scheduler/API
  wiring, Jira/OpenAI calls, projection delivery, frontend, deployment, UAT, or M1 completion.
- Work is local only. Do not access live credentials, mutate Jira/AWS, deploy, push, or claim UAT.
- After each task, run its review gate before starting the next task. Use the plan-scoped ignored SDD
  workspace, task brief, implementation report, review package, task review, and fix-loop ledger
  required by `superpowers:subagent-driven-development`.

---

Status: IN PROGRESS

## Task Checklist

- [x] Task 5 — Persist authoritative Scrum state at revision 015 — completed 2026-08-11
- [ ] Task 6 — Commit authoritative Scrum state atomically

## Deferred Validation Hardening Outside These Tasks

`DraftEnvelope` rejects self-referential Python mapping/list input before opening a session or
mutating state, but the recursive JSON-key guard currently surfaces raw `RecursionError` instead of
the normal invalid-JSON `ValueError`. Preserve this reviewed non-blocking Minor for a dedicated
validation-hardening micro-fix before an API accepts arbitrary v2 payload objects. Neither Task 5 nor
Task 6 changes that payload boundary.

## Task 5: Persist authoritative Scrum state at revision 015

**Goal:** Define, validate, persist, and restart-reload a representative authoritative Scrum state
without changing lifecycle state, consuming a counter, advancing runtime, appending a ledger, or
owning a database transaction.

**Dependency:** Start only from reviewed head `11f3663` and revision 014. Read the global constraints
above, `backend/app/v2/domain/team_blueprint.py`, `team_runtime.py`, `deterministic_rng.py`,
`sampling.py`, `business_calendar.py`, the existing persistence modules, and the focused Task 1-4
tests before writing Task 5 tests.

**Inputs:** A persisted `ResolvedTeamBlueprint`, semantic team/run/member/sprint/item/visit UUIDs,
one aware commit-time snapshot, explicit lifecycle values, deterministic simulator rank, Task 3
sample/factor provenance, exact microsecond clocks, and initial semantic counter/evaluation rows.

**Outputs:** Frozen authoritative Scrum-state value objects; relational mappings for semantic member
identity, runtime overlay/consumption, work items/factors, sprints/scope, status visits/samples,
semantic counters, and natural-evaluation deduplication; caller-owned-session mapping; and reversible
Alembic revision 015.

### Binding choices for Task 5

- Lifecycle enums are closed and exact:
  - `WorkItemLifecycle`: `BACKLOG`, `ACTIVE`, `DONE`, `CANCELLED`.
  - `SprintLifecycle`: `PLANNED`, `ACTIVE`, `COMPLETED`.
  - `StatusVisitLifecycle`: `OPEN`, `CLOSED`.
  Constructors and replacement validate coherent snapshots, but this task exposes no transition
  method and does not decide when any lifecycle value changes.
- `WorkPriority` is the exact closed order `HIGHEST`, `HIGH`, `MEDIUM`, `LOW`, `LOWEST`.
  `SimulatorRank(priority, relative_rank, work_item_id)` validates the non-negative safe integer and
  compares only by that three-part tuple.
- `SemanticCounterKind` is closed to `SPRINT_ORDINAL`, `ITEM_SEQUENCE`, `VISIT_ORDINAL`, and
  `NATURAL_DECISION_OCCURRENCE` for this slice. `SemanticCounterScope(kind, scope_id, scope_key)` is
  globally unambiguous within team/run: sprint scope uses the team UUID plus `SCRUM`; item scope uses
  the team UUID plus the exact `CreationKind`; visit scope uses the item UUID plus `VISIT`; natural
  scope uses the decision entity UUID plus the exact `DecisionType`.
- A stored `SemanticCounter` carries `next_value`, not the last issued value. It starts at zero,
  normally remains in `0..2^53-1`, and may become exactly `2^53` only as the persisted exhausted
  sentinel after allocating coordinate `2^53-1`; the sentinel can never be claimed. Counter state is
  never inferred from domain rows or append ledgers.
- A natural eligibility identity is exactly
  `(team_id, run_id, decision_type, semantic_entity_id, business_date)`. Its stored committed
  occurrence is a non-negative safe integer and is separately unique within
  `(team_id, run_id, decision_type, semantic_entity_id, occurrence)`.
- `MemberIdentity` stores only semantic member UUID, `team_id`, and persisted-blueprint array index;
  member identity is team-scoped and stable across runs. Names, roles, responsibilities, proficiency,
  nominal capacity, WIP, and configured availability remain in the immutable blueprint. Mutable
  member overlay/consumption rows carry both `team_id` and `run_id`.
- `MemberAvailabilityOverlay` stores source, aware UTC half-open interval, availability fraction,
  optional daily-capacity ceiling, reason, and provenance. `MemberBusinessDateConsumption` stores
  exact consumed labor microseconds for one member/business date. This task stores values but applies
  no overlay composition or allocation formula.
- `WorkItemState` stores semantic creation kind/sequence, issue type, Fibonacci points, priority,
  integer relative rank, lifecycle, canonical current status key, and aware created/updated times.
  Sprint membership and the open visit are derived from their own constrained tables rather than
  duplicated mutable foreign keys on the work item.
- `WorkItemFactor` is one immutable `DESCRIPTION_QUALITY` or `LATENT_COMPLEXITY` value in `[0,1]`
  with canonical provenance JSON and SHA-256. Factor sampling/risk effects are out of scope.
- `SprintState` stores semantic ordinal, lifecycle, immutable planned start/end UTC instants,
  optional observed start/end, and aware created/updated times. `SprintScopeEntry` stores item
  membership with added/removed instants; at most one non-removed scope row exists per item.
- `StatusVisitState` stores semantic item-scoped ordinal, lifecycle, canonical status/activity keys,
  optional semantic member owner, entered/closed instants, and exact required/elapsed/remaining,
  queue, pause, and credited microseconds. Required equals elapsed plus remaining where applicable;
  closed visits have `closed_at`, open visits do not; at most one open visit exists per work item.
- `StatusVisitSample` is immutable and one-to-one with a visit. It retains timing profile/version,
  sampler versions, dwell anchors/touch bounds, both Task 3 explicit unit draws and complete canonical
  draw provenance, sampled float hours, and the exact persisted required microseconds/hash used by
  `StatusVisitState`.
- `ScrumStateSnapshot` is the detached aggregate returned by the mapper. `ScrumStateWriteSet` is a
  frozen tuple-only collection of complete after-images that Task 6 will persist; it contains no
  callable, SQLAlchemy object, transition decision, or external intent.

### Files

- Create `backend/app/v2/domain/scrum_state.py` for the exact enums, validation helpers, frozen state
  records, `SemanticCounterScope`, `SemanticCounter`, `NaturalDecisionEvaluation`,
  `ScrumStateSnapshot`, and `ScrumStateWriteSet`.
- Create `backend/app/v2/persistence/scrum_state_models.py` as the third v2 model module and keep it
  limited to the new Task 5 SQLAlchemy mappings.
- Create `backend/app/v2/persistence/scrum_state_mapper.py` for detached domain/ORM mapping through a
  caller-owned `Session`; it must never call `commit`, `rollback`, `begin`, or an external adapter.
- Create `backend/alembic/versions/015_add_v2_authoritative_scrum_state.py` with
  `revision = "015"` and `down_revision = "014"`.
- Modify `backend/app/v2/domain/__init__.py` and `backend/app/v2/persistence/__init__.py` only for
  additive lazy public exports approved by this task.
- Modify `backend/app/models/__init__.py` to register the third v2 model module without reintroducing
  the reviewed cold-import cycle.
- Modify `backend/tests/v2/conftest.py` so every v2 SQLite test connection explicitly executes
  `PRAGMA foreign_keys=ON`; retain file-backed disposable SQLite and engine disposal.
- Create `backend/tests/v2/unit/test_scrum_state.py`.
- Create `backend/tests/v2/integration/test_scrum_state_mapper.py`.
- Create `backend/tests/v2/integration/test_migration_015.py`.
- Modify `backend/tests/v2/integration/test_projection_boundary.py` for every new table and every
  direct/lazy cold-import permutation.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` for pure-domain isolation, no hidden
  allocation/nondeterminism, mapper transaction ownership, and additive exports.
- Create `evidence/v2/M1-T05/README.md`; retain exact RED/GREEN/regression/migration/static outputs in
  that directory.
- Modify `README.md`, `changelog.md`, `assumptions.md`, `agent_instruction.md`,
  `backlog/v2/README.md`, and this plan after implementation as required by `AGENTS.md`.

### Relational schema owned by revision 015

- `v2_member_identities`: semantic UUID primary key; `team_id` and safe blueprint index; unique
  `(team_id, blueprint_index)` and composite `(team_id, id)` identity key. This configuration-free
  semantic identity is not run-derived.
- `v2_member_availability_overlays`: semantic UUID primary key; composite member ownership; source,
  UTC start/end, fraction, nullable capacity ceiling, reason, canonical provenance/hash, and created
  time. Configured blueprint availability is not copied here.
- `v2_member_business_date_consumption`: composite team/run/member/business-date key and exact
  non-negative `consumed_labor_microseconds`.
- `v2_work_items`: semantic UUID primary key; team/run, `CreationKind`, safe creation sequence,
  supported issue type/points, priority, safe relative rank, lifecycle, canonical status key, and UTC
  created/updated times; unique creation coordinate and composite identity key.
- `v2_work_item_factors`: semantic UUID primary key; composite work-item ownership; exact factor
  kind/value, canonical provenance/hash, and recorded time; unique factor kind per item.
- `v2_sprints`: semantic UUID primary key; team/run, safe ordinal, lifecycle, immutable planned UTC
  start/end, nullable observed UTC start/end, created/updated times; unique ordinal, one partial unique
  active sprint per team/run, and composite identity key.
- `v2_sprint_scope`: semantic UUID primary key; composite sprint and item ownership, added/removed UTC
  instants; unique sprint/item pair and one partial unique non-removed scope row per item.
- `v2_status_visits`: semantic UUID primary key; composite work-item and optional member ownership;
  safe item-scoped ordinal, lifecycle/status/activity, UTC entered/closed, and every required,
  elapsed, remaining, queue, pause, and credit value as checked non-negative integer microseconds;
  unique item ordinal and one partial unique open visit per item.
- `v2_status_visit_samples`: visit UUID primary/composite FK; timing/sampler versions, canonical
  dwell/touch parameter and draw provenance JSON plus SHA-256, sampled finite floats, and exact
  required microseconds matching the visit state.
- `v2_semantic_counters`: composite team/run/scope identity and checked `next_value` in `0..2^53`,
  where only `2^53` is the exhausted sentinel; no server default and no autoincrement identity.
- `v2_natural_decision_evaluations`: semantic UUID primary key; composite team/run, exact decision
  type, semantic entity, business date, committed occurrence, commit UUID, and recorded time; unique
  eligibility identity and unique committed occurrence coordinate.
- All partial unique indexes are declared identically in ORM metadata and migration 015. Upgrade
  creates parents before children; downgrade drops children before parents.

### Public mapping interfaces

```python
@dataclass(frozen=True)
class ScrumStateQuery:
    team_id: UUID
    run_id: UUID


class SqlAlchemyScrumStateMapper:
    def load(self, session: Session, query: ScrumStateQuery) -> ScrumStateSnapshot: ...
    def add(self, session: Session, state: ScrumStateWriteSet) -> ScrumStateSnapshot: ...
```

`load` returns detached immutable values in deterministic semantic order. `add` validates the full
write set before the first SQL statement, inserts only Task 5 state, flushes so constraints surface
inside the caller's transaction, and returns the detached persisted subset. The caller decides to
commit or roll back; a mapper exception leaves that decision with the caller.

### RED and focused behavior

- [x] Write all Task 5 unit/integration/migration/import tests before production or migration code.
- [x] Cover exact closed enums; strict scalar/UUID/UTC/date validation; direct construction,
  replacement, copy, deepcopy, and reconstruction policy; supported Fibonacci points; rank ordering
  through every tie; boolean/negative/unsafe integer rejection; microsecond balance; lifecycle/time
  coherence; canonical sample/factor payload and digest validation; and tuple/deep immutability.
- [x] Prove blueprint-only configuration: semantic member IDs derive from persisted blueprint array
  position, while no new table contains names, roles, configured capacity/WIP, responsibility,
  proficiency, route, timing-grid, calendar, or policy configuration.
- [x] Prove the mapper opens no session and owns no transaction, emits no commit/rollback, flushes
  within a caller transaction, reloads every state type exactly, and a caller rollback leaves every
  new table empty.
- [x] With `PRAGMA foreign_keys=ON`, reject mixed team/run member, work, sprint, scope, visit, sample,
  counter, and evaluation references. Prove one-active-sprint, one-open-visit, one-current-scope,
  unique ordinal/factor/eligibility constraints, and every SQL check.
- [x] Dispose the engine, create a fresh engine/session factory, and prove all detached state,
  microseconds, canonical provenance, counters, eligibility assignments, and ordering reload exactly.
- [x] Cold-import each team/live/Scrum-state model and each lazy persistence/UOW export first in a
  fresh process; prove `Base.metadata.create_all()` registers all revision-015 tables with no cycle.
- [x] Seed populated legacy, Task 1, and Task 2 tables at revision 014, including runtime version and
  all three ledgers. Prove `014 -> 015 -> 014 -> 015` preserves their ordered content and table,
  column, index, FK, and check metadata byte-for-byte; downgrade removes only Task 5 tables and
  re-upgrade recreates them empty with sole head 015.
- [x] From `backend/`, run the exact RED command with pipeline propagation:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/red.txt
  ```

- [x] Confirm non-zero RED is caused only by absent Task 5 modules/interfaces/revision 015 and new
  table expectations, not malformed tests, an import cycle, or a Task 1-4 regression.

### GREEN, refactor, and verification

- [x] Implement the minimum domain values and validation needed for the complete RED selection.
- [x] Implement mappings and migration in the exact schema order above; use existing `UTCDateTime`,
  canonical JSON/hash, immutable-value, and semantic-ID helpers instead of copies.
- [x] Implement the caller-owned-session mapper with short table-specific mapping helpers. Do not add
  a service, transition method, allocator, implicit clock, counter claim, or commit/rollback call.
- [x] Rerun the identical focused command, replacing only `red.txt` with `green.txt`; retain GREEN.
- [x] Refactor while focused GREEN remains unchanged and run an AST scan proving every touched/new
  function is at most 30 lines and accepts at most three arguments.
- [x] From `backend/`, retain these exact verification classes under `evidence/v2/M1-T05/` using
  `set -o pipefail`: Task 1 focused, Task 2 focused, Task 3 focused, Task 4 focused, all `tests/v2 -q`,
  full safe `tests -q`, Ruff `../.venv/bin/python -B -m ruff check --no-cache .`, Alembic `heads
  --verbose`, `branches --verbose`, `history`, the populated round trip, the AST/import scan, and
  repository-root `git diff --check`.
- [x] Write `evidence/v2/M1-T05/README.md` with base/head, environment, exact RED reason, GREEN and
  regression counts, schema/constraint inventory, PRAGMA proof, caller-transaction rollback,
  disposed-engine restart, cold-import matrix, populated migration round trip, sole head, warning
  inventory, static checks, and explicit no-external/no-live statement. Include no secrets.
- [x] Append Task 5 to `changelog.md` and `assumptions.md`; update current-state `README.md`,
  `agent_instruction.md`, `backlog/v2/README.md`, and this plan. Mark Task 5 complete only after its
  task review is clean; leave Task 6 unchecked and M1 in progress.
- [x] Stage only Task 5 production/tests/migration/evidence/mandatory documentation, verify
  `git diff --cached --check`, and commit exactly:

  ```bash
  git commit -m "feat(v2): persist authoritative scrum state"
  ```

**Done condition:** Revision 015 is the sole linear head; exact immutable authoritative Scrum state
round-trips through caller-owned-session mapping and a disposed-engine restart; relational checks,
partial uniqueness, and real SQLite composite FKs reject every invalid/mixed-team case; populated
revision 014 survives the reversible migration unchanged; configuration remains solely in the
canonical blueprint; no transition, allocation, UOW mutation, counter claim, external call, or
revision 016 exists; focused/v2/full tests, Ruff, static checks, evidence, documentation, and review
are complete under the exact Task 5 commit.

## Task 6: Commit authoritative Scrum state atomically

**Goal:** Extend the reviewed v2 unit of work so one validated authoritative slice atomically
compare-and-swaps runtime, writes Task 5 state after-images, advances explicit semantic counters and
eligible natural-decision occurrences, and appends the existing activity, ground-truth, and pending
projection records.

**Dependency:** Begin only after Task 5 is reviewed and committed with sole head 015. Read this full
Task 6 brief first, then the Task 5 public contracts, `live_slice.py`, `unit_of_work.py`, and their
focused tests. Task 6 consumes revision 015 unchanged and creates no migration.

**Inputs:** One existing `TickSliceCommit`, one immutable `ScrumStateWriteSet`, caller-supplied
semantic counter claims with exact expected-next values, eligible natural-decision claims with exact
business-date keys and expected committed occurrences, and the existing session factory.

**Outputs:** An immutable authoritative-slice command/result, typed stale/conflict errors, additive
UOW port/adapter operations, and proof that runtime/state/counters/evaluations/evidence/intents are
one rollback and restart boundary.

### Binding choices for Task 6

- Add `AuthoritativeTickSliceCommit(live_slice, state, counter_claims,
  natural_decision_claims)`; it wraps rather than replaces/reinterprets `TickSliceCommit`.
- Add `CommittedAuthoritativeTickSlice(live_slice, state, counters,
  natural_decision_evaluations)`; `live_slice` remains the exact existing `CommittedTickSlice`.
- Add `SemanticCounterClaim(scope, expected_next, count)`. `expected_next` is a safe non-negative
  integer, `count` is a positive safe integer, and `expected_next + count - 1` must remain at most
  `2^53-1`. The claimed half-open ordinal range is `[expected_next, expected_next + count)`; a new
  counter value of exactly `2^53` is the exhausted sentinel and rejects every later claim.
- New sprint/item/visit IDs and stored ordinal fields in the write set must match every claimed range
  through the existing `sprint_rng_id`, `item_rng_id`, and `visit_rng_id` helpers. A missing, extra,
  mismatched, duplicate, or unrelated claim rejects before a session is opened.
- Add `EligibleNaturalDecisionClaim(decision, business_date)`, where `decision` is the reviewed
  `DecisionOccurrence`. Its exact dedup key is decision type + entity UUID + business date, and
  `decision.occurrence` must equal the natural counter's expected next value. This task accepts the
  counter plumbing for `RISK_CANCELLATION_OUTCOME` and `RISK_MEMBER_UNAVAILABLE_OUTCOME` only; it
  implements no probability, eligibility, duration, or mechanical risk behavior.
- Disabled, forced, duplicate, and ineligible evaluations are represented by absence of an eligible
  claim and consume nothing. Forced rework and member-unavailability duration draws do not advance
  this natural counter in Task 6.
- Runtime CAS remains the team-level writer fence. Counter updates additionally use
  `WHERE next_value = :expected_next`; zero updated rows raise `StaleSemanticCounter`. An existing
  identical eligibility row returns the stored occurrence without increment; a differing occurrence
  or immutable key/content collision raises `NaturalEligibilityConflict`.
- `ScrumStateWriteSet` contains complete after-images only for rows touched by this slice. The mapper
  persists them in the caller's current session. Task 6 does not derive transitions, allocate labor,
  recalculate time, resample, inspect Jira, or synthesize a write set.
- The atomic order is: validate the complete command before session creation; open one short session;
  runtime team/run/version CAS; apply Task 5 state after-images; CAS semantic counters; insert/resolve
  eligible natural-evaluation rows; append existing activity, ground truth, and pending projection;
  flush; commit once. Any exception rolls back every class.
- Existing `commit_tick_slice`, paging, replay, and adapter boundaries remain public and compatible.
  Refactor shared private in-session helpers, but never call `commit_tick_slice` from inside the new
  operation because it owns its own session/transaction.

### Files

- Create `backend/app/v2/domain/authoritative_slice.py` for claim validation, command/result values,
  and cross-binding of claims to Task 5 state and existing live-slice drafts.
- Modify `backend/app/v2/domain/__init__.py` only for additive exports.
- Modify `backend/app/v2/persistence/scrum_state_mapper.py` to apply complete after-images and exact
  claims through the caller-owned session without commit/rollback.
- Modify `backend/app/v2/persistence/unit_of_work.py` to add the port/SQLAlchemy operation, typed
  errors, and shared in-session transaction steps while preserving all Task 2 operations.
- Modify `backend/app/v2/persistence/__init__.py` only for lazy additive exports.
- Create `backend/tests/v2/unit/test_authoritative_slice.py`.
- Create `backend/tests/v2/integration/test_authoritative_unit_of_work.py`.
- Modify `backend/tests/v2/integration/test_projection_boundary.py` for the unchanged post-commit
  adapter-only boundary of the new operation.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` for pure command-domain isolation,
  no external adapters/hidden allocation, and no revision 016.
- Create `evidence/v2/M1-T06/README.md`; retain exact RED/GREEN/regression/atomicity/static outputs in
  that directory.
- Modify `README.md`, `changelog.md`, `assumptions.md`, `agent_instruction.md`,
  `backlog/v2/README.md`, and this plan after implementation as required by `AGENTS.md`.
- Do not create or modify an Alembic revision in Task 6.

### Public UOW interface

```python
class V2UnitOfWork(ABC):
    @abstractmethod
    def commit_authoritative_slice(
        self, commit: AuthoritativeTickSliceCommit
    ) -> CommittedAuthoritativeTickSlice: ...
```

`SqlAlchemyV2UnitOfWork.commit_authoritative_slice` accepts only the immutable command. It calls
`commit.validate()` before requesting a session, returns detached domain values only after
`session.commit()` succeeds, rolls back and re-raises typed/domain/database errors, and imports or
calls no simulation engine, scheduler, Jira/OpenAI client, projection adapter, or delivery method.

### RED and focused behavior

- [ ] Write all Task 6 command/UOW/adapter/architecture tests before production changes.
- [ ] Prove direct construction, replacement, forged nested write sets/claims, wrong team/run,
  malformed/unsafe/overflowing expected-next ranges, non-contiguous ordinals, wrong semantic IDs,
  unsupported natural decision types, naive dates/instants, and claim/write mismatches fail before a
  session is opened and leave revision-015 state unchanged.
- [ ] Prove one successful commit advances runtime version `0 -> 1`, persists representative member
  consumption, work/factor, sprint/scope, visit/sample state, advances sprint/item/visit/natural
  counters exactly once, stores exact eligible business-date occurrence assignments, and appends the
  existing ordered activity/ground-truth/projection records.
- [ ] Inject failure independently at runtime update; every Task 5 state write class; every counter
  update; natural-evaluation insert; activity insert; ground-truth insert; projection insert; final
  flush; and commit. After each failure, a fresh session must observe the original runtime/version,
  state, counters, evaluations, and ledgers with zero partial change.
- [ ] Load the same runtime/counter versions through two UOW instances. Prove the winner commits and
  the stale writer raises `StaleRuntimeVersion` or `StaleSemanticCounter` as appropriate, with no
  state/claim/ledger rows from the loser.
- [ ] Prove identical authoritative replay returns existing immutable state/evaluation/ledger rows
  and consumes no second occurrence. Conflicting semantic state, counter range, eligibility
  occurrence, or canonical evidence raises the exact typed conflict and rolls back the full slice.
- [ ] Prove an empty natural-claim tuple (disabled/ineligible/forced/duplicate caller outcome) leaves
  natural counters unchanged. Prove only a successful eligible claim increments and a rollback does
  not create a gap.
- [ ] Dispose the engine after a committed slice, create a fresh engine/session factory/UOW, and
  reload the exact runtime, all Task 5 state, counter next-values, eligibility assignments, canonical
  provenance, append cursors, and pending intents. The next valid claim continues at the persisted
  expected occurrence.
- [ ] Call an exploding fake projection adapter only after the authoritative commit returns; prove
  its failure cannot undo or mutate any committed runtime/state/counter/evaluation/ledger row. AST
  and spy tests prove neither UOW operation imports or invokes an adapter or external client.
- [ ] Prove Alembic still reports sole head 015, empty branch output, linear history, and no changed or
  new migration file relative to the reviewed Task 5 commit.
- [ ] From `backend/`, run the exact RED command with pipeline propagation:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_authoritative_slice.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T06/red.txt
  ```

- [ ] Confirm non-zero RED is caused only by absent Task 6 command/UOW interfaces and expectations,
  while Task 5 schema/reload and existing Task 2 tests remain otherwise healthy.

### GREEN, refactor, and verification

- [ ] Implement the immutable authoritative command/result and short validation helpers first.
- [ ] Extend the mapper with caller-session after-image and counter/evaluation operations; translate
  only recognized stale/semantic conflicts to the exact typed errors.
- [ ] Refactor the existing private UOW in-session path just enough for both public commit methods to
  share runtime CAS and ledger persistence while each public method still owns exactly one session,
  commit, rollback, and detached result.
- [ ] Rerun the identical focused command, replacing only `red.txt` with `green.txt`; retain GREEN.
- [ ] Refactor while focused GREEN remains unchanged and run an AST scan proving every touched/new
  function is at most 30 lines and accepts at most three arguments.
- [ ] From `backend/`, retain these exact verification classes under `evidence/v2/M1-T06/` using
  `set -o pipefail`: Task 1 focused, Task 2 focused, Task 3 focused, Task 4 focused, Task 5 focused,
  Task 6 focused, all `tests/v2 -q`, full safe `tests -q`, Ruff, Alembic graph, no-migration diff,
  disposed-engine restart/continuation, atomic failure matrix, AST/import scan, and repository-root
  `git diff --check`.
- [ ] Write `evidence/v2/M1-T06/README.md` with base/head, environment, exact RED reason, GREEN and
  regression counts, validation-before-session proof, successful write ordering, every injected
  rollback point, stale-writer result, replay/conflict behavior, no-gap eligible occurrence proof,
  disposed-engine restart/continuation, adapter boundary, unchanged sole revision 015, warning
  inventory, static checks, and explicit no-external/no-live statement. Include no secrets.
- [ ] Append Task 6 to `changelog.md` and `assumptions.md`; update current-state `README.md`,
  `agent_instruction.md`, `backlog/v2/README.md`, and this plan. Mark both tasks and this plan
  complete only after the Task 6 review is clean; leave M1 in progress for the separately planned
  allocator/live-flow slices.
- [ ] Stage only Task 6 production/tests/evidence/mandatory documentation, verify
  `git diff --cached --check`, and commit exactly:

  ```bash
  git commit -m "feat(v2): commit scrum state atomically"
  ```

**Done condition:** With revision 015 unchanged, one validated authoritative slice atomically
compare-and-swaps runtime, persists complete Task 5 after-images, claims exact semantic ranges,
advances only committed eligible natural occurrences, and appends existing evidence/intents; every
validation, injected failure, stale writer, semantic conflict, and external adapter failure leaves no
partial or skipped authoritative progress; a fresh process reloads and continues from the exact
committed state; existing `commit_tick_slice` remains compatible; no allocator, transition, live-flow,
scheduler, external call, migration 016, deployment, UAT, or M1 completion is added; focused/v2/full
tests, Ruff, static checks, evidence, documentation, and review are complete under the exact Task 6
commit.

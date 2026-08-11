# M1 Deterministic Capacity Credit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic member-capacity allocation, then atomically persist one bounded segment
of touch credit and its calibration evidence through the accepted Task 6 unit of work.

**Architecture:** Task 7 is a pure immutable domain policy implementing
`AVAILABILITY_OVERLAY_V1`, `CAPACITY_ALLOCATOR_V1`, and segment-local
`PROFICIENCY_CREDIT_V1`. Task 8 adds one coherent detached read port and an application service that
turns the pure result into the existing `AuthoritativeTickSliceCommit`; revision 015 remains the
sole schema head, and the slice deliberately stops before dwell or workflow transitions.

**Tech Stack:** Python 3.12, immutable dataclasses and frozen Pydantic v2 blueprints, exact integer
microsecond arithmetic, SQLAlchemy 2, SQLite/WAL, pytest, Ruff.

## Authority and Global Constraints

- Later explicit instructions, `AGENTS.md`, and `docs/v2/high-level-plan.md` are authoritative in
  that order. Optional capacity/flow notes may clarify mechanics only where they do not expand this
  plan.
- Begin from clean reviewed head `847e799`, with Tasks 1-6 accepted and Alembic revision 015 as the
  sole linear head. Preserve every accepted public behavior and the additive v1/v2 boundary.
- Follow strict RED -> GREEN -> REFACTOR. Run the complete focused selection to an expected non-zero
  result before production code, retain that output with `set -o pipefail`, implement only the
  current task, rerun the identical selection to GREEN, and refactor only while it remains GREEN.
- Apply the installed Superpowers TDD skill and project Python clean-code skills. Public interfaces
  are typed, functions accept at most three arguments, functions are at most 30 lines, dependencies
  are injected, and each module has one responsibility.
- `ResolvedTeamBlueprint` remains the only configuration authority. Do not copy names, roles,
  responsibilities, proficiency, nominal capacity, WIP, configured availability, calendar, route,
  timing, risk, or Scrum policy into another configuration table or mutable object.
- Use only reviewed semantic team/run/member/item/visit identities. Database IDs, ledger sequence,
  insertion order, timestamps, scheduler order, Python `hash()`, random UUIDs, and Jira IDs never
  choose a member, order work, or allocate replay identity.
- Every mutable duration and capacity value is an exact non-negative built-in integer microsecond
  within signed SQLite range. Built-in blueprint floats are converted through exact
  `as_integer_ratio()` arithmetic and nearest-ties-to-even rounding; booleans, subclasses,
  non-finite values, negative values, and overflow reject.
- Task 7 performs no I/O and creates no ledger draft. Task 8 performs one coherent read, constructs
  one immutable Task 6 command, and delegates one atomic commit. No network or external adapter call
  occurs before, during, or after either task.
- This plan authorizes capacity ownership and touch credit only. It does not close or open a visit,
  evaluate the dwell gate, move a route/status, change work/sprint/visit lifecycle, emit p50/p99
  monitors, plan or carry sprint scope, run risks/dependencies, schedule a wake, generate backlog,
  deliver a projection, call Jira/OpenAI, touch frontend code, deploy, perform UAT, or complete M1.
- Do not create revision 016 or modify revision 015, ORM schema, or migration metadata. Existing
  visit touch fields, member ownership, runtime overlays, business-date consumption, runtime CAS,
  and ground-truth ledger are sufficient for this slice.
- `PROFICIENCY_CREDIT_V1` is intentionally segment-local. Arbitrary scheduler partition invariance
  and persisted fractional-credit residue are deferred to the separately planned revision 016
  schema task; this plan neither creates nor reserves that revision, and neither concern may be
  simulated with hidden in-memory carry or a new column here.
- Work is local only. Do not access credentials, Jira, OpenAI, AWS, deployment targets, or GitHub
  remotes, and do not push.
- After each task, use the ignored plan-scoped SDD brief/report/review workspace, complete both
  review stages, update all mandatory documentation, and make only the task's exact commit.

---

Status: IN PROGRESS

## Task Checklist

- [ ] Task 7 — Add deterministic capacity allocation — next
- [ ] Task 8 — Commit capacity credit slices — begins only after Task 7 is reviewed and committed

## Deferred Validation Hardening Outside These Tasks

`DraftEnvelope` cyclic Python mapping/list input currently fails before session/state mutation with
a raw `RecursionError`. Preserve this accepted non-blocking Minor for a separate validation task
before an API accepts arbitrary v2 payload objects; neither capacity task changes that boundary.

## Shared Capacity-Credit Contract

- A capacity segment is half-open `[start, end)` in aware UTC and belongs to one team business date.
  Task 7 may shorten the requested interval at the first workday, configured-availability,
  runtime-overlay, daily-capacity-exhaustion, or touch-completion boundary. Task 8 commits exactly
  the returned segment and never loops across a second segment in the same transaction.
- Configured availability is the one active blueprint interval or the default fraction `1.0` and
  nominal daily capacity. Runtime overlays are independent. Effective fraction is the minimum of
  the configured fraction and all active runtime fractions; effective pre-fraction cap is the
  minimum configured cap and all non-null runtime ceilings. Multiplication is exact half-even.
  Existing consumption is never reversed; when it equals or exceeds the resolved cap, remaining
  labor is zero.
- Work order is exactly `SimulatorRank` followed by `entered_at` and semantic visit UUID. Sticky
  eligible owners are retained before new assignment. An owner is released only when touch is
  already complete or the member is ineligible or effectively unavailable for the segment. Merely
  exhausting the current date's remaining capacity does not erase ownership.
- WIP is the count of open positive-touch visits currently owned by a member across the complete
  run snapshot. New assignment requires `active_wip < max_concurrent_wip`. Among eligible members,
  compare `active_wip / max_wip` by integer cross-multiplication, then descending proficiency,
  descending remaining daily labor, then semantic member UUID. Never compare a float WIP ratio.
- After ownership resolution, at most one visit per member receives labor in a segment: the first
  owned visit in work order. An eligible positive-touch visit that receives no labor during a
  positive business subsegment accrues that exact business duration in `queue_microseconds` only
  when the cause is effective capacity, WIP, or member contention. This is queue-business
  accounting, never dwell. Pause, work classification, sprint/scope, samples, counters, natural
  evaluations, and every lifecycle/status value remain byte-for-byte unchanged.
- For proficiency `p_num / p_den`, segment labor `L` earns
  `round_half_even(L * p_num / p_den)` effective touch microseconds, capped at remaining touch.
  When that cap completes touch before the requested end, consume the smallest integer labor
  microseconds whose half-even credit reaches the remaining demand, end the segment there, set
  remaining touch to zero, and release the member while leaving the visit `OPEN` with
  `closed_at=None`.
- Queue-reason precedence is exact: `CAPACITY` when no responsibility-eligible member has remaining
  effective labor, `WIP_LIMIT` when labor exists but every otherwise-selectable member is at WIP,
  then `CONTENTION` when another higher-ordered owned visit receives that member's labor. Zero
  business elapsed accrues no queue. Ineligible, zero-touch, closed, out-of-scope, or already
  touch-complete visits accrue none.
- A segment result retains every ordering key, candidate WIP numerator/denominator, proficiency
  numerator/denominator, capacity contributor, prior consumption, labor debit, effective credit,
  queue reason/accrual, and before/after touch balance required to serialize deterministic
  calibration ground truth.

## Task 7: Add deterministic capacity allocation

**Goal:** Produce one immutable, deterministic `CAPACITY_ALLOCATOR_V1` capacity-segment decision
using `AVAILABILITY_OVERLAY_V1` and segment-local `PROFICIENCY_CREDIT_V1` from a trusted blueprint,
complete authoritative state, requested UTC interval, and explicit eligible open visits, without
opening a session or mutating an input.

**Dependency:** Read this entire brief first. Then read `team_blueprint.py`, `business_calendar.py`,
`scrum_state.py`, `immutable_value.py`, their focused tests, and the accepted Task 5/6 contracts.
Use the binding mechanics below verbatim; do not import a persistence, application, v1 engine,
Jira, OpenAI, scheduler, wall-clock, or random module.

**Inputs:** Exact `ResolvedTeamBlueprint`, complete `ScrumStateSnapshot`, `UtcInterval`, and a unique
tuple of semantic visit UUIDs selected by a later application policy.

**Outputs:** Exact duration helpers; immutable member score, availability resolution, ownership
decision, labor credit, request, and result values; and one pure allocation function.

### Files

- Create `backend/app/v2/domain/duration_math.py` for exact signed-range integer validation,
  hours/fraction/proficiency conversion, half-even rational rounding, and minimum labor inversion.
- Create `backend/app/v2/domain/capacity_allocator.py` for the closed policy enum/value contracts,
  availability resolution, total ordering, one-segment allocation, and pure result construction.
- Modify `backend/app/v2/domain/scrum_state.py` only to delegate its existing retained touch-hours
  conversion to `duration_math.hours_to_microseconds`; preserve exact public values and messages.
- Modify `backend/app/v2/domain/__init__.py` only for lazy additive Task 7 exports.
- Create `backend/tests/v2/unit/test_duration_math.py`.
- Create `backend/tests/v2/unit/test_capacity_allocator.py`.
- Modify `backend/tests/v2/unit/test_scrum_state.py` only for shared-helper parity regression.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` for pure-domain imports, prohibited
  dependencies/nondeterminism, exact public exports, and no schema ownership.
- Create `evidence/v2/M1-T07/README.md` and retain every named RED/GREEN/regression/static output in
  that directory.
- After implementation, update `README.md`, `changelog.md`, `assumptions.md`,
  `agent_instruction.md`, `backlog/v2/README.md`, and this plan as required by `AGENTS.md`.

### Exact interfaces

```python
class OwnershipOutcome(StrEnum):
    ASSIGNED = "ASSIGNED"
    RELEASED = "RELEASED"


class CapacityQueueReason(StrEnum):
    CAPACITY = "CAPACITY"
    WIP_LIMIT = "WIP_LIMIT"
    CONTENTION = "CONTENTION"


@immutable_dataclass
class CapacityMemberScore(ImmutableValue):
    member_id: UUID
    active_wip: int
    max_wip: int
    proficiency_numerator: int
    proficiency_denominator: int
    remaining_labor_microseconds: int


@immutable_dataclass
class AvailabilityResolution(ImmutableValue):
    member_id: UUID
    business_date: date
    effective_fraction_numerator: int
    effective_fraction_denominator: int
    pre_fraction_cap_microseconds: int
    effective_cap_microseconds: int
    consumed_before_microseconds: int
    remaining_before_microseconds: int
    contributor_ids: tuple[str, ...]


@immutable_dataclass
class CapacityOwnershipDecision(ImmutableValue):
    visit_id: UUID
    previous_member_id: UUID | None
    labor_member_id: UUID | None
    owner_after_member_id: UUID | None
    ordered_candidates: tuple[CapacityMemberScore, ...]


@immutable_dataclass
class CapacityOwnershipChange(ImmutableValue):
    visit_id: UUID
    member_id: UUID
    outcome: OwnershipOutcome
    occurred_at: datetime


@immutable_dataclass
class CapacityLaborCredit(ImmutableValue):
    visit_id: UUID
    member_id: UUID
    business_date: date
    labor_microseconds: int
    touch_credit_microseconds: int
    proficiency_numerator: int
    proficiency_denominator: int
    elapsed_before_microseconds: int
    elapsed_after_microseconds: int
    remaining_before_microseconds: int
    remaining_after_microseconds: int


@immutable_dataclass
class CapacityQueueAccrual(ImmutableValue):
    visit_id: UUID
    reason: CapacityQueueReason
    business_microseconds: int
    queue_before_microseconds: int
    queue_after_microseconds: int


@immutable_dataclass
class CapacityAllocationRequest(ImmutableValue):
    blueprint: ResolvedTeamBlueprint
    state: ScrumStateSnapshot
    interval: UtcInterval
    eligible_visit_ids: tuple[UUID, ...]


@immutable_dataclass
class CapacityAllocationResult(ImmutableValue):
    processed_interval: UtcInterval
    business_date: date
    availability: tuple[AvailabilityResolution, ...]
    ownership: tuple[CapacityOwnershipDecision, ...]
    ownership_changes: tuple[CapacityOwnershipChange, ...]
    credits: tuple[CapacityLaborCredit, ...]
    queue_accruals: tuple[CapacityQueueAccrual, ...]
    visit_after_images: tuple[StatusVisitState, ...]
    consumption_after_images: tuple[MemberBusinessDateConsumption, ...]


def allocate_capacity(request: CapacityAllocationRequest) -> CapacityAllocationResult: ...
```

`duration_math.py` exposes exactly these typed functions:

```python
def hours_to_microseconds(hours: float, label: str) -> int: ...
def multiply_microseconds(value: int, factor: float, label: str) -> int: ...
def proficiency_credit(labor_microseconds: int, proficiency: float) -> int: ...
def labor_to_complete(remaining_credit_microseconds: int, proficiency: float) -> int: ...
```

All values reject runtime subclasses and post-construction/replacement forgery consistently with
Tasks 3-6. `contributor_ids` uses stable canonical strings: `BLUEPRINT_DEFAULT`,
`BLUEPRINT_INTERVAL:<zero-based-index>`, and `RUNTIME_OVERLAY:<semantic-uuid>`, ordered exactly in
that sequence. Queue evidence uses only the three closed reasons above and records business
microseconds; no field or payload calls queue time dwell. Ownership changes are exact events:
invalid/unavailable prior-owner release and new assignment occur at the processed start; release
caused by touch completion occurs at the processed end. For the same visit/instant, release sorts
before assignment. A newly assigned owner who completes touch within the segment therefore emits
assignment at start and release at end while `owner_after_member_id` is `None`.

### Binding mechanics

- Build `BusinessCalendar` only from `blueprint.team.timezone` and `blueprint.calendar`. Validate the
  complete state against that exact blueprint before selecting anything. The request interval is
  aware UTC, positive, inside the authenticated holiday horizon, and is shortened rather than
  crossed at the first local business-date/workday or availability boundary.
- Produce one `AvailabilityResolution` for every persisted `MemberIdentity`, in blueprint-index
  order. The active configured interval or default supplies fraction/cap; every active runtime
  overlay may only lower them. Apply the minimum pre-fraction cap and minimum fraction once with
  exact rational half-even arithmetic, then subtract the exact persisted business-date consumption.
- Validate eligible IDs as a unique exact tuple of existing `OPEN`, positive-touch visits from one
  team/run. Sort visits by `SimulatorRank`, `entered_at`, and visit UUID. A member is a candidate only
  when the blueprint responsibility matches `activity_key`; compare WIP fractions by integer cross-
  multiplication, then proficiency descending, remaining labor descending, and member UUID.
- Preserve an eligible/effectively-available sticky owner. Release an ineligible/unavailable or
  already-complete owner at segment start; daily exhaustion alone retains ownership. Assign
  unowned visits in work order while WIP space remains, then give each member's labor to only their
  first owned visit in that same order.
- Choose one common processed end: earliest requested end, workday/date boundary, configured/runtime
  availability boundary, daily-capacity exhaustion, or touch completion. Debit unadjusted labor,
  credit exact capped proficiency work, and release a touch-complete owner at that end. Never close
  the visit or change status/lifecycle.
- `PROFICIENCY_CREDIT_V1` computes
  `round_half_even(labor_microseconds * proficiency_numerator / proficiency_denominator)` and caps
  the result at remaining touch. When credit would complete touch early, consume the smallest
  integer labor microseconds whose half-even credit reaches the remaining demand and use that instant
  as the common processed end. Arithmetic is segment-local: persist no fractional residue or hidden
  carry, and defer arbitrary scheduler partition invariance/residue storage to the separately planned
  revision 016 schema task.
- For every eligible positive-touch visit receiving zero labor over positive business time, accrue
  queue using exact precedence `CAPACITY`, `WIP_LIMIT`, then `CONTENTION`. Do not accrue queue for an
  ineligible/out-of-scope/closed/zero-touch/already-complete visit, and never change pause or dwell.
- Return only changed visit and consumption after-images, ordered by semantic identity, plus complete
  availability/selection/change/credit/queue traces. The result contains no draft, ORM value,
  callable, fractional residue, implicit clock, or hidden second segment.

### TDD steps and exact cases

- [ ] Write `test_duration_math.py` first. Cover zero, one microsecond, exact halves with even/odd
  neighbors, binary-float ratios, proficiency `0.25`, `1.0`, and `2.0`, minimum inverse labor,
  saturation at signed SQLite maximum, bool/int/float subclasses, NaN/infinity, negative values,
  zero proficiency, and overflow. Assert direct construction/replacement cannot bypass exact types.
- [ ] Write `test_capacity_allocator.py` before production code. Build immutable snapshots for:
  default availability; one configured interval; overlapping runtime restrictions; boundary-active
  half-open intervals; a later restriction below prior consumption; daily exhaustion; ineligible
  activity; zero fraction; sticky owner; completed/unavailable release; WIP full/equal fractions;
  every work/member tie-break; two owned visits for one member; two members in parallel; touch
  completion before the requested end; capacity exhaustion before completion; non-working time;
  one-date/DST windows; duplicate/foreign/missing eligible IDs; unsafe clocks; input permutation;
  exact `CAPACITY`/`WIP_LIMIT`/`CONTENTION` queue precedence and accrual; assignment/release event
  instants including assign-then-complete and release-then-reassign; zero/non-business queue;
  direct/replacement/mutation/reconstruction attacks; and unchanged pause/dwell/lifecycle/status,
  samples, work, sprint, counter, and natural collections.
- [ ] Add fixed golden vectors proving exact segment-local `PROFICIENCY_CREDIT_V1` labor/credit and
  balance equations. Do not assert equality between one large segment and arbitrary subdivisions;
  explicitly assert that no fractional residue exists in the request/result or state after-images.
- [ ] Run the focused command from `backend/` and retain the expected non-zero output caused only by
  missing Task 7 modules/interfaces:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_duration_math.py tests/v2/unit/test_capacity_allocator.py tests/v2/unit/test_scrum_state.py tests/v2/unit/test_business_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T07/red.txt
  ```

- [ ] Implement the exact duration functions, frozen contracts, overlay resolver, exact ordering,
  ownership normalization, common segment end, parallel labor debit, effective credit, queue-business
  accrual, after-images, and typed evidence inputs. Never mutate the request/snapshot or consult
  implicit current time.
- [ ] Rerun the identical command to GREEN and save `green.txt`. Refactor only while the identical
  command remains GREEN; use small private request/result helpers rather than long functions.
- [ ] Run Task 3, Task 4, Task 5, and Task 6 focused selections, then all `tests/v2 -q`, the full safe
  `tests -q`, Ruff, cold-import checks, and an AST scan for function/argument limits with
  `set -o pipefail`; retain exact outputs under `evidence/v2/M1-T07/`.
- [ ] Prove `git diff -- backend/alembic backend/app/v2/persistence backend/app/v2/persistence/*.py`
  is empty for Task 7 and Alembic still reports sole head 015, empty branches, and linear history.
- [ ] Record formulas, golden vectors, selection/overlay matrices, immutability, regression counts,
  warnings, environment, and exact commands in `evidence/v2/M1-T07/README.md`.
- [ ] Complete mandatory documentation, mark only Task 7 complete after both review stages are clean,
  leave Task 8 unchecked and M1 in progress, inspect the staged diff, and commit exactly:

  ```bash
  git commit -m "feat(v2): add deterministic capacity allocation"
  ```

**Done condition:** One pure call deterministically returns a validated common capacity segment,
sticky/WIP-safe ownership, exact daily consumption, proficiency-adjusted touch, eligible-denial
queue-business after-images, and complete typed evidence inputs; no input is mutated, no
I/O/nondeterminism/schema/lifecycle or dwell behavior is added, and focused/regression/static/review
gates are clean under the exact Task 7 commit.

## Task 8: Commit capacity credit slices

**Goal:** Load one coherent detached authoritative view and atomically commit exactly one Task 7
capacity result, runtime advance, and deterministic calibration records through the accepted Task 6
operation, without performing any visit or workflow transition.

**Dependency:** Begin only after Task 7 is reviewed and committed. Read this full brief, the accepted
Task 6 command/UOW/replay tests, Task 5 mapper/read behavior, Task 7 public contracts/tests, and the
existing live-ledger factories before writing tests. Revision 015 is frozen.

**Inputs:** Semantic team UUID, a strictly later aware UTC target within the current active sprint
and team business date, one aware recording instant, a coherent persisted blueprint/runtime/state
view, and the Task 7 allocator.

**Outputs:** Immutable read/command/result contracts; a one-session SQLAlchemy read adapter; an
injected application service; deterministic owner-change activity, capacity-resolution/selection/
credit ground truth, and one call to `commit_authoritative_slice`.

### Files

- Create `backend/app/v2/domain/capacity_credit.py` for `AuthoritativeStateView`, the application
  command/result values, coordinate/time validation, and deterministic segment evidence creation.
- Create `backend/app/v2/application/commit_capacity_credit.py` for structural read/commit protocols,
  eligible visit selection from an existing active sprint snapshot, Task 7 invocation, Task 6
  command construction, and the one-call service.
- Create `backend/app/v2/persistence/authoritative_state_reader.py` for the SQLAlchemy adapter that
  structurally satisfies the application read protocol and loads blueprint, runtime, and complete
  state in one caller-clean session.
- Modify `backend/app/v2/persistence/scrum_state_mapper.py` only to expose a typed caller-session
  `load_authoritative` operation that reuses its reviewed refreshed authority and complete-snapshot
  paths; it owns no transaction and performs no DML.
- Modify domain/application/persistence `__init__.py` files only for lazy additive exports.
- Create `backend/tests/v2/unit/test_capacity_credit.py`.
- Create `backend/tests/v2/integration/test_authoritative_state_reader.py`.
- Create `backend/tests/v2/integration/test_capacity_credit_service.py`.
- Modify `backend/tests/v2/integration/test_authoritative_unit_of_work.py` only for exact Task 8
  command compatibility/rollback/replay assertions.
- Modify `backend/tests/v2/integration/test_projection_boundary.py` for empty projection, narrowly
  internal owner-change activity, and prohibited adapter imports/calls.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` for allowed dependency direction,
  one-session reads, no hidden loop/mechanics/external code, and no revision 016.
- Create `evidence/v2/M1-T08/README.md` and retain every named output in that directory.
- After implementation, update `README.md`, `changelog.md`, `assumptions.md`,
  `agent_instruction.md`, `backlog/v2/README.md`, and this plan as required by `AGENTS.md`.

### Exact interfaces

```python
@immutable_dataclass
class AuthoritativeStateView(ImmutableValue):
    blueprint: ResolvedTeamBlueprint
    runtime: TeamRuntime
    state: ScrumStateSnapshot


@immutable_dataclass
class CommitCapacityCreditCommand(ImmutableValue):
    team_id: UUID
    through: datetime
    recorded_at: datetime


@immutable_dataclass
class CommittedCapacityCredit(ImmutableValue):
    allocation: CapacityAllocationResult
    committed: CommittedAuthoritativeTickSlice


class CapacityCreditReader(Protocol):
    def get_authoritative_view(self, team_id: UUID) -> AuthoritativeStateView: ...


class SqlAlchemyV2AuthoritativeStateReader:
    def __init__(self, session_factory: sessionmaker[Session]) -> None: ...
    def get_authoritative_view(self, team_id: UUID) -> AuthoritativeStateView: ...


class CapacityCreditCommitter(Protocol):
    def commit_authoritative_slice(
        self, commit: AuthoritativeTickSliceCommit
    ) -> CommittedAuthoritativeTickSlice: ...


class CommitCapacityCreditService:
    def __init__(
        self,
        reader: CapacityCreditReader,
        committer: CapacityCreditCommitter,
    ) -> None: ...

    def commit(self, command: CommitCapacityCreditCommand) -> CommittedCapacityCredit: ...
```

`SqlAlchemyScrumStateMapper.load_authoritative` has this exact caller-owned-session signature:

```python
def load_authoritative(
    self,
    session: Session,
    query: ScrumStateQuery,
) -> tuple[ResolvedTeamBlueprint, ScrumStateSnapshot]: ...
```

It returns the exact persisted `ResolvedTeamBlueprint` and complete `ScrumStateSnapshot` as the
typed immutable tuple used by the reader; it repeats no SQL mapping or blueprint validation logic.
The reader loads the matching `TeamRuntime` in that same session, returns detached values, and never
calls `commit`, `rollback`, `begin`, a simulation service, or an adapter. Runtime CAS safely rejects
a view made stale after the read.

### Binding application behavior

- Require runtime state `RUNNING`, `through > runtime.simulation_time`, one exact active sprint, and
  `through <= planned_end_at`. The interval must remain within one team business date and holiday
  horizon. Invalid/stale/foreign inputs fail before Task 7 or the commit port.
- Eligible visits are derived, not supplied by an API: take non-removed scope entries in the exact
  active sprint, their `WorkItemLifecycle.ACTIVE` work items, and their exact open positive-touch
  visits with remaining work. Order IDs by Task 7 work order before constructing its request.
- Call `allocate_capacity` once. Do not loop to the original `through` when Task 7 returns an earlier
  segment boundary; advance runtime only to `allocation.processed_interval.end`, preserve runtime
  state and `next_wake_at`, and let a later caller request the next segment.
- Task 8 consumes the reviewed Task 7 seam exactly as
  `allocate_capacity(CapacityAllocationRequest) -> CapacityAllocationResult`. It may serialize the
  result and place its sparse after-images into Task 6, but it must not reinterpret candidate order,
  recompute availability/proficiency/queue, or manufacture an ownership change.
- Build `ScrumStateWriteSet` from only Task 7 visit and business-date-consumption after-images. Visit
  after-images may change owner, touch clocks, credited labor, and the bounded queue-business clock.
  Do not include work, sprint, scope, sample, factor, overlay, counter, or natural-evaluation
  after-images.
  Both claim tuples are empty because no semantic ordinal or natural occurrence is allocated.
- Create commit UUID from
  `capacity-credit-commit/<team-id>/<run-id>/<expected-runtime-version>`. Create deterministic ground-
  truth keys from the same team/run/expected-version prefix: one
  `capacity-resolution/.../<member-id>` record per availability result, one
  `capacity-selection/.../<visit-id>` record per ownership/queue decision, and one
  `capacity-credit/.../<visit-id>/<member-id>` record per credit subsegment. Neither identity
  contains a timestamp or ledger position.
- Resolution payloads contain every configured/runtime contributor and exact cap/consumption result;
  selection payloads contain every ordering/WIP/proficiency/capacity key plus owner and queue reason;
  every credit payload contains requested/processed UTC intervals, business date, labor debit,
  effective credit, exact proficiency ratio, and before/after touch/queue balances. All payloads
  include `CAPACITY_ALLOCATOR_V1`, `AVAILABILITY_OVERLAY_V1`, `PROFICIENCY_CREDIT_V1`, expected
  runtime version, and proposed post-slice runtime version. `occurred_at` is the processed end and
  ledger `recorded_at` is the command value.
- Emit `OWNER_ASSIGNED` and `OWNER_RELEASED` activity only when the internal visit owner actually
  changes according to `allocation.ownership_changes`; emit release before assignment for a same-
  visit/same-instant replacement and no activity for retained ownership, queue, or ordinary credit.
  Assignment occurs at the processed start, invalid/unavailable-owner release occurs at the start,
  and touch-completion release occurs at the processed end. Use `aggregate_type="STATUS_VISIT"`, the
  semantic visit UUID, and `aggregate_version=expected_runtime_version + 1`. This is explicitly
  `POST_SLICE_RUNTIME_VERSION_V1`, a temporary activity aggregate-version convention until a later
  schema owns per-visit versions; include that convention and both runtime versions in the canonical
  activity payload. Set `projection_intents=()` and never call an adapter.
- Leave a touch-complete visit `OPEN`, `closed_at=None`, and at its unchanged status with
  `remaining_work_microseconds=0` and `member_id=None`. Task 8 must not inspect the next route step,
  sample a visit, claim a visit ordinal, evaluate dwell, or change any lifecycle.
- Queue increments only by Task 7's exact business subsegment for an eligible positive-touch visit
  denied labor by `CAPACITY`, `WIP_LIMIT`, or `CONTENTION`. Never label or serialize this value as
  dwell, and never infer a lifecycle or readiness result from it.
- Validate the complete `AuthoritativeTickSliceCommit` before calling the committer. Call the
  committer exactly once, return its exact committed result plus the Task 7 result, propagate typed
  stale/semantic conflicts, and perform no hidden retry.

### TDD steps and exact cases

- [ ] Write `test_capacity_credit.py` first. Cover exact types, UTC normalization, team/run/blueprint
  cross-binding, strict-later target, business-date and sprint-end bounds, deterministic commit,
  activity, and evidence keys, canonical payload/hash, expected/post-slice runtime versions, exact
  owner-change activity ordering and temporary aggregate semantics, empty projection/claims, sparse
  allowed after-images, exact queue-business payload terminology, and rejection of any visit
  close/open, status/lifecycle/sample/counter change. Include direct/replacement/subclass/mutation/
  reconstruction attacks.
- [ ] Write reader tests before adapter code. Prove one session returns the exact refreshed persisted
  blueprint/runtime/complete snapshot; cross-team/run, missing/corrupt authority, cached corruption,
  external update/deletion, dirty/new/deleted caller state, disposal/reopen, detached return values,
  no DML, and no commit/rollback are handled consistently with Task 5.
- [ ] Write service tests with strict fakes first, then real SQLite integration. Prove derived active-
  sprint eligibility, one allocator call, one committer call, early segment truncation, exact visit
  and consumption after-images, capacity/WIP/contention queue-business increments, touch-completion
  release while the visit stays open, assignment/release-only activity, deterministic resolution/
  selection/every-credit ground truth, empty projection/claims, no work/sprint/status/sample
  mutation, and stable propagation of invalid and stale input before partial effects.
- [ ] Add a two-reader stale race, injected Task 6 failures at runtime/visit/consumption/ground-truth/
  final-flush/commit, identical semantic evidence replay, conflicting evidence rollback, response-
  loss reload, disposed-engine continuation, and consecutive segment tests. Assert every failure
  leaves runtime, Scrum state, counters, natural evaluations, and all ledgers unchanged.
- [ ] Add architecture spies/import scans proving no visit constructor/sample factory/transition,
  route walker, dwell calculation, monitor, planner, lifecycle, scheduler, risk/dependency, Jira,
  OpenAI, projection adapter, v1 engine, wall-clock, or random UUID path is called or imported.
- [ ] Run the focused command from `backend/` and retain the expected non-zero output caused only by
  missing Task 8 modules/interfaces:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_capacity_credit.py tests/v2/integration/test_authoritative_state_reader.py tests/v2/integration/test_capacity_credit_service.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T08/red.txt
  ```

- [ ] Implement the exact contracts, coherent read adapter, eligibility selector, deterministic
  evidence builder, Task 6 command builder, and one-call service. Keep domain construction pure and
  keep SQLAlchemy out of domain/application modules.
- [ ] Rerun the identical command to GREEN and save `green.txt`; refactor only while it remains
  GREEN. Run an AST scan and split helpers before any function exceeds the project limits.
- [ ] Run Task 1 through Task 7 focused selections, all `tests/v2 -q`, full safe `tests -q`, Ruff,
  cold direct/lazy import permutations, architecture/static scans, and exact warning accounting with
  `set -o pipefail`; retain outputs under `evidence/v2/M1-T08/`.
- [ ] Prove Alembic reports sole head 015, empty branches, and linear history; compare migration and
  ORM schema files byte-for-byte with the Task 7 base and retain a no-revision-016/no-schema-diff
  artifact.
- [ ] Record the read/session matrix, exact command/payload examples, rollback/replay/restart matrix,
  no-transition and no-adapter proofs, test counts, warnings, environment, and commands in
  `evidence/v2/M1-T08/README.md`.
- [ ] Complete mandatory documentation, mark Task 8 complete only after both review stages are clean,
  leave this plan complete but M1 in progress for separately planned flow/planning/lifecycle work,
  inspect the staged diff, and commit exactly:

  ```bash
  git commit -m "feat(v2): commit capacity credit slices"
  ```

**Done condition:** One application command reads a coherent authoritative view, deterministically
selects existing active-sprint touch visits, and commits one Task 7 segment's runtime/state,
assignment/release activity, and resolution/selection/credit ground truth through Task 6. Queue
advances only for exact eligible-denial business subsegments, and reload/restart creates no duplicate
credit or partial effect. Visits remain open; dwell/status/lifecycle/planning/scheduler/risk/Jira/
projection/schema behavior remains absent; focused, regression, atomicity, restart, static, evidence,
documentation, and review gates are clean under the exact Task 8 commit.

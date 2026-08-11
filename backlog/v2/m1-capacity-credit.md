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
- Begin from the clean branch containing this reviewed plan. The accepted Tasks 1-6 implementation
  baseline is `847e799`, and Alembic revision 015 remains the sole linear head. Preserve every
  accepted public behavior and the additive v1/v2 boundary.
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
- Capacity composition is not algebraically reassociable. Convert only blueprint nominal/override
  hours floats independently with `hours_to_microseconds`. Preserve each runtime
  `MemberAvailabilityOverlay.daily_capacity_ceiling_microseconds` exact built-in `int | None`
  unchanged after signed-range validation. Take the minimum of those integer caps, then apply the
  selected exact availability-fraction ratio to that integer and half-even once. Never reinterpret a
  runtime ceiling as hours, multiply hours by fraction first, or combine their ratios.
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

- A capacity segment is a strictly positive half-open `[start, end)` interval in aware UTC and
  belongs to one team business date. Its start must itself be a working instant; a non-working start
  rejects instead of jumping. Task 7 ignores every structural/exhaustion candidate `<= start` and
  chooses the first candidate strictly after start among requested end, workday/date,
  configured-availability, runtime-overlay, daily-capacity-exhaustion, and touch-completion
  boundaries. If capacity is already exhausted at start, it processes the next positive structural
  or requested segment with zero labor and exact denial queue. Task 8 commits exactly the returned
  segment and never loops across a second segment in the same transaction.
- Configured availability is the one active blueprint interval or the default fraction `1.0` and
  nominal daily capacity. Runtime overlays are independent. Effective fraction is the minimum of
  the configured fraction and all active runtime fractions; effective pre-fraction cap is the
  minimum configured cap and all non-null runtime ceilings. Resolve this composition in exactly
  three stages: convert only the blueprint nominal/override hours contributor with
  `hours_to_microseconds` using its exact binary ratio and one half-even rounding; preserve each
  runtime `daily_capacity_ceiling_microseconds` exact integer unchanged after validation and take the
  integer minimum; multiply that integer by the selected exact fraction ratio and half-even once.
  Reinterpretation/reassociation is forbidden. The blueprint-hours binding golden is
  `hours=1.000000001 -> 3_600_000_004` microseconds, followed by
  `fraction=0.95 -> 3_420_000_004`; the combined-ratio result `3_420_000_003` is invalid. Existing
  consumption is never reversed; when it equals or exceeds the resolved cap, remaining labor is
  zero.
- Work order is exactly the four-field tuple
  `(WORK_PRIORITY_ORDER.index(work_item.priority.value), work_item.relative_rank,
  visit.entered_at, work_item.id)`. Compare those fields directly in that order. Never order via a
  `SimulatorRank` object, whose item UUID precedes `visit.entered_at`, and never use the visit UUID
  as the final tie-break. Sticky eligible owners are retained before new assignment. An owner is
  released only when touch is already complete or the member is ineligible or effectively
  unavailable for the segment. Merely exhausting the current date's remaining capacity does not
  erase ownership.
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
- When one member owns multiple eligible positive-touch visits, that member's labor goes only to the
  highest-ordered owned visit. Every lower-ordered owned visit denied labor for that reason receives
  `CONTENTION` and the exact positive business-subsegment queue accrual; it is not classified as
  `CAPACITY` merely because the member's labor has already been allocated higher in the same segment.
- For proficiency `p_num / p_den`, segment labor `L` earns
  `round_half_even(L * p_num / p_den)` effective touch microseconds, capped at remaining touch.
  When that cap completes touch before the requested end, consume the smallest integer labor
  microseconds whose half-even credit reaches the remaining demand, end the segment there, set
  remaining touch to zero, and release the member while leaving the visit `OPEN` with
  `closed_at=None`.
- A retained sticky owner with zero remaining effective labor produces `CAPACITY` for that visit,
  based on the retained owner's capacity, even when another responsibility-eligible member has
  labor; sticky ownership forbids reassignment. For an unowned visit, queue-reason precedence is
  closed and exact: `CAPACITY` when no responsibility-eligible, effectively available member has
  remaining labor; `WIP_LIMIT` when labor exists but every candidate is WIP-full; otherwise
  `CONTENTION` when labor and WIP space exist but selected members serve higher-ordered owned work.
  Zero business elapsed accrues no queue. Ineligible, zero-touch, closed, out-of-scope, or already
  touch-complete visits accrue none.
- A segment result retains every ordering key, candidate WIP numerator/denominator, proficiency
  numerator/denominator, capacity contributor, prior consumption, labor debit, effective credit,
  queue reason/accrual, before/after touch balance, typed processed-boundary causes, and typed owner-
  release cause required to serialize deterministic calibration ground truth without reconstructing
  policy. Each contributor retains its kind, canonical ID, configured/runtime interval, source,
  reason, exact fraction ratio, exact integer ceiling, and exactly one authority proof: blueprint
  canonical SHA for the default/active configured contributor or canonical runtime-overlay
  provenance JSON/SHA for a runtime contributor. Contributor order is blueprint default or the
  active blueprint interval first, followed by runtime overlays in ascending semantic overlay UUID
  order; input/row order never changes the trace.

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

**Outputs:** Exact duration helpers; immutable four-field work-order key, member score, availability
contributor/resolution, ownership decision, labor credit, request, and result values; and one pure
allocation function.

### Self-contained authority and constraints

- Later explicit instructions, `AGENTS.md`, and `docs/v2/high-level-plan.md` govern in that order.
  Begin from the clean branch containing this reviewed plan; Tasks 1-6 implementation baseline
  `847e799` is accepted and revision 015 is the sole Alembic head. Preserve accepted behavior and
  the additive v1/v2 boundary; optional capacity/flow notes cannot expand this task.
- Use strict RED -> GREEN -> REFACTOR with retained `set -o pipefail` evidence. Apply the installed
  Superpowers TDD and Python clean-code skills; keep public types exact, functions within three
  arguments/30 lines, dependencies injected, and modules single-purpose.
- `ResolvedTeamBlueprint` is the only configuration authority. Never copy configuration into a
  mutable object or table. Validate the complete immutable `ScrumStateSnapshot` against the exact
  blueprint and use only semantic team/run/member/item/visit/overlay UUIDs.
- Every duration/capacity value is an exact non-negative built-in integer microsecond within signed
  SQLite range. Convert each built-in float through `as_integer_ratio()`; reject booleans,
  subclasses, non-finite/negative values, and overflow. Runtime overlay capacity ceilings are
  already exact built-in integer microseconds and must only be type/range validated. Apply only the
  staged rounding contract below; reinterpretation or reassociation is a contract violation.
- Task 7 is a pure domain policy: no session, ORM, ledger draft, I/O, network, adapter, implicit
  clock, scheduler, randomness, v1 engine, Jira/OpenAI, frontend, deployment, UAT, or push. Do not
  access credentials, AWS/deployment targets, or GitHub remotes.
- Capacity ownership, bounded queue-business accounting, and touch credit are the entire scope. Do
  not close/open a visit, evaluate dwell, move route/status, change any lifecycle, plan/carry scope,
  run risks/dependencies, schedule wakes, generate backlog, emit projection, or complete M1.
- Do not alter revision 015 or create/reserve revision 016. Segment-local proficiency carries no
  fractional residue; arbitrary scheduler partition invariance/residue persistence belongs to the
  separately planned revision 016 schema task and must not be emulated in memory.
- After GREEN/regression/static verification, retain evidence, complete both review stages, update
  every `AGENTS.md` document, and make only Task 7's exact commit.

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


class AvailabilityContributorKind(StrEnum):
    BLUEPRINT_DEFAULT = "BLUEPRINT_DEFAULT"
    BLUEPRINT_INTERVAL = "BLUEPRINT_INTERVAL"
    RUNTIME_OVERLAY = "RUNTIME_OVERLAY"


class CapacityProcessedBoundaryCause(StrEnum):
    REQUEST_END = "REQUEST_END"
    WORKDAY_END = "WORKDAY_END"
    BUSINESS_DATE_END = "BUSINESS_DATE_END"
    CONFIGURED_AVAILABILITY_CHANGE = "CONFIGURED_AVAILABILITY_CHANGE"
    RUNTIME_OVERLAY_CHANGE = "RUNTIME_OVERLAY_CHANGE"
    DAILY_CAPACITY_EXHAUSTION = "DAILY_CAPACITY_EXHAUSTION"
    TOUCH_COMPLETION = "TOUCH_COMPLETION"


class OwnershipReleaseCause(StrEnum):
    TOUCH_COMPLETE = "TOUCH_COMPLETE"
    RESPONSIBILITY_INELIGIBLE = "RESPONSIBILITY_INELIGIBLE"
    EFFECTIVELY_UNAVAILABLE = "EFFECTIVELY_UNAVAILABLE"


@immutable_dataclass
class CapacityWorkOrderKey(ImmutableValue):
    work_priority_order_index: int
    relative_rank: int
    entered_at: datetime
    work_item_id: UUID


@immutable_dataclass
class CapacityMemberScore(ImmutableValue):
    member_id: UUID
    active_wip: int
    max_wip: int
    proficiency_numerator: int
    proficiency_denominator: int
    remaining_labor_microseconds: int


@immutable_dataclass
class AvailabilityContributor(ImmutableValue):
    kind: AvailabilityContributorKind
    contributor_id: str
    configured_starts_at: datetime | None
    configured_ends_at: datetime | None
    runtime_starts_at: datetime | None
    runtime_ends_at: datetime | None
    source: str
    reason: str | None
    fraction_numerator: int
    fraction_denominator: int
    pre_fraction_cap_microseconds: int | None
    blueprint_canonical_sha256: str | None
    overlay_provenance_json: str | None
    overlay_provenance_sha256: str | None


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
    contributors: tuple[AvailabilityContributor, ...]


@immutable_dataclass
class CapacityOwnershipDecision(ImmutableValue):
    visit_id: UUID
    work_order_key: CapacityWorkOrderKey
    previous_member_id: UUID | None
    labor_member_id: UUID | None
    owner_after_member_id: UUID | None
    ordered_candidates: tuple[CapacityMemberScore, ...]


@immutable_dataclass
class CapacityOwnershipChange(ImmutableValue):
    visit_id: UUID
    member_id: UUID
    outcome: OwnershipOutcome
    release_cause: OwnershipReleaseCause | None
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
    processed_boundary_causes: tuple[CapacityProcessedBoundaryCause, ...]
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
Tasks 3-6. Contributor invariants are exact and closed:

- Blueprint default uses kind/ID `BLUEPRINT_DEFAULT`, all four interval fields `None`,
  `source="BLUEPRINT"`, `reason=None`, non-null `blueprint_canonical_sha256`, and null overlay
  provenance. The active configured interval instead uses kind `BLUEPRINT_INTERVAL`, canonical ID
  `BLUEPRINT_INTERVAL:<zero-based-index>`, its exact configured UTC starts/ends and reason, null
  runtime starts/ends, the same blueprint SHA, and null overlay provenance.
- A runtime row uses kind `RUNTIME_OVERLAY`, canonical ID
  `RUNTIME_OVERLAY:<lower-case-hyphenated-overlay-uuid>`, null configured starts/ends, its exact
  runtime UTC starts/ends/source/reason, null blueprint SHA, and its exact already-validated canonical
  `overlay_provenance_json`/lower-case SHA-256. It retains its exact fraction ratio and exact integer
  ceiling without reinterpretation. Runtime contributors sort by semantic overlay UUID after the one
  blueprint contributor.
- Exactly one authority proof is populated. Every UTC instant is normalized; all irrelevant
  interval/provenance fields are explicitly `None`; direct/replace/mutation/reconstruction attacks
  revalidate these cross-field rules.

`processed_boundary_causes` is a non-empty tuple of every tied cause at the selected strictly
positive end, in the declaration order above; causes whose candidate is `<= start` are absent.
Queue evidence uses only the three closed reasons and records business microseconds; no field or
payload calls queue time dwell. Ownership changes are exact events: a release always has its exact
`OwnershipReleaseCause`, assignment always has `release_cause=None`, invalid/unavailable prior-owner
release and new assignment occur at the processed start, and touch-completion release occurs at the
processed end. For the same visit/instant, release sorts before assignment. A newly assigned owner
who completes touch within the segment therefore emits assignment at start and release at end while
`owner_after_member_id` is `None`. Task 8 serializes these typed facts and never reconstructs a cause.

### Self-contained shared capacity-credit contract and binding mechanics

- Build `BusinessCalendar` only from `blueprint.team.timezone` and `blueprint.calendar`. Validate the
  complete state against that exact blueprint before selecting anything. The request interval is
  aware UTC, positive, inside the authenticated holiday horizon, and starts at a working instant; a
  non-working start is invalid and is never advanced implicitly. Compute candidates from requested
  end, local business-date/workday, configured/runtime availability, daily-capacity exhaustion, and
  touch completion; discard every candidate `<= interval.start`, then choose the minimum remaining
  end. The returned half-open segment must satisfy `start < end`, belongs to one business date, and
  represents only one common segment. An exact boundary at start selects the new half-open state.
  Capacity already exhausted at start is a denial condition, not a zero-length boundary: process to
  the next positive structural/request end with zero labor and queue the exact business duration.
- Produce one `AvailabilityResolution` for every persisted `MemberIdentity`, in blueprint-index
  order. The active configured interval or default supplies fraction/cap; every active runtime
  overlay may only lower them. Compute the contributor authority SHA exactly as
  `canonical_sha256(json.loads(blueprint.canonical_json()))`; Task 8 later requires it to equal the
  coherent runtime's `blueprint_sha256`. Convert only the configured nominal/override hours through
  `hours_to_microseconds` using the float's exact binary ratio and half-even once. Validate every
  non-null `MemberAvailabilityOverlay.daily_capacity_ceiling_microseconds` as an exact non-negative
  built-in integer within signed SQLite range and preserve it unchanged. Take the minimum of those
  integer caps. Select the minimum availability fraction by exact ratio comparison, multiply the
  selected ratio by that integer cap, half-even once, then subtract exact persisted business-date
  consumption. Never send a runtime integer ceiling through `hours_to_microseconds`, pre-multiply an
  hours float by a fraction, or combine/reassociate ratios. The mandatory blueprint golden is
  `hours_to_microseconds(1.000000001, "daily capacity") == 3_600_000_004`, then fraction `0.95`
  produces `3_420_000_004`; `3_420_000_003` is forbidden. Order the contributor trace as the
  blueprint default/active interval first, then runtime overlays by ascending semantic overlay UUID.
- Validate eligible IDs as a unique exact tuple of existing `OPEN`, positive-touch visits from one
  team/run. Build and retain `CapacityWorkOrderKey` directly as
  `(WORK_PRIORITY_ORDER.index(work_item.priority.value), work_item.relative_rank,
  visit.entered_at, work_item.id)` and sort only by those four fields. Never compare
  `work_item.simulator_rank`/`SimulatorRank`, and never append or substitute `visit.id`. A member is
  a candidate only when the blueprint responsibility matches `activity_key`; compare WIP fractions
  by integer cross-multiplication, then proficiency descending, remaining labor descending, and
  member UUID.
- Preserve an eligible/effectively-available sticky owner. Release an ineligible/unavailable or
  already-complete owner at segment start; daily exhaustion alone retains ownership. A retained
  sticky owner with zero remaining effective labor is not replaced by another eligible member: it
  receives zero labor and exact `CAPACITY` queue denial based on that owner. Assign unowned visits in
  work order while WIP space remains, then give each member's labor to only their first owned visit
  in that same order. When that member owns another lower-ordered eligible positive-touch visit, the
  lower visit receives zero labor and exact `CONTENTION` queue accrual for the processed business
  segment, even though the member's post-allocation remaining labor is zero.
- WIP is the complete run-snapshot count of open positive-touch visits owned by a member. New
  assignment requires `active_wip < max_concurrent_wip`; compare candidate WIP fractions by integer
  cross-multiplication, followed by proficiency descending, remaining labor descending, and semantic
  member UUID. Never use float division or input order.
- Choose one common strictly-positive processed end under the boundary rule above and retain every
  tied `CapacityProcessedBoundaryCause` in enum declaration order. Debit unadjusted labor, credit
  exact capped proficiency work, and release a touch-complete owner at that end. Retain the exact
  `OwnershipReleaseCause` on every release. Never close the visit or change status/lifecycle.
- `PROFICIENCY_CREDIT_V1` computes
  `round_half_even(labor_microseconds * proficiency_numerator / proficiency_denominator)` and caps
  the result at remaining touch. When credit would complete touch early, consume the smallest
  integer labor microseconds whose half-even credit reaches the remaining demand and use that instant
  as the common processed end. Arithmetic is segment-local: persist no fractional residue or hidden
  carry, and defer arbitrary scheduler partition invariance/residue storage to the separately planned
  revision 016 schema task.
- For every eligible positive-touch visit receiving zero labor over positive business time, apply
  retained-sticky `CAPACITY` first. For an unowned visit only, use `CAPACITY` when no
  responsibility-eligible/effectively-available member has labor, `WIP_LIMIT` when labor exists but
  all candidates are WIP-full, then `CONTENTION` when labor/WIP space exist but selected members
  serve higher-ordered owned work. Do not accrue queue for an ineligible/out-of-scope/closed/zero-
  touch/already-complete visit, and never change pause or dwell.
- Return only changed visit and consumption after-images, ordered by semantic identity, plus complete
  availability/selection/change/credit/queue traces. Retain every four-field work key, candidate
  WIP/proficiency/capacity input, ordered contributor, prior consumption, labor/credit, queue reason,
  before/after balance, processed-boundary causes, release cause, and contributor authority/provenance
  required by Task 8 ground truth. The result contains no draft, ORM value, callable, fractional
  residue, implicit clock, reconstructed evidence fact, or hidden second segment.

### TDD steps and exact cases

- [ ] Write `test_duration_math.py` first with concrete tests
  `test_hours_to_microseconds_uses_exact_binary_ratio_and_half_even`,
  `test_half_even_rational_rounding_uses_even_neighbor`,
  `test_proficiency_credit_golden_vectors`, and `test_labor_to_complete_is_minimal`.
  Parameterize built-in values/boundaries and assert exact outputs: `0.0 -> 0`,
  `1.000000001 -> 3_600_000_004`, proficiency `(4, 0.25) -> 1`, `(3, 1.0) -> 3`, and
  `(3, 2.0) -> 6`; for every inverse vector assert `credit(labor - 1) < remaining <= credit(labor)`.
  Add named rejection parametrizations `test_duration_math_rejects_non_exact_runtime_types` and
  `test_duration_math_rejects_invalid_or_overflowing_values` for booleans, int/float subclasses,
  NaN, infinities, negatives, zero proficiency, and signed-SQLite overflow.
- [ ] Write `test_capacity_allocator.py` before production code. The first RED cases are
  `test_capacity_rounding_converts_each_hours_value_before_fraction_without_reassociation` asserting
  exact contributor cap `3_600_000_004`, the exact binary-float ratio for `0.95` as
  `(4_278_419_646_001_971, 4_503_599_627_370_496)`, and effective cap `3_420_000_004` while
  explicitly rejecting `3_420_000_003`; and
  `test_runtime_overlay_permutation_preserves_resolution_and_contributor_order`, which supplies
  reversed overlay rows but expects blueprint contributor first and runtime UUIDs ascending with
  byte-identical results. Assert every contributor's exact kind/ID, configured/runtime UTC interval,
  source/reason, fraction ratio, integer ceiling, and mutually exclusive blueprint canonical SHA or
  canonical overlay provenance JSON/SHA.

  ```python
  cap = hours_to_microseconds(1.000000001, "daily capacity")
  assert cap == 3_600_000_004
  assert multiply_microseconds(cap, 0.95, "availability fraction") == 3_420_000_004
  assert multiply_microseconds(cap, 0.95, "availability fraction") != 3_420_000_003
  ```

- [ ] Add `test_runtime_integer_ceiling_is_preserved_without_hours_conversion_or_rerounding`.
  Configure blueprint capacity `2.0 hours -> 7_200_000_000`, runtime ceiling
  `3_600_000_003`, and fraction `0.95`. Assert the runtime contributor and selected pre-fraction cap
  remain exactly `3_600_000_003`, then the single fraction step yields `3_420_000_003`. Spy or
  monkeypatch `hours_to_microseconds` to prove it is called for the blueprint value only and never
  for the runtime integer; bool, integer subclass, negative, and overflow ceilings reject.

- [ ] Add exact ordering/denial tests
  `test_work_order_uses_entered_at_before_opposed_item_uuid`,
  `test_work_order_uses_item_uuid_not_visit_uuid_as_final_tie_break`, and
  `test_sticky_exhausted_owner_reports_capacity_even_when_other_member_is_idle`. The first expects
  an older-entered item with the larger item UUID to sort first; the second expects equal entry
  instants to follow item UUID despite reversed visit UUIDs; the third expects owner A unchanged,
  member B unselected, zero labor, and one `CAPACITY` queue accrual.
- [ ] Parameterize `test_unowned_queue_reason_precedence` as
  `[("no_labor", CAPACITY), ("all_wip_full", WIP_LIMIT),
  ("higher_owned_work", CONTENTION)]`. Add named tests
  `test_sticky_owner_is_released_only_for_binding_release_causes`,
  `test_lower_owned_visit_queues_contention_while_higher_owned_visit_uses_member_labor`,
  `test_two_members_credit_in_parallel`, `test_touch_completion_shortens_common_segment`, and
  `test_ineligible_closed_or_zero_touch_visits_never_accrue_queue` with exact before/after microsecond
  balances and assignment/release instants. The one-member/two-owned-visits vector gives the higher
  visit the only positive credit and gives the lower visit zero labor plus `CONTENTION` and the exact
  full processed business microseconds in queue.
- [ ] Parameterize `test_allocator_segment_boundaries` across configured/runtime boundaries, daily
  exhaustion, workday/date/DST boundaries, touch completion, and tied causes. Add named
  `test_exact_boundary_start_uses_new_half_open_state_and_next_positive_boundary`,
  `test_nonworking_start_rejects_instead_of_jumping`, and
  `test_capacity_exhausted_at_start_advances_positive_segment_with_capacity_queue`. Assert the
  returned end is always strictly greater than start, candidates `<= start` are ignored, the
  exhausted-at-start vector advances to the next request/structural boundary with zero labor and
  exact `CAPACITY` queue, and typed boundary causes are complete and declaration-ordered. Add
  validation/immutability tests for duplicate/foreign/missing eligible IDs, unsafe clocks,
  ineligible/zero-touch/closed/completed visits, input permutations, direct/replacement/subclass/
  mutation/reconstruction attacks, contributor interval/provenance exclusivity, release causes, and
  unchanged pause/dwell/lifecycle/status/sample/work/sprint/counter/natural collections.
- [ ] Add `test_proficiency_credit_v1_segment_local_golden_vectors` with exact labor, credit, and
  before/after balance equations for proficiency `0.25`, `1.0`, and `2.0`. Assert no fractional
  residue field exists and do not assert equality between one large segment and arbitrary
  subdivisions.
- [ ] Run the focused command from `backend/` and retain the expected non-zero output caused only by
  missing Task 7 modules/interfaces:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_duration_math.py tests/v2/unit/test_capacity_allocator.py tests/v2/unit/test_scrum_state.py tests/v2/unit/test_business_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T07/red.txt
  ```

- [ ] Implement `duration_math.py` around private
  `_round_half_even_ratio(numerator: int, denominator: int) -> int`. `hours_to_microseconds` obtains
  the exact float ratio and rounds `numerator * 3_600_000_000 / denominator` once;
  `multiply_microseconds` rounds `value * factor_numerator / factor_denominator` once;
  `proficiency_credit` delegates the same primitive; `labor_to_complete` binary-searches the smallest
  labor satisfying the reviewed credit predicate and verifies the preceding microsecond fails.
- [ ] Implement `capacity_allocator.py` with private frozen `_AllocationContext`,
  `_AvailabilityInputs`, `_ResolvedOwnership`, and `_ProcessedBoundary` bundles so every helper has
  at most three arguments. `_AllocationContext` holds the validated request, calendar, business date,
  work/visit/member indexes, blueprint SHA, and configured/runtime boundaries. Use these exact helper
  responsibilities and preserve the shown composition order:

  ```python
  def _availability_contributors(context, member_id):
      configured = _configured_contributor(context, member_id)
      runtime = tuple(_runtime_contributor(row) for row in context.overlays(member_id))
      return (configured, *sorted(runtime, key=_runtime_overlay_uuid))

  def _resolve_member_availability(context, member_id):
      contributors = _availability_contributors(context, member_id)
      pre_fraction_cap = min(cap for cap in _present_caps(contributors))
      fraction = _minimum_exact_fraction(contributors)
      effective_cap = _round_half_even_ratio(pre_fraction_cap * fraction.numerator, fraction.denominator)
      inputs = _AvailabilityInputs(member_id, contributors, pre_fraction_cap, fraction, effective_cap)
      return _resolution_from_inputs(context, inputs)

  def _common_processed_boundary(context, ownership):
      candidates = _typed_boundary_candidates(context, ownership)
      positive = tuple(candidate for candidate in candidates if candidate.end > context.interval.start)
      return _minimum_boundary_with_all_tied_causes(positive)

  def allocate_capacity(request):
      context = _validate_request(request)
      availability = _resolve_all_availability(context)
      ordered_visits = _ordered_eligible_visits(context)
      ownership = _resolve_sticky_then_unowned(context, availability, ordered_visits)
      boundary = _common_processed_boundary(context, ownership)
      return _apply_segment(context, ownership, boundary)
  ```

  `_configured_contributor` calls `hours_to_microseconds` exactly once for the selected blueprint
  nominal/override hours and records blueprint authority fields. `_runtime_contributor` calls
  `_exact_runtime_ceiling`, which accepts only exact built-in `int | None` in range and returns it
  unchanged; neither calls an hours helper. `_ordered_eligible_visits` constructs the exact four-
  field key. `_resolve_sticky_then_unowned` owns WIP/member ordering, sticky exhaustion, lower-owned-
  visit contention, and closed denial precedence. `_typed_boundary_candidates` records typed causes;
  `_minimum_boundary_with_all_tied_causes` rejects an empty set and declaration-orders every cause
  tied at the strictly-positive minimum. `_apply_segment` delegates to small helpers for labor debit,
  segment-local credit, typed completion release, denial queue clocks, and sparse after-images; it
  does not recompute a cause. Never mutate request/snapshot state or consult implicit time.
- [ ] Rerun the identical command to GREEN and save `green.txt`. Refactor only while the identical
  command remains GREEN; use small private request/result helpers rather than long functions.
- [ ] Run Task 3, Task 4, Task 5, and Task 6 focused selections, then all `tests/v2 -q`, the full safe
  `tests -q`, Ruff, cold-import checks, and an AST scan for function/argument limits with
  `set -o pipefail`; retain exact outputs under `evidence/v2/M1-T07/`.
- [ ] Prove `git diff -- backend/alembic backend/app/v2/persistence backend/app/v2/persistence/*.py`
  is empty for Task 7 and Alembic still reports sole head 015, empty branches, and linear history.
- [ ] Record formulas, golden vectors, selection/overlay/contention matrices, strictly-positive
  boundary and exhausted-at-start vectors, typed contributor/release traces, immutability, regression
  counts, warnings, environment, and exact commands in `evidence/v2/M1-T07/README.md`.
- [ ] Complete mandatory documentation, mark only Task 7 complete after both review stages are clean,
  leave Task 8 unchecked and M1 in progress, inspect the staged diff, and commit exactly:

  ```bash
  git commit -m "feat(v2): add deterministic capacity allocation"
  ```

**Done condition:** One pure call deterministically returns a validated strictly-positive common
capacity segment, sticky/WIP-safe ownership, exact daily consumption, proficiency-adjusted touch,
eligible-denial queue-business after-images, and complete typed evidence inputs; no input is mutated,
no I/O/nondeterminism/schema/lifecycle or dwell behavior is added, and focused/regression/static/review
gates are clean under the exact Task 7 commit.

## Task 8: Commit capacity credit slices

**Goal:** Load one coherent detached authoritative view and atomically commit exactly one Task 7
capacity result, runtime advance, and deterministic calibration records through the accepted Task 6
operation, without performing any visit or workflow transition.

**Dependency:** Begin only after Task 7 is reviewed and committed. Read this full brief, the accepted
Task 6 command/UOW/replay tests, Task 5 mapper/read behavior, Task 7 public contracts/tests, and the
existing live-ledger factories before writing tests. Revision 015 is frozen.

**Inputs:** Semantic team UUID, an aware UTC desired target/horizon within the current active sprint
and team business date, one aware recording instant, a coherent persisted blueprint/runtime/state
view, and the Task 7 allocator. `through` may equal current runtime only to report the stable
already-reached no-write outcome.

**Outputs:** Immutable read/command/result contracts; a one-session SQLAlchemy read adapter; an
injected application service; deterministic owner-change activity, capacity-resolution/selection/
visit-progress ground truth, and one call to `commit_authoritative_slice`.

### Self-contained authority and constraints

- Later explicit instructions, `AGENTS.md`, and `docs/v2/high-level-plan.md` govern in that order.
  Begin only from the clean branch containing this reviewed plan and accepted Task 7 commit. Tasks
  1-6 implementation baseline `847e799` is accepted; revision 015 remains the sole Alembic head.
  Preserve accepted behavior and the additive v1/v2 boundary; optional capacity/flow notes cannot
  expand this task.
- Use strict RED -> GREEN -> REFACTOR with retained `set -o pipefail` evidence. Apply the installed
  Superpowers TDD and Python clean-code skills; keep public types exact, functions within three
  arguments/30 lines, dependencies injected, and modules single-purpose.
- `ResolvedTeamBlueprint` is the sole configuration authority. Read a complete coherent immutable
  blueprint/runtime/state view, validate every semantic team/run/member/item/visit/overlay identity,
  and never persist copied configuration or trust database IDs, row/ledger order, timestamps,
  scheduler order, random UUIDs, Python `hash()`, or Jira IDs for selection/replay identity.
- Every mutable duration/capacity value is an exact non-negative built-in integer microsecond within
  signed SQLite range. Task 8 serializes Task 7's staged hours-then-fraction result exactly and must
  not recompute, reassociate, or re-round availability/proficiency values. Booleans, runtime
  subclasses, non-finite/negative values, and overflow reject.
- Perform one caller-clean SQLAlchemy read, construct one immutable
  `AuthoritativeTickSliceCommit`, and call the Task 6 commit port exactly once. No network/external
  adapter, hidden retry, simulation loop, wall clock, randomness, v1 engine, Jira/OpenAI, frontend,
  deployment, UAT, or push is allowed. Do not access credentials, AWS/deployment targets, or GitHub
  remotes.
- Capacity ownership, bounded queue-business accounting, and touch credit are the entire scope. Do
  not close/open a visit, evaluate dwell, move route/status, change a lifecycle, plan/carry scope,
  run risks/dependencies, schedule wakes, generate backlog, deliver a projection, or complete M1.
- Do not alter revision 015 or create/reserve revision 016. Segment-local proficiency carries no
  fractional residue; arbitrary scheduler partition invariance/residue persistence belongs to the
  separately planned revision 016 schema task and must not be emulated in memory.
- After GREEN/regression/static verification, retain evidence, complete both review stages, update
  every `AGENTS.md` document, and make only Task 8's exact commit.

### Self-contained inherited capacity-credit contract

- The request is aware UTC; current runtime must be a working instant. Task 7 rejects a non-working
  start, ignores boundary/exhaustion candidates `<= start`, and returns exactly one strictly positive
  half-open `[start, end)` segment within one team business date and active sprint. Capacity already
  exhausted at start produces zero labor plus denial queue through the next positive structural or
  request boundary. Commit exactly that segment and never loop to the original target inside the
  transaction; a Task 8 commit can never bump runtime version without advancing the UTC cursor.
- `CommitCapacityCreditCommand.through` is a desired target/horizon, never an idempotency key. Each
  invocation reads current runtime and can commit only its next contiguous segment. A response-loss
  retry below the target commits the following segment with the new expected version; equality raises
  `CapacityCreditTargetReached` without writes. Previous-response reconstruction/durable request
  replay is deferred to a separate receipt/idempotency seam.
- `AVAILABILITY_OVERLAY_V1` converts only blueprint nominal/override hours floats independently with
  `hours_to_microseconds` using exact binary-ratio half-even rounding. Runtime
  `daily_capacity_ceiling_microseconds` values are already exact `int | None`: validate and preserve
  them unchanged, take the minimum integer cap, then multiply that integer by the selected exact
  minimum fraction and half-even once. Never reinterpret a runtime integer as hours or reassociate
  ratios. The blueprint golden is `1.000000001 hours -> 3_600_000_004` microseconds, then
  `fraction=0.95 -> 3_420_000_004`; `3_420_000_003` is forbidden. Contributor order is the blueprint
  default/active interval first, then runtime overlays by ascending semantic overlay UUID. Preserve
  every typed contributor's kind/ID, configured/runtime interval, source/reason, exact ratio/ceiling,
  and mutually exclusive blueprint canonical SHA or canonical runtime provenance JSON/SHA.
- Work order is exactly `(WORK_PRIORITY_ORDER.index(work_item.priority.value),
  work_item.relative_rank, visit.entered_at, work_item.id)`. `SimulatorRank`, visit UUID, input order,
  and float comparison never participate. Member order is exact WIP-ratio cross-multiplication,
  proficiency descending, remaining labor descending, then semantic member UUID.
- Sticky eligible ownership wins before new assignment. A retained sticky owner with zero remaining
  effective labor stays assigned and yields `CAPACITY`, even if another member is idle. For unowned
  visits only: no responsibility-eligible/effectively-available labor is `CAPACITY`; labor with all
  candidates WIP-full is `WIP_LIMIT`; otherwise higher-ordered owned work is `CONTENTION`.
- At most one owned visit per member receives labor in a segment. Labor is debited before exact
  segment-local `PROFICIENCY_CREDIT_V1` credit. A completion shortens the common segment and releases
  the owner but leaves the visit `OPEN`, status/lifecycle unchanged, `closed_at=None`, and remaining
  touch zero. Eligible positive-touch zero-labor visits accrue only exact business-subsegment queue;
  zero/non-business or ineligible/closed/complete visits accrue none and queue is never dwell.
- A lower-ordered eligible positive-touch visit owned by the same member serving higher-ordered owned
  work receives `CONTENTION` and exact queue-business accrual, not post-allocation `CAPACITY`.
- Preserve Task 7's complete availability, four-field selection, ownership-change, labor/credit,
  queue, contributor, boundary-cause, release-cause, and before/after traces without reinterpretation
  so Task 8 can serialize exact deterministic evidence.

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
- Create `backend/tests/v2/fixtures/capacity_credit_v1_vectors.json` with independently reviewed
  literal canonical JSON and lower-case SHA-256 vectors for resolution, selection, progress,
  assignment, and release payloads; production helpers must not generate the expected side.
- Create `backend/tests/v2/integration/test_authoritative_state_reader.py`.
- Create `backend/tests/v2/integration/test_capacity_credit_service.py`.
- Modify `backend/tests/v2/integration/test_authoritative_unit_of_work.py` only for exact Task 8
  command compatibility and direct Task 6 conflicting-ledger rollback assertions; do not add a
  service-level replay promise.
- Modify `backend/tests/v2/integration/test_projection_boundary.py` for empty projection, narrowly
  internal owner-change activity, and prohibited adapter imports/calls.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` for allowed dependency direction,
  one-session reads, no hidden loop/mechanics/external code, and no revision 016.
- Create `evidence/v2/M1-T08/README.md` and retain every named output in that directory.
- After implementation, update `README.md`, `changelog.md`, `assumptions.md`,
  `agent_instruction.md`, `backlog/v2/README.md`, and this plan as required by `AGENTS.md`.

### Exact interfaces

```python
class CapacityCreditTargetReached(ValueError):  # noqa: N818
    pass


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

`CommitCapacityCreditCommand.through` is a desired horizon, not an idempotency key and not a request
identity. `CapacityCreditTargetReached` is the exact stable typed no-write signal and always uses
message `capacity credit target is already reached`. A target before current runtime raises
`ValueError("capacity credit target precedes current simulation time")`.

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

- Validate absolute command types/UTC and the coherent team/run/blueprint view first. Compare desired
  `through` with the freshly read runtime before allocator/committer calls. When equal, raise exact
  `CapacityCreditTargetReached("capacity credit target is already reached")`; when earlier, raise
  exact `ValueError("capacity credit target precedes current simulation time")`. Both paths call
  neither allocator nor committer and write nothing. When later, require runtime state `RUNNING`, one
  exact active sprint, `through <= planned_end_at`, one team business date, and authenticated holiday
  horizon. Other invalid/stale/foreign inputs still fail before Task 7 or the commit port.
- Eligible visits are derived, not supplied by an API: take non-removed scope entries in the exact
  active sprint, their `WorkItemLifecycle.ACTIVE` work items, and their exact open positive-touch
  visits with remaining work. Order IDs only by Task 7's retained four fields:
  `WORK_PRIORITY_ORDER` index, relative rank, visit entry instant, and semantic work-item UUID.
  Neither `SimulatorRank` nor visit UUID participates.
- Call `allocate_capacity` once and commit at most one next segment per service call. Require
  `allocation.processed_interval.start == runtime.simulation_time` and
  `runtime.simulation_time < allocation.processed_interval.end <= command.through`; a gap, overlap,
  reversal, or overshoot rejects before the commit port. Do not loop when Task 7 returns an earlier
  boundary. Advance runtime only to that processed end, preserve runtime state/`next_wake_at`, and
  let another call with the same desired target request the subsequent segment.
- After response loss, repeating the same command never reconstructs or replays the previous result.
  A fresh read below `through` builds the next segment with the new expected runtime version and new
  version-scoped commit/evidence keys; a fresh read equal to `through` raises
  `CapacityCreditTargetReached` with zero writes. Neither branch duplicates the prior credit or key.
  Exact previous-response reconstruction or durable request replay requires a separately planned
  receipt/idempotency seam and is explicitly outside Tasks 7/8.
- Task 8 consumes the reviewed Task 7 seam exactly as
  `allocate_capacity(CapacityAllocationRequest) -> CapacityAllocationResult`. It may serialize the
  result and place its sparse after-images into Task 6, but it must not reinterpret candidate order,
  recompute availability/proficiency/queue, or manufacture an ownership change. Require every
  blueprint contributor SHA to equal the coherent runtime `blueprint_sha256`; runtime contributors
  already carry their authenticated canonical provenance JSON/SHA.
- Build `ScrumStateWriteSet` from only Task 7 visit and business-date-consumption after-images. Visit
  after-images may change owner, touch clocks, credited labor, and the bounded queue-business clock.
  Do not include work, sprint, scope, sample, factor, overlay, counter, or natural-evaluation
  after-images.
  Both claim tuples are empty because no semantic ordinal or natural occurrence is allocated.
- Create commit UUID from
  `capacity-credit-commit/<team-id>/<run-id>/<expected-runtime-version>`. Every activity and ground-
  truth `DraftEnvelope` uses exact `schema_version="1.0"`; semantic identities contain no timestamp,
  database/ledger position, insertion order, or random UUID.
- Create one resolution ground-truth draft per availability result with exact semantic key
  `capacity-resolution/<team-id>/<run-id>/<expected-runtime-version>/<member-id>` and exact metadata
  `record_type="CAPACITY_RESOLUTION"`, `provenance_type="AVAILABILITY_OVERLAY_V1"`. Payloads contain
  the blueprint default/active interval contributor first, runtime contributors in ascending
  semantic overlay UUID order, every independently rounded blueprint hours cap, every unchanged
  validated runtime integer ceiling, selected exact fraction ratio, effective cap, prior consumption,
  and remaining labor.
- Create one selection ground-truth draft per ownership/queue decision with exact semantic key
  `capacity-selection/<team-id>/<run-id>/<expected-runtime-version>/<visit-id>` and exact metadata
  `record_type="CAPACITY_SELECTION"`, `provenance_type="CAPACITY_ALLOCATOR_V1"`. Payloads contain
  `work_priority_order_index`, `relative_rank`, `entered_at`, and `work_item_id` from
  `CapacityWorkOrderKey`, every ordered WIP/proficiency/capacity candidate, previous/labor/after
  owner, and queue reason/accrual.
- Create exactly one progress ground-truth draft for each changed visit in the processed segment,
  including owner-only and queue-only zero-labor changes. Its exact semantic key is
  `capacity-progress/<team-id>/<run-id>/<expected-runtime-version>/<visit-id>` and exact metadata is
  `record_type="STATUS_VISIT_PROGRESS"`, `provenance_type="PROFICIENCY_CREDIT_V1"`. The nullable
  `labor_member_id` and nullable proficiency ratio are `null` when labor is zero. A queue-only visit
  still records zero labor/credit, its exact `CAPACITY`/`WIP_LIMIT`/`CONTENTION` reason and balances,
  typed processed-boundary causes, and unchanged touch balances. Every ground-truth payload contains
  expected/proposed post-slice runtime versions; envelope `occurred_at` is the processed end and
  ledger `recorded_at` is the command value.
- Freeze `live_slice.ground_truth` order as all resolution drafts in blueprint member-index order,
  then all selection drafts by `CapacityWorkOrderKey`, then exactly one progress draft per changed
  visit by `CapacityWorkOrderKey`. Task 7 contributor/candidate order is retained byte-for-byte;
  input, ORM-row, or map order cannot change canonical payloads, hashes, or draft order.
- Emit activity only when the internal visit owner changes according to
  `allocation.ownership_changes`. Assignment uses exact catalogue
  `event_type="WORK_ITEM_ASSIGNED_INTERNAL"` and semantic key
  `work-item-assigned-internal/<team>/<run>/<expected-version>/<visit>/<member>`; release uses exact
  catalogue `event_type="WORK_ITEM_RELEASED_INTERNAL"` and semantic key
  `work-item-released-internal/<team>/<run>/<expected-version>/<visit>/<member>`. Both use
  `schema_version="1.0"`, `aggregate_type="STATUS_VISIT"`, semantic visit UUID, and
  `aggregate_version=expected_runtime_version + 1`.
- Freeze activity order by `(occurred_at, CapacityWorkOrderKey, event precedence, member UUID)`, with
  release before assignment at the same visit/instant. Assignment occurs at processed start,
  invalid/unavailable-owner release at start, and touch-completion release at processed end. Distinct
  assignment/release key prefixes guarantee that assign-then-complete in one segment yields two
  unique drafts. No activity is emitted for retained ownership, queue, or ordinary credit.
  `POST_SLICE_RUNTIME_VERSION_V1` remains the explicit temporary aggregate-version convention until
  later per-visit schema ownership; include it and both runtime versions in each canonical activity
  payload. The required catalogue `WORK_CREDITED` event belongs to the later full event-time/per-
  visit-version slice and is an explicit active-plan deferral: every credit is durable progress
  ground truth here, and temporary runtime-version activity is never emitted for ordinary credit.
  Set `projection_intents=()` and never call an adapter.
- Leave a touch-complete visit `OPEN`, `closed_at=None`, and at its unchanged status with
  `remaining_work_microseconds=0` and `member_id=None`. Task 8 must not inspect the next route step,
  sample a visit, claim a visit ordinal, evaluate dwell, or change any lifecycle.
- Queue increments only by Task 7's exact business subsegment for an eligible positive-touch visit
  denied labor by `CAPACITY`, `WIP_LIMIT`, or `CONTENTION`. A retained sticky owner with zero
  remaining effective labor is `CAPACITY` based on that owner even if another eligible member is
  idle. Only an unowned visit uses the closed no-labor, all-WIP-full, then higher-work-contention
  precedence. Never label or serialize this value as dwell, and never infer a lifecycle or readiness
  result from it.
- Validate the complete `AuthoritativeTickSliceCommit` before calling the committer. Call the
  committer exactly once, return its exact committed result plus the Task 7 result, propagate typed
  stale/semantic conflicts, and perform no hidden retry.

### Exact canonical evidence schemas and goldens

All five payload families use the exact object/nesting/null shape below. No listed key may be
omitted and no additional key is allowed. UUID strings are lower-case hyphenated `str(UUID)`; UTC
instants use `value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")`;
dates use `date.isoformat()`; enums use `.value`; ratios and microseconds are JSON integers; missing
semantic values are JSON `null`. Serialize with existing `canonical_json` (`sort_keys=True`, compact
separators, UTF-8, no NaN) and hash those exact bytes with lower-case SHA-256. Array order is policy
order and is never re-sorted by JSON encoding. Selection/progress `queue` is the shown object when
queue accrues and explicit `null` otherwise; progress `proficiency` and `labor_member_id` are both
explicit `null` exactly when labor is zero. Assignment `release_cause` is always `null`; release
requires one closed `OwnershipReleaseCause`. Every envelope has exact `schema_version="1.0"`.

The resolution golden also freezes the exact contributor union. `BLUEPRINT_INTERVAL` has the same
keys as the shown blueprint contributor but uses its interval kind/ID, exact configured starts/ends
and reason; runtime interval/provenance keys remain explicitly null/non-null under the cross-field
rules from Task 7.

```json
{
  "availability": {
    "business_date": "2026-08-11",
    "consumed_before_microseconds": 0,
    "contributors": [
      {
        "blueprint_canonical_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "configured_ends_at": null,
        "configured_starts_at": null,
        "contributor_id": "BLUEPRINT_DEFAULT",
        "fraction": {"denominator": 1, "numerator": 1},
        "kind": "BLUEPRINT_DEFAULT",
        "overlay_provenance_json": null,
        "overlay_provenance_sha256": null,
        "pre_fraction_cap_microseconds": 7200000000,
        "reason": null,
        "runtime_ends_at": null,
        "runtime_starts_at": null,
        "source": "BLUEPRINT"
      },
      {
        "blueprint_canonical_sha256": null,
        "configured_ends_at": null,
        "configured_starts_at": null,
        "contributor_id": "RUNTIME_OVERLAY:00000000-0000-0000-0000-000000000006",
        "fraction": {"denominator": 4503599627370496, "numerator": 4278419646001971},
        "kind": "RUNTIME_OVERLAY",
        "overlay_provenance_json": "{\"reason\":\"training\"}",
        "overlay_provenance_sha256": "ee7b12e98b741cffd12574f856dbd3af3ae4274cce3b32bde1ff13c9a5616d4b",
        "pre_fraction_cap_microseconds": 3600000003,
        "reason": "training",
        "runtime_ends_at": "2026-08-11T18:00:00.000000Z",
        "runtime_starts_at": "2026-08-11T16:00:00.000000Z",
        "source": "MANUAL"
      }
    ],
    "effective_cap_microseconds": 3420000003,
    "effective_fraction": {"denominator": 4503599627370496, "numerator": 4278419646001971},
    "member_id": "00000000-0000-0000-0000-000000000003",
    "pre_fraction_cap_microseconds": 3600000003,
    "remaining_before_microseconds": 3420000003
  },
  "policy": {"availability": "AVAILABILITY_OVERLAY_V1"},
  "run_id": "00000000-0000-0000-0000-000000000002",
  "runtime": {"expected_version": 7, "post_slice_version": 8},
  "team_id": "00000000-0000-0000-0000-000000000001"
}
```

```json
{
  "policy": {"allocator": "CAPACITY_ALLOCATOR_V1"},
  "run_id": "00000000-0000-0000-0000-000000000002",
  "runtime": {"expected_version": 7, "post_slice_version": 8},
  "selection": {
    "activity_key": "DEVELOP",
    "candidates": [
      {
        "active_wip": 2,
        "max_wip": 2,
        "member_id": "00000000-0000-0000-0000-000000000003",
        "proficiency": {"denominator": 1, "numerator": 1},
        "remaining_labor_microseconds": 3420000003
      }
    ],
    "labor_member_id": null,
    "owner_after_member_id": "00000000-0000-0000-0000-000000000003",
    "previous_member_id": "00000000-0000-0000-0000-000000000003",
    "queue": {
      "accrued_microseconds": 1800000000,
      "after_microseconds": 1800000000,
      "before_microseconds": 0,
      "reason": "CONTENTION"
    },
    "visit_id": "00000000-0000-0000-0000-000000000005",
    "work_order": {
      "entered_at": "2026-08-11T15:00:00.000000Z",
      "relative_rank": 11,
      "work_item_id": "00000000-0000-0000-0000-000000000004",
      "work_priority_order_index": 1
    }
  },
  "team_id": "00000000-0000-0000-0000-000000000001"
}
```

```json
{
  "policy": {"proficiency_credit": "PROFICIENCY_CREDIT_V1"},
  "progress": {
    "boundary_causes": ["REQUEST_END"],
    "business_date": "2026-08-11",
    "labor_member_id": null,
    "labor_microseconds": 0,
    "owner_after_member_id": "00000000-0000-0000-0000-000000000003",
    "owner_before_member_id": "00000000-0000-0000-0000-000000000003",
    "processed_interval": {
      "end": "2026-08-11T16:30:00.000000Z",
      "start": "2026-08-11T16:00:00.000000Z"
    },
    "proficiency": null,
    "queue": {
      "accrued_microseconds": 1800000000,
      "after_microseconds": 1800000000,
      "before_microseconds": 0,
      "reason": "CONTENTION"
    },
    "requested_interval": {
      "end": "2026-08-11T16:30:00.000000Z",
      "start": "2026-08-11T16:00:00.000000Z"
    },
    "touch": {
      "elapsed_after_microseconds": 0,
      "elapsed_before_microseconds": 0,
      "remaining_after_microseconds": 7200000000,
      "remaining_before_microseconds": 7200000000
    },
    "touch_credit_microseconds": 0,
    "visit_id": "00000000-0000-0000-0000-000000000005"
  },
  "run_id": "00000000-0000-0000-0000-000000000002",
  "runtime": {"expected_version": 7, "post_slice_version": 8},
  "team_id": "00000000-0000-0000-0000-000000000001"
}
```

Assignment and release use this same exact shape; only the shown event/occurrence values differ. The
assignment golden is first and the release golden is second:

```json
{
  "aggregate_version_convention": "POST_SLICE_RUNTIME_VERSION_V1",
  "event": {
    "event_type": "WORK_ITEM_ASSIGNED_INTERNAL",
    "member_id": "00000000-0000-0000-0000-000000000003",
    "outcome": "ASSIGNED",
    "release_cause": null,
    "visit_id": "00000000-0000-0000-0000-000000000005",
    "work_item_id": "00000000-0000-0000-0000-000000000004"
  },
  "occurred_at": "2026-08-11T16:00:00.000000Z",
  "policy": {"allocator": "CAPACITY_ALLOCATOR_V1"},
  "run_id": "00000000-0000-0000-0000-000000000002",
  "runtime": {"expected_version": 7, "post_slice_version": 8},
  "team_id": "00000000-0000-0000-0000-000000000001"
}
```

```json
{
  "aggregate_version_convention": "POST_SLICE_RUNTIME_VERSION_V1",
  "event": {
    "event_type": "WORK_ITEM_RELEASED_INTERNAL",
    "member_id": "00000000-0000-0000-0000-000000000003",
    "outcome": "RELEASED",
    "release_cause": "TOUCH_COMPLETE",
    "visit_id": "00000000-0000-0000-0000-000000000005",
    "work_item_id": "00000000-0000-0000-0000-000000000004"
  },
  "occurred_at": "2026-08-11T16:30:00.000000Z",
  "policy": {"allocator": "CAPACITY_ALLOCATOR_V1"},
  "run_id": "00000000-0000-0000-0000-000000000002",
  "runtime": {"expected_version": 7, "post_slice_version": 8},
  "team_id": "00000000-0000-0000-0000-000000000001"
}
```

`backend/tests/v2/fixtures/capacity_credit_v1_vectors.json` stores, for each named object above,
the literal compact canonical string and its fixed digest. The independent test parses the pretty
source object, recomputes with only stdlib `json.dumps(..., sort_keys=True, separators=(",", ":"),
ensure_ascii=False, allow_nan=False)` plus `hashlib.sha256`, and compares both literals without
importing any production serializer/evidence builder. The progress shape above is the `CONTENTION`
vector. The `CAPACITY` vector differs only by `queue.reason="CAPACITY"` and represents its retained
sticky owner. The unowned `WIP_LIMIT` vector uses `queue.reason="WIP_LIMIT"` and exact JSON null for
both owner IDs. This freezes all three queue-only variants independently and semantically.
The fixed digest table is:

| Vector | SHA-256 |
|---|---|
| `capacity_resolution_runtime_overlay` | `23d65b4d8038df71f9b0b14ddd2ec20e300f58401c96830965921fd7b85afa65` |
| `capacity_selection_contention` | `d3a6ec9a3cafeafbbd49aa3bb924660660b809fbea3b1fed14387569a596b795` |
| `capacity_progress_queue_only_capacity` | `d25f701dfbd0569fcfc36f6d324248786de4169822eb45bdfb010e287221b12a` |
| `capacity_progress_queue_only_wip_limit` | `1f858d12b75b280f597368fbbfbc65bad8f2c98fb43cc65769d6030122292566` |
| `capacity_progress_queue_only_contention` | `7ef1bfdc07cfe10d2972de182d2f2b80fbfbcf146b200825de2c228ea883f689` |
| `work_item_assigned_internal` | `cbc373a9f334fed9fba48c0c7448732ffdbbc3e556c3e5af8dc5eb2724141407` |
| `work_item_released_internal` | `9426a87cc6bcd50506be012bbfd1a90c11249bacfc2ce59a31335715a240b54a` |

### TDD steps and exact cases

- [ ] Write `test_capacity_credit.py` first with
  `test_ground_truth_envelopes_have_exact_schema_metadata_keys_and_order`. Use two members/two visits
  and assert `schema_version == "1.0"` for every draft; resolution drafts precede selection drafts,
  which precede progress drafts; and exact `(record_type, provenance_type)` pairs are
  `("CAPACITY_RESOLUTION", "AVAILABILITY_OVERLAY_V1")`,
  `("CAPACITY_SELECTION", "CAPACITY_ALLOCATOR_V1")`, and
  `("STATUS_VISIT_PROGRESS", "PROFICIENCY_CREDIT_V1")`.

  ```python
  assert [draft.semantic_key for draft in ground_truth] == [
      f"capacity-resolution/{team_id}/{run_id}/{expected_version}/{member_a_id}",
      f"capacity-resolution/{team_id}/{run_id}/{expected_version}/{member_b_id}",
      f"capacity-selection/{team_id}/{run_id}/{expected_version}/{visit_a_id}",
      f"capacity-selection/{team_id}/{run_id}/{expected_version}/{visit_b_id}",
      f"capacity-progress/{team_id}/{run_id}/{expected_version}/{visit_a_id}",
      f"capacity-progress/{team_id}/{run_id}/{expected_version}/{visit_b_id}",
  ]
  ```

  Assert each changed visit has exactly one progress key even when its labor member is null or an
  owner change and queue change occur together; unchanged visits have none.

- [ ] Add `test_assign_then_complete_emits_two_unique_catalogue_activity_drafts`. Assert exact event
  types `["WORK_ITEM_ASSIGNED_INTERNAL", "WORK_ITEM_RELEASED_INTERNAL"]`, exact distinct semantic
  keys
  `work-item-assigned-internal/<team>/<run>/<expected-version>/<visit>/<member>` and
  `work-item-released-internal/<team>/<run>/<expected-version>/<visit>/<member>`,
  `schema_version="1.0"`, `aggregate_type="STATUS_VISIT"`, the semantic visit UUID,
  `aggregate_version == expected_version + 1`, start/end occurrence instants, and empty projection.
  Assert assignment has `release_cause=null`, release has exact `TOUCH_COMPLETE`, and both match the
  frozen canonical hashes. Add `test_same_instant_replacement_orders_release_before_assignment` and
  use a responsibility-mismatched prior owner to assert two unique keys plus exact
  `RESPONSIBILITY_INELIGIBLE` release cause.
- [ ] Add `test_runtime_overlay_permutation_preserves_resolution_payload_hash_and_draft_order`.
  Reverse ORM/runtime overlay input, retain blueprint contributor first and semantic overlay UUID
  order, and assert identical canonical payload/hash/draft order with independently rounded blueprint cap
  `3_600_000_004`, exact `0.95` ratio
  `(4_278_419_646_001_971, 4_503_599_627_370_496)`, and effective cap `3_420_000_004`; reject
  evidence containing the reassociated value `3_420_000_003`. Add
  `test_resolution_evidence_preserves_runtime_integer_ceiling_without_rerounding` with blueprint
  `7_200_000_000`, runtime ceiling/pre-fraction cap `3_600_000_003`, and post-fraction cap
  `3_420_000_003`. Assert the typed contributor's complete authority fields survive unchanged.
- [ ] Add `test_capacity_credit_v1_independent_canonical_json_and_sha256_goldens` against all seven
  literal fixture vectors across the five payload families and exact hashes in this brief. Expected
  canonical strings/digests must be produced only by stdlib JSON/hashlib in the fixture/test side,
  never by importing the production serializer or evidence builder. Add
  `test_queue_only_progress_is_canonical_and_unique_for_each_denial_reason`, parameterized over
  `CAPACITY`, `WIP_LIMIT`, and `CONTENTION`, with zero labor/null member/null proficiency, exact
  before/after queue values, one `capacity-progress/.../<visit>` key, matching independent hash, and
  no duplicate progress draft.
- [ ] Parameterize `test_capacity_credit_command_rejects_invalid_coordinates_before_ports` over
  naive time, target before current runtime, wrong business date, beyond sprint end, foreign
  team/run/blueprint, and forged exact-value subclasses. Add
  `test_target_equal_to_current_raises_capacity_credit_target_reached_without_port_calls` asserting
  exact type/message and zero allocator/committer calls. Add named unit cases
  `test_capacity_credit_write_set_contains_only_visit_and_consumption_after_images`,
  `test_capacity_credit_claims_and_projection_are_empty`, and
  `test_capacity_credit_never_closes_or_transitions_visit` with exact unchanged collection/status/
  lifecycle assertions.
- [ ] Write reader tests before adapter code with concrete functions
  `test_authoritative_reader_uses_one_clean_session_and_returns_detached_complete_view`,
  `test_authoritative_reader_refreshes_cached_blueprint_runtime_and_state`,
  `test_authoritative_reader_observes_external_update_deletion_and_corruption`, and
  `test_authoritative_reader_rejects_dirty_new_or_deleted_caller_state_without_dml`. Parameterize
  missing/cross-team/run/corrupt authority, dispose/reopen, and assert no commit/rollback.
- [ ] Implement and deliver only `AuthoritativeStateView`, `load_authoritative`, the reader protocol,
  and SQLAlchemy read adapter; run `test_authoritative_state_reader.py` plus its mapper/architecture
  dependencies to GREEN. Stop at this explicit internal review checkpoint, record the reader/session
  evidence and an ignored SDD spec/code-review report, and resolve every finding before beginning the
  evidence/command builder or commit orchestration. This checkpoint changes no schema and is not a
  partial Task 8 commit.
- [ ] Write strict-fake then SQLite service cases
  `test_service_calls_allocator_and_committer_once_for_first_bounded_segment`,
  `test_service_preserves_four_field_order_in_selection_ground_truth`,
  `test_service_sticky_exhausted_owner_a_reports_capacity_with_idle_member_b`, and
  `test_service_lower_owned_visit_records_contention_progress_while_higher_visit_gets_credit`, and
  `test_service_touch_completion_releases_owner_but_keeps_visit_open`. Assert exact visit/
  consumption after-images, opposed item-UUID/entry-instant order, queue microseconds, and no work/
  sprint/status/sample mutation. The one-member/two-owned-visits service vector emits positive credit
  only for the higher order and one queue-only `CONTENTION` progress draft for the lower order.
- [ ] Add
  `test_response_loss_retry_below_target_commits_next_segment_with_new_version_and_keys`, asserting
  the second call starts at the committed runtime, uses `expected_version + 1`, and contains no prior
  credit/progress key; and
  `test_response_loss_retry_at_target_raises_target_reached_with_zero_writes`, asserting exact
  `CapacityCreditTargetReached` type/message and unchanged runtime/state/ledgers. Add
  `test_exhausted_at_start_retry_advances_each_committed_version_without_zero_length_slice`, which
  proves a zero-labor denial segment advances to a strictly later cursor and the same target then
  continues at the new version or reaches the typed no-write result. Add
  `test_processed_interval_gap_overlap_zero_length_reversal_or_overshoot_rejects_before_committer`,
  a non-working-current-time rejection, an exact-boundary-start vector, a two-reader stale-race test,
  disposed-engine continuation, and consecutive-segment restart tests. Parameterize
  `test_capacity_credit_failure_rolls_back_entire_slice(failure_point)` with
  `["runtime", "visit", "consumption", "activity_insert", "ground_truth",
  "activity_semantic_conflict", "final_flush", "commit"]`; every failure
  must leave runtime, Scrum state, counters, natural evaluations, and all ledgers unchanged. Retain
  the direct Task 6 conflicting-same-ledger-key/different-content rollback case and inject the
  activity semantic conflict with one existing same key/different payload; do not promise service-
  level replay or prior-response reconstruction.
- [ ] Add named architecture checks
  `test_capacity_credit_dependency_direction_and_session_boundary`,
  `test_capacity_credit_has_no_transition_or_external_imports`, and
  `test_capacity_credit_does_not_create_revision_016`. Spies must reject visit/sample factories,
  route/dwell/monitor/planner/lifecycle/scheduler/risk/dependency/Jira/OpenAI/projection adapters,
  v1 engine, wall-clock, random UUID, hidden loop, or retry calls.
- [ ] Run the focused command from `backend/` and retain the expected non-zero output caused only by
  missing Task 8 modules/interfaces:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_capacity_credit.py tests/v2/integration/test_authoritative_state_reader.py tests/v2/integration/test_capacity_credit_service.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T08/red.txt
  ```

- [ ] After the reader checkpoint is accepted, implement the command/evidence/commit half with private
  frozen `_CommitContext` and `_EvidenceContext` bundles so helpers stay within three arguments and
  30 lines. Use this exact orchestration shape; split payload families into single-purpose helpers:

  ```python
  def _build_live_slice(context, allocation):
      return TickSliceCommit(
          commit_id=context.commit_id,
          team_id=context.team_id,
          run_id=context.run_id,
          expected_runtime_version=context.expected_version,
          runtime_after=_runtime_advance(context, allocation),
          activity=_activity_drafts(context, allocation.ownership_changes),
          ground_truth=(*_resolution_drafts(context, allocation.availability),
                        *_selection_drafts(context, allocation.ownership),
                        *_progress_drafts(context, allocation)),
          projection_intents=(),
          recorded_at=context.recorded_at,
      )

  def _build_commit(context, allocation):
      live_slice = _build_live_slice(_evidence_context(context, allocation), allocation)
      write_set = _write_set_from_after_images(allocation)
      return AuthoritativeTickSliceCommit(
          live_slice=live_slice,
          state=write_set,
          counter_claims=(),
          natural_decision_claims=(),
      )

  def commit(self, command):
      view = self._reader.get_authoritative_view(command.team_id)
      context = _validate_target_and_view(command, view)
      eligible_ids = _eligible_visit_ids(context)
      allocation = allocate_capacity(_allocation_request(context, eligible_ids))
      _validate_strictly_positive_contiguous_segment(context, allocation)
      committed = self._committer.commit_authoritative_slice(_build_commit(context, allocation))
      return CommittedCapacityCredit(allocation, committed)
  ```

  `_validate_target_and_view` owns the exact before/equal/after target branching and builds no session
  or draft. `_eligible_visit_ids` retains the four-field order. `_resolution_drafts`,
  `_selection_drafts`, `_progress_drafts`, and `_activity_drafts` serialize only Task 7 typed traces
  with the frozen schemas/keys/order above; `_progress_drafts` joins each changed after-image to its
  selection/credit/queue trace and emits exactly one visit record. `_write_set_from_after_images`
  includes only visits/consumption, while `_runtime_advance` changes only UTC cursor/version. Validate
  the completed immutable Task 6 command before the single port call. Keep SQLAlchemy out of domain/
  application modules and do not reconstruct boundary, release, availability, or denial causes.
- [ ] Rerun the identical command to GREEN and save `green.txt`; refactor only while it remains
  GREEN. Run an AST scan and split helpers before any function exceeds the project limits.
- [ ] Run Task 1 through Task 7 focused selections, all `tests/v2 -q`, full safe `tests -q`, Ruff,
  cold direct/lazy import permutations, architecture/static scans, and exact warning accounting with
  `set -o pipefail`; retain outputs under `evidence/v2/M1-T08/`.
- [ ] Prove Alembic reports sole head 015, empty branches, and linear history; compare migration and
  ORM schema files byte-for-byte with the Task 7 base and retain a no-revision-016/no-schema-diff
  artifact.
- [ ] Record the reader checkpoint, exact command/payload schemas and independent golden digests,
  contributor/boundary/release traces, rollback/response-loss/target-reached/restart matrix, explicit
  no-receipt and deferred-`WORK_CREDITED` limitations, no-transition/no-adapter proofs, test counts,
  warnings, environment, and commands in `evidence/v2/M1-T08/README.md`.
- [ ] Complete mandatory documentation, mark Task 8 complete only after both review stages are clean,
  leave this plan complete but M1 in progress for separately planned flow/planning/lifecycle work,
  inspect the staged diff, and commit exactly:

  ```bash
  git commit -m "feat(v2): commit capacity credit slices"
  ```

**Done condition:** One application command reads a coherent authoritative view, deterministically
selects existing active-sprint touch visits, and commits one Task 7 segment's runtime/state,
assignment/release activity, and resolution/selection/visit-progress ground truth through Task 6. Queue
advances only for exact eligible-denial business subsegments. After response loss, the same desired
target either commits only the next versioned segment or raises `CapacityCreditTargetReached` with
zero writes at the target; it never duplicates prior credit/progress key and never reconstructs the prior
response, and no committed runtime version exists without strictly positive UTC cursor progress.
Visits remain open; dwell/status/lifecycle/planning/scheduler/risk/Jira/projection/schema
behavior remains absent; focused, regression, atomicity, restart, static, evidence, documentation,
and review gates are clean under the exact Task 8 commit.

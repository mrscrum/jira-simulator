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
- Capacity composition is not algebraically reassociable. Convert each configured nominal/override
  and runtime-ceiling hours float independently with `hours_to_microseconds`, take the minimum of
  those already-rounded integer caps, then apply the selected exact availability-fraction ratio to
  that integer and half-even once. Never multiply hours by fraction first or combine their ratios.
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
  minimum configured cap and all non-null runtime ceilings. Resolve this composition in exactly
  three stages: convert every hours contributor independently with `hours_to_microseconds` using its
  exact binary ratio and one half-even rounding; take the integer minimum; multiply that integer by
  the selected exact fraction ratio and half-even once. Reassociation is forbidden. The binding
  golden is `hours=1.000000001 -> 3_600_000_004` microseconds, followed by
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
  queue reason/accrual, and before/after touch balance required to serialize deterministic
  calibration ground truth. Contributor order is blueprint default or the active blueprint interval
  first, followed by runtime overlays in ascending semantic overlay UUID order; input/row order never
  changes the trace.

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
  subclasses, non-finite/negative values, and overflow. Apply only the staged rounding contract
  below; reassociation is a contract violation.
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
    contributor_id: str
    fraction_numerator: int
    fraction_denominator: int
    pre_fraction_cap_microseconds: int | None


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
Tasks 3-6. `AvailabilityContributor.contributor_id` uses stable canonical strings:
`BLUEPRINT_DEFAULT` or
`BLUEPRINT_INTERVAL:<zero-based-index>` first, then every
`RUNTIME_OVERLAY:<semantic-overlay-uuid>` in ascending semantic overlay UUID order. Each contributor
retains its exact fraction ratio and independently rounded optional hours cap so Task 8 never reads
configuration again to build evidence. Queue evidence uses only the three closed reasons above and
records business microseconds; no field or payload calls queue time dwell. Ownership changes are
exact events:
invalid/unavailable prior-owner release and new assignment occur at the processed start; release
caused by touch completion occurs at the processed end. For the same visit/instant, release sorts
before assignment. A newly assigned owner who completes touch within the segment therefore emits
assignment at start and release at end while `owner_after_member_id` is `None`.

### Self-contained shared capacity-credit contract and binding mechanics

- Build `BusinessCalendar` only from `blueprint.team.timezone` and `blueprint.calendar`. Validate the
  complete state against that exact blueprint before selecting anything. The request interval is
  aware UTC, positive, inside the authenticated holiday horizon, and is shortened rather than
  crossed at the first local business-date/workday, configured/runtime availability,
  daily-capacity-exhaustion, or touch-completion boundary. It is half-open `[start, end)`, belongs to
  one team business date, and represents only one common segment.
- Produce one `AvailabilityResolution` for every persisted `MemberIdentity`, in blueprint-index
  order. The active configured interval or default supplies fraction/cap; every active runtime
  overlay may only lower them. Convert the configured nominal/override hours and each non-null
  runtime ceiling independently through `hours_to_microseconds`; each conversion uses the float's
  exact binary ratio and half-even once. Take the minimum of those integer caps. Select the minimum
  availability fraction by exact ratio comparison, multiply the selected ratio by that integer cap,
  half-even once, then subtract exact persisted business-date consumption. Never pre-multiply an
  hours float by a fraction or combine/reassociate their ratios. The mandatory golden is
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
  in that same order.
- WIP is the complete run-snapshot count of open positive-touch visits owned by a member. New
  assignment requires `active_wip < max_concurrent_wip`; compare candidate WIP fractions by integer
  cross-multiplication, followed by proficiency descending, remaining labor descending, and semantic
  member UUID. Never use float division or input order.
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
- For every eligible positive-touch visit receiving zero labor over positive business time, apply
  retained-sticky `CAPACITY` first. For an unowned visit only, use `CAPACITY` when no
  responsibility-eligible/effectively-available member has labor, `WIP_LIMIT` when labor exists but
  all candidates are WIP-full, then `CONTENTION` when labor/WIP space exist but selected members
  serve higher-ordered owned work. Do not accrue queue for an ineligible/out-of-scope/closed/zero-
  touch/already-complete visit, and never change pause or dwell.
- Return only changed visit and consumption after-images, ordered by semantic identity, plus complete
  availability/selection/change/credit/queue traces. Retain every four-field work key, candidate
  WIP/proficiency/capacity input, ordered contributor, prior consumption, labor/credit, queue reason,
  and before/after balance required by Task 8 ground truth. The result contains no draft, ORM value,
  callable, fractional residue, implicit clock, or hidden second segment.

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
  byte-identical results.

  ```python
  cap = hours_to_microseconds(1.000000001, "daily capacity")
  assert cap == 3_600_000_004
  assert multiply_microseconds(cap, 0.95, "availability fraction") == 3_420_000_004
  assert multiply_microseconds(cap, 0.95, "availability fraction") != 3_420_000_003
  ```

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
  `test_one_member_credits_only_first_owned_visit`,
  `test_two_members_credit_in_parallel`, `test_touch_completion_shortens_common_segment`, and
  `test_zero_or_non_business_elapsed_never_accrues_queue` with exact before/after microsecond
  balances and assignment/release instants.
- [ ] Parameterize `test_allocator_segment_boundaries` across configured/runtime boundaries, daily
  exhaustion, workday/date/DST boundaries, touch completion, and non-working intervals. Add named
  validation/immutability tests for duplicate/foreign/missing eligible IDs, unsafe clocks,
  ineligible/zero-touch/closed/completed visits, input permutations, direct/replacement/subclass/
  mutation/reconstruction attacks, and unchanged pause/dwell/lifecycle/status/sample/work/sprint/
  counter/natural collections.
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

- The requested/processed interval is aware UTC and half-open `[start, end)`, belongs to one team
  business date and active sprint, and is shortened at the first workday, configured/runtime
  availability, daily-capacity-exhaustion, or touch-completion boundary. Commit exactly Task 7's one
  returned segment and never loop to the original target inside the transaction.
- `AVAILABILITY_OVERLAY_V1` converts every nominal/override/ceiling hours float independently with
  `hours_to_microseconds` using exact binary-ratio half-even rounding, takes the minimum integer cap,
  then multiplies that integer by the selected exact minimum fraction and half-even once. Never
  combine or reassociate ratios. The golden is `1.000000001 hours -> 3_600_000_004` microseconds,
  then `fraction=0.95 -> 3_420_000_004`; `3_420_000_003` is forbidden. Contributor order is the
  blueprint default/active interval first, then runtime overlays by ascending semantic overlay UUID.
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
- Preserve Task 7's complete availability, four-field selection, ownership-change, labor/credit,
  queue, contributor, and before/after traces without reinterpretation so Task 8 can serialize exact
  deterministic evidence.

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
  visits with remaining work. Order IDs only by Task 7's retained four fields:
  `WORK_PRIORITY_ORDER` index, relative rank, visit entry instant, and semantic work-item UUID.
  Neither `SimulatorRank` nor visit UUID participates.
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
  `capacity-credit-commit/<team-id>/<run-id>/<expected-runtime-version>`. Every activity and ground-
  truth `DraftEnvelope` uses exact `schema_version="1.0"`; semantic identities contain no timestamp,
  database/ledger position, insertion order, or random UUID.
- Create one resolution ground-truth draft per availability result with exact semantic key
  `capacity-resolution/<team-id>/<run-id>/<expected-runtime-version>/<member-id>` and exact metadata
  `record_type="CAPACITY_RESOLUTION"`, `provenance_type="AVAILABILITY_OVERLAY_V1"`. Payloads contain
  the blueprint default/active interval contributor first, runtime contributors in ascending
  semantic overlay UUID order, every independently rounded hours cap, selected exact fraction ratio,
  effective cap, prior consumption, and remaining labor.
- Create one selection ground-truth draft per ownership/queue decision with exact semantic key
  `capacity-selection/<team-id>/<run-id>/<expected-runtime-version>/<visit-id>` and exact metadata
  `record_type="CAPACITY_SELECTION"`, `provenance_type="CAPACITY_ALLOCATOR_V1"`. Payloads contain
  `work_priority_order_index`, `relative_rank`, `entered_at`, and `work_item_id` from
  `CapacityWorkOrderKey`, every ordered WIP/proficiency/capacity candidate, previous/labor/after
  owner, and queue reason/accrual.
- Create one progress ground-truth draft per credit subsegment with exact semantic key
  `capacity-credit/<team-id>/<run-id>/<expected-runtime-version>/<visit-id>/<member-id>` and exact
  metadata `record_type="STATUS_VISIT_PROGRESS"`, `provenance_type="PROFICIENCY_CREDIT_V1"`.
  Payloads contain requested/processed UTC intervals, business date, labor debit, effective credit,
  exact proficiency ratio, and before/after touch and queue balances. Every ground-truth payload
  contains expected and proposed post-slice runtime versions; `occurred_at` is the processed end and
  ledger `recorded_at` is the command value.
- Freeze `live_slice.ground_truth` order as all resolution drafts in blueprint member-index order,
  then all selection drafts by `CapacityWorkOrderKey`, then all progress drafts by
  `(CapacityWorkOrderKey, member UUID)`. Task 7 contributor/candidate order is retained byte-for-byte;
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
  payload. Set `projection_intents=()` and never call an adapter.
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
      f"capacity-credit/{team_id}/{run_id}/{expected_version}/{visit_a_id}/{member_a_id}",
  ]
  ```

- [ ] Add `test_assign_then_complete_emits_two_unique_catalogue_activity_drafts`. Assert exact event
  types `["WORK_ITEM_ASSIGNED_INTERNAL", "WORK_ITEM_RELEASED_INTERNAL"]`, exact distinct semantic
  keys
  `work-item-assigned-internal/<team>/<run>/<expected-version>/<visit>/<member>` and
  `work-item-released-internal/<team>/<run>/<expected-version>/<visit>/<member>`,
  `schema_version="1.0"`, `aggregate_type="STATUS_VISIT"`, the semantic visit UUID,
  `aggregate_version == expected_version + 1`, start/end occurrence instants, and empty projection.
  Add `test_same_instant_replacement_orders_release_before_assignment` and assert two unique keys.
- [ ] Add `test_runtime_overlay_permutation_preserves_resolution_payload_hash_and_draft_order`.
  Reverse ORM/runtime overlay input, retain blueprint contributor first and semantic overlay UUID
  order, and assert identical canonical payload/hash/draft order with independently rounded cap
  `3_600_000_004`, exact `0.95` ratio
  `(4_278_419_646_001_971, 4_503_599_627_370_496)`, and effective cap `3_420_000_004`; reject
  evidence containing the reassociated value `3_420_000_003`.
- [ ] Parameterize `test_capacity_credit_command_rejects_invalid_coordinates_before_ports` over
  naive time, non-later target, wrong business date, beyond sprint end, foreign team/run/blueprint,
  and forged exact-value subclasses. Add named unit cases
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
- [ ] Write strict-fake then SQLite service cases
  `test_service_calls_allocator_and_committer_once_for_first_bounded_segment`,
  `test_service_preserves_four_field_order_in_selection_ground_truth`,
  `test_service_sticky_exhausted_owner_a_reports_capacity_with_idle_member_b`, and
  `test_service_touch_completion_releases_owner_but_keeps_visit_open`. Assert exact visit/
  consumption after-images, opposed item-UUID/entry-instant order, queue microseconds, and no work/
  sprint/status/sample mutation.
- [ ] Add `test_identical_capacity_credit_command_replays_exact_evidence_without_duplicates`, a
  two-reader stale-race test, response-loss/reload, disposed-engine continuation, and consecutive-
  segment restart tests. Parameterize
  `test_capacity_credit_failure_rolls_back_entire_slice(failure_point)` with
  `["runtime", "visit", "consumption", "ground_truth", "final_flush", "commit"]`; every failure
  must leave runtime, Scrum state, counters, natural evaluations, and all ledgers unchanged. Add a
  conflicting-same-key/different-content rollback case.
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

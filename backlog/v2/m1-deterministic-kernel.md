# M1 Deterministic Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the pure deterministic decision, bounded timing-sample, and dual-clock calendar contracts that later work/sprint/status-visit persistence and the live Scrum flow can consume without redesigning their stored provenance or clock fields.

**Architecture:** Keep this slice inside the additive v2 domain. Task 3 derives stable semantic RNG identities and stateless HMAC unit draws from already-persisted blueprint/team/run inputs, then applies explicit draws to bounded dwell/touch samplers. Task 4 consumes the resolved team timezone/calendar/sprint cadence and provides exact UTC/business-time arithmetic. Neither task allocates persistence occurrences, changes the schema, advances a runtime, calls Jira/OpenAI, or imports the v1 engine.

**Tech Stack:** Python 3.12 standard library (`dataclasses`, `datetime`, `enum`, `hashlib`, `hmac`, `json`, `math`, `unicodedata`, `uuid`, `zoneinfo`), existing v2 domain contracts, pytest, Ruff.

## Authority and Global Constraints

- `docs/v2/high-level-plan.md` remains the product authority after later explicit instructions and `AGENTS.md`. Detailed values below selectively freeze implementation choices from `docs/v2/decisions.md`, `docs/v2/architecture.md`, `docs/v2/contracts/starter-catalog.md`, and the Stage 1 reference; those historical files do not override the high-level plan.
- Follow strict RED -> GREEN -> REFACTOR. Write every behavior test before its production behavior, run the stated RED command with pipeline failure propagation, retain the real failure, make the minimum implementation pass the identical test selection, and refactor only while GREEN.
- Apply the installed Superpowers TDD skill and project Python clean-code skills. Public interfaces are fully typed; functions are at most 30 lines and accept at most three arguments; dependencies are injected; modules have one responsibility.
- Preserve the reviewed Task 1/Task 2 persistence spine and `CANONICAL_JSON_V1`. Do not recompute, migrate, or reinterpret stored blueprint hashes, team/run IDs, canonical payload bytes, or ledger identities.
- Semantic IDs use UUIDv5 namespace `0f896a61-4777-57d8-9e81-62c5c4ab2b7f`. Never use Python `hash()`, `random`, random UUIDs, database/autoincrement IDs, timestamps, scheduler order, or insertion order as replay identity.
- All instant inputs reject naive values and normalize aware values to UTC. Team calendar behavior uses the resolved IANA timezone, ordered work interval, weekdays, explicit holidays, and fixed local-cadence anchor.
- These two tasks add no Alembic revision or ORM mapping. Revision `014` remains the sole head. Work/sprint/status-visit persistence and any migration `015` belong to a later reviewed plan.
- RNG occurrence values are explicit inputs only. Do not add an occurrence allocator/counter, infer an occurrence from a ledger count, or mutate/persist an occurrence in this slice. Commit-only allocation belongs with the future authoritative state transaction.
- No v1 model/schema/route/engine/integration behavior changes. Do not import or route through `app.engine.precompute`, scheduled events, the v1 scheduler, Jira queue/client, OpenAI, or any external adapter.
- Work is local only: no live Jira credentials/calls, deploy, push, production mutation, UAT claim, or M1 completion.
- Finish each implementation task by updating its checklist marker and evidence plus `README.md`, `changelog.md`, `assumptions.md`, and `agent_instruction.md`. Keep documentation limited to implemented current state.

---

Status: IN PROGRESS

## Task Checklist

- [ ] Task 3 — Add exact deterministic HMAC-U53 decisions and bounded dwell/touch sampling
- [ ] Task 4 — Add dual-clock, DST-safe business-calendar primitives

## Deferred Non-Blocking Validation Hardening

`DraftEnvelope` currently rejects a self-referential Python mapping/list before any session or state mutation, but its recursive JSON-key guard raises `RecursionError` rather than the normal invalid-JSON `ValueError`. This reviewed Minor is outside Tasks 3 and 4 because neither task touches the live-slice payload boundary. Retain it for a dedicated validation-hardening micro-fix before an API accepts arbitrary v2 payload objects; do not fold it into deterministic RNG or calendar code.

## Task 3: Add exact deterministic HMAC-U53 decisions and bounded dwell/touch sampling

**Goal:** Given the persisted root seed and stable semantic identities, produce cross-process/order-independent `HMAC_SHA256_U53_V1` draws and apply explicit unit draws to the approved bounded full-dwell and touch-work samplers without persistence or hidden mutable RNG state.

**Dependency:** Start from the reviewed persistence-spine head with Alembic `014`. This task consumes existing `canonical_json`, `semantic_uuid`, `ResolvedTeamBlueprint`, `TimingBlueprint`, and `TimingEntry` contracts but does not modify their persisted representation.

**Inputs:** The exact persisted root seed, stored canonical-final-blueprint SHA-256, stable team/run/entity UUIDs or catalog key, one closed decision type, explicit non-negative occurrence and draw index, and one validated timing entry's five dwell anchors plus touch bounds.

**Outputs:** Typed semantic RNG identity helpers, a closed creation-kind/decision enum, an immutable decision coordinate/provenance result, one stateless HMAC-U53 stream, and pure bounded dwell/touch sampling results suitable for later ground-truth serialization.

**Public interfaces:**

- `CreationKind(StrEnum)` and `DecisionType(StrEnum)` are the closed exact enums below.
- `team_rng_id(blueprint_sha256: str) -> UUID`, `run_rng_id(team_id: UUID, ordinal: int) -> UUID`, `member_rng_id(team_id: UUID, index: int) -> UUID`, `sprint_rng_id(team_id: UUID, ordinal: int) -> UUID`, `item_rng_id(team_id: UUID, creation_kind: CreationKind, sequence: int) -> UUID`, `visit_rng_id(item_id: UUID, ordinal: int) -> UUID`, `dependency_rng_id(visit_id: UUID, ordinal: int) -> UUID`, and `rework_rng_id(item_id: UUID, ordinal: int) -> UUID` expose only the approved paths.
- Frozen `DecisionOccurrence(entity_id: UUID | str, decision_type: DecisionType, occurrence: int)` groups the semantic coordinate. `DeterministicRandomStream(root_seed: str, team_id: UUID, run_id: UUID).draw(decision: DecisionOccurrence, draw_index: int = 0) -> UniformDraw` is stateless and requires an explicit occurrence.
- Frozen `UniformDraw` exposes `algorithm`, `decision`, `draw_index`, `canonical_message`, `hmac_sha256`, `u53_integer`, and `unit_value` with exact validated types.
- Frozen `DwellAnchors` exposes `minimum`, `p25`, `p50`, `p99`, and `maximum`; frozen `TouchBounds` exposes `minimum` and `maximum`; frozen `DurationSample` exposes the input draw and sampled hours without claiming persistence.
- `dwell_anchors(entry: TimingEntry) -> DwellAnchors`, `touch_bounds(entry: TimingEntry) -> TouchBounds`, `sample_dwell(anchors: DwellAnchors, unit_draw: float) -> DurationSample`, and `sample_touch(bounds: TouchBounds, unit_draw: float) -> DurationSample` are the only sampling operations.

**Files:**

- Create `backend/app/v2/domain/deterministic_rng.py` for semantic RNG path helpers, exact enums, decision validation/canonical message bytes, root-key derivation, HMAC conversion, and immutable draw provenance.
- Create `backend/app/v2/domain/sampling.py` for validated dwell anchors/touch bounds and the two explicit-unit-draw samplers only.
- Modify `backend/app/v2/domain/__init__.py` only for additive public exports.
- Create `backend/tests/v2/unit/test_deterministic_rng.py`.
- Create `backend/tests/v2/unit/test_sampling.py`.
- Create `backend/tests/v2/fixtures/hmac_sha256_u53_v1_vectors.json` with literal canonical-message, digest, 53-bit integer, and unit-draw results computed independently of production functions.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` only to enforce the new pure-domain dependency boundary and forbidden identity/randomness sources.
- Create `evidence/v2/M1-T03/README.md` plus command-output evidence during implementation.
- Do not create/modify Alembic, ORM, repository, unit-of-work, API, scheduler, engine, Jira/OpenAI, frontend, or deployment files.

**Exact semantic identity contract:**

- All UUID segments use lower-case hyphenated RFC 4122 text.
- Team: `team/<canonical-final-blueprint-sha256>`.
- Run: `run/<team-rng-uuid>/<zero-based-run-ordinal>`.
- Member: `member/<team-rng-uuid>/<zero-based-canonical-blueprint-index>`.
- Sprint: `sprint/<team-rng-uuid>/<zero-based-created-sprint-ordinal>`.
- Item: `item/<team-rng-uuid>/<creation-kind>/<zero-based-kind-sequence>`.
- Visit: `visit/<item-rng-uuid>/<zero-based-visit-ordinal>`.
- Dependency: `dependency/<visit-rng-uuid>/<zero-based-dependency-ordinal>`.
- Rework: `rework/<item-rng-uuid>/<zero-based-rework-ordinal>`.
- `creation-kind` is exactly one of `INITIAL_BACKLOG`, `SCRUM_REPLENISHMENT`, `KANBAN_ARRIVAL`, `AGENT_CREATED`, or `JIRA_IMPORTED`; its sequence is scoped to team plus kind.
- Member identity uses persisted final-blueprint array position. The helpers validate a 64-character lower-case hexadecimal blueprint digest, exact enum membership, true non-negative integers (not booleans), and UUID inputs before derivation.
- For the existing Task 1 aggregate, `team_rng_id(blueprint_sha256)` and `run_rng_id(team_id, 0)` must equal the already-persisted team/run semantic IDs; no parallel database identity is created.

**Exact decision contract:**

- Algorithm ID is exactly `HMAC_SHA256_U53_V1`.
- Decision types are exactly: `BACKLOG_ISSUE_TYPE`, `BACKLOG_STORY_POINTS`, `BACKLOG_PRIORITY`, `ITEM_DESCRIPTION_QUALITY`, `ITEM_LATENT_COMPLEXITY`, `STATUS_DWELL`, `STATUS_TOUCH`, `SCRUM_CAPACITY_TARGET`, `RISK_EXTERNAL_DEPENDENCY_OUTCOME`, `RISK_EXTERNAL_DEPENDENCY_DURATION`, `RISK_CANCELLATION_OUTCOME`, `RISK_REVIEW_REJECTION_OUTCOME`, `RISK_REWORK_DURATION`, `RISK_MEMBER_UNAVAILABLE_OUTCOME`, `RISK_MEMBER_UNAVAILABLE_DURATION`, `FORCED_REWORK_DURATION`, `KANBAN_ARRIVAL_GAP`, and `KANBAN_CLASS_OF_SERVICE`. Adding/renaming a value requires a new algorithm version.
- Normalize the persisted root seed with Unicode NFC, encode UTF-8, and SHA-256 it once; the 32 digest bytes are the HMAC key. Do not replace or persist a normalized seed silently.
- The canonical decision object has exactly `algorithm`, `team_id`, `run_id`, `entity_id`, `decision_type`, `occurrence`, and `draw_index`. UUID values use lower-case hyphenated text. It is encoded as RFC 8785 canonical UTF-8 JSON with no whitespace. For this closed string/integer schema, an implementation may reuse a proven byte-equivalent compact/sorted encoder but must not change `CANONICAL_JSON_V1` or use it to rehash persisted blueprints.
- Calculate HMAC-SHA-256 over those exact bytes. Interpret the first eight digest bytes as unsigned big-endian, discard the low 11 bits, and divide the remaining integer by `2^53`. The generator returns `u` in `[0,1)`; it never emits `1`.
- `entity_id` is the stable semantic UUID or approved catalog key. `occurrence` and `draw_index` are explicit true non-negative integers. A frozen result retains algorithm, coordinate, canonical message, full lower-case HMAC digest, high-53-bit integer, and `u` without exposing mutable state.
- Backlog/item draws use the item semantic UUID and occurrence `0`; dwell/touch and visit-triggered natural risks use the visit semantic UUID and occurrence `0`; sprint capacity uses the sprint semantic UUID and occurrence `0`. Cancellation/member-unavailability eligibility additionally keys by business date while HMAC uses the item/member UUID and explicit zero-based committed eligible-evaluation occurrence. Forced rework uses the review-visit UUID and explicit committed forced ordinal. Kanban arrival gap uses the run UUID and explicit arrival ordinal; Kanban class uses the created item UUID and occurrence `0`.
- Disabled, ineligible, forced, duplicate, or rolled-back natural evaluations must not consume an occurrence, but this task only validates caller-supplied coordinates; it does not implement that state transition.

**Exact sampling contract:**

- Full-status dwell anchors are `(u=0, minimum)`, `(u=.25, p25)`, `(u=.50, p50)`, `(u=.99, p99)`, and `(u=1, maximum)`.
- At an exact anchor probability, return the configured anchor. Between adjacent anchors, interpolate linearly in `log1p(hours)` and transform with `expm1`. Results are monotone and bounded; five zero anchors return zero.
- Reject a boolean/non-number/non-finite unit draw, a draw outside `[0,1]`, or any negative, non-finite, or unordered dwell anchor. Equal adjacent anchors are valid.
- Touch uses exact `LINEAR_UNIFORM_TOUCH_V1`: for finite ordered bounds `a <= b` and explicit `u` in `[0,1]`, return `a + (b - a) * u`; exact `u=0` returns `a`, exact `u=1` returns `b`, and `a=b` returns that bound.
- Samplers accept explicit `u=1` for endpoint tests even though HMAC-U53 does not emit it. They import no RNG and consume no occurrence. Results retain the supplied bounds/anchors, draw, and sampled hours; the existing timing profile/version/algorithm remains the provenance source and is not rewritten.

**RED command and required failures:**

- [ ] Write the fixture/tests first. From `backend/`, run exactly:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/red.txt
  ```

- [ ] Confirm the command exits non-zero because the new domain modules/interfaces are absent, not because fixtures, imports, or assertions are malformed.
- [ ] Freeze literal vectors covering canonical message bytes, full HMAC digest, high-53-bit integer, and `u`; include composed/decomposed Unicode seeds that normalize to the same key and a distinct seed that does not.
- [ ] Prove every path with fixed UUID literals, exact lower-case formatting, zero and positive ordinals, each creation kind, malformed digest, wrong enum/string, negative/bool ordinal, and separation from current database IDs/order.
- [ ] Prove fixed draw replay in a fresh subprocess and equality across reversed/interleaved call order and unrelated draws. AST/import tests reject Python `hash`, `random`, `uuid4`, database/ORM imports, current time, and mutable global counters.
- [ ] Prove dwell exact anchors/endpoints, dense monotonic/bounded values across every segment, all-zero/equal anchors, very small/large finite values, and every invalid draw/anchor category.
- [ ] Prove touch exact endpoints/formula/equal bounds and every invalid draw/bounds category. Exercise every timing cell in `resolved_scrum_blueprint.json` through both samplers without changing the fixture.

**Implementation steps:**

- [ ] Implement the enums and short validation helpers, then the eight exact UUIDv5 path helpers using the existing fixed namespace.
- [ ] Implement the immutable decision input/result contracts and stateless stream. Keep canonical-message construction, seed-key derivation, HMAC, and U53 conversion in separately testable short functions.
- [ ] Implement validated dwell/touch value objects and pure samplers; use endpoint branches for exact configured anchors/bounds and `log1p`/`expm1` only for interior dwell interpolation.
- [ ] Add only the approved exports and dependency-boundary assertions. Do not create persistence state, occurrence allocation, generic arbitrary-path APIs, stochastic defaults, or external dependencies.
- [ ] Run the identical test selection after implementation, retaining GREEN with:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/green.txt
  ```

- [ ] Refactor only while the same focused selection remains green and every touched/new function remains within the project limits.

**Verification, documentation, and evidence:**

- [ ] Run the focused GREEN selection, `tests/v2 -q`, the full safe backend `tests -q`, Ruff `../.venv/bin/python -B -m ruff check --no-cache .`, Alembic `heads --verbose`, `branches --verbose`, and `history`, an AST touched-function scan, and `git diff --check`; retain exact commands/output under `evidence/v2/M1-T03/`.
- [ ] Record Python/dependency versions, RED reason, golden-vector provenance, subprocess/order-independence proof, sampler boundary/invariant results, full regression counts/warnings, sole `014` head, no migration, and no external call in `evidence/v2/M1-T03/README.md` without secrets.
- [ ] Update mandatory current-state documents and this plan's checklist. Do not mark Task 4 or M1 complete and do not claim persistence occurrence allocation, live flow, Jira, deployment, or UAT.
- [ ] Inspect/stage only Task 3 files and commit exactly `feat(v2): add deterministic decision sampling` before Task 4 begins.

**Done condition:** Independent literal vectors and subprocess/order tests prove stable UUIDv5/HMAC-U53 results; bounded dwell/touch samples satisfy every endpoint, monotonicity, finite/order, and starter-fixture invariant; no persistence/schema/external boundary changed; Alembic remains sole head `014`; focused/v2/full tests and Ruff pass with truthful evidence and the exact Task 3 commit.

## Task 4: Add dual-clock, DST-safe business-calendar primitives

**Goal:** Provide pure, deterministic UTC/calendar/business-time arithmetic for one resolved team calendar and fixed local Scrum cadence, including explicit holidays and `US_FEDERAL_V1` horizon materialization, without altering stored sprint boundaries or persisting policy revisions.

**Dependency:** Begin only from the reviewed Task 3 commit. Task 4 does not consume Task 3 randomness at runtime, but the separate review/commit order keeps each kernel boundary context-sized and independently rejectable.

**Inputs:** Aware instants, a bounded UTC interval, a non-negative business duration, `TeamBlueprintTeam.timezone`, `CalendarBlueprint` ordered weekdays/local start/end/profile/version/horizon/holidays, and the fixed aware `ScrumBlueprint.first_boundary` plus positive `cadence_days`.

**Outputs:** Frozen interval/result/request contracts; one immutable business calendar constructed from the resolved blueprint; exact calendar/business elapsed time, forward business-time addition, next working instant, working interval/business date/end; fixed local-cadence boundary arithmetic; and pure versioned US federal holiday/horizon results for later policy persistence.

**Public interfaces:**

- Frozen `UtcInterval(start: datetime, end: datetime)`, `DualElapsed(calendar: timedelta, business: timedelta)`, `BusinessTimeAddition(start: datetime, duration: timedelta)`, `CadenceRule(anchor: datetime, cadence_days: int)`, and `HolidayHorizon(profile: str, version: str, starts_on: date, ends_on: date, holidays: tuple[date, ...])` validate at construction.
- `BusinessCalendar.from_blueprint(timezone_name: str, blueprint: CalendarBlueprint) -> BusinessCalendar` is the only public construction path.
- `BusinessCalendar.elapsed(interval: UtcInterval) -> DualElapsed`, `BusinessCalendar.add(request: BusinessTimeAddition) -> datetime`, `BusinessCalendar.next_working_instant(instant: datetime) -> datetime`, `BusinessCalendar.working_interval(day: date) -> UtcInterval | None`, `BusinessCalendar.business_date(instant: datetime) -> date`, and `BusinessCalendar.business_day_end(day: date) -> datetime | None` are pure queries/calculations.
- `cadence_boundary(calendar: BusinessCalendar, rule: CadenceRule, ordinal: int) -> datetime` returns the fixed ordinal boundary without consulting workdays/holidays.
- `materialize_us_federal_horizon(first_start: datetime) -> HolidayHorizon` and `extend_us_federal_horizon(horizon: HolidayHorizon, as_of: date) -> HolidayHorizon` are pure data functions. They accept/return only `US_FEDERAL_V1` horizons and never persist a revision.

**Files:**

- Create `backend/app/v2/domain/business_calendar.py` for aware interval contracts, resolved-calendar validation, dual-clock arithmetic, working-instant/date helpers, and fixed cadence only.
- Create `backend/app/v2/domain/us_federal_calendar.py` for `US_FEDERAL_V1` date rules, observed dates, immutable holiday horizon, and pure idempotent extension only.
- Modify `backend/app/v2/domain/__init__.py` only for additive public exports.
- Create `backend/tests/v2/unit/test_business_calendar.py`.
- Create `backend/tests/v2/unit/test_us_federal_calendar.py`.
- Modify `backend/tests/v2/unit/test_architecture_boundaries.py` only for the pure-domain dependency boundary.
- Create `evidence/v2/M1-T04/README.md` plus command-output evidence during implementation.
- Do not modify Task 3 algorithms/vectors unless its reviewed public contract is demonstrably unusable; stop for plan review rather than silently changing it.
- Do not create/modify Alembic, ORM, repository, unit-of-work, work/sprint/visit persistence, scheduler, engine, Jira/OpenAI, frontend, or deployment files.

**Exact calendar contract:**

- All public instant inputs must be aware. Normalize typed results to UTC. Calendar elapsed time is exact UTC elapsed duration; business elapsed time is the exact intersection with resolved working intervals after weekdays and explicit full-day holidays are applied.
- The MVP calendar is one local daily interval with strictly ordered `HH:MM` endpoints, a non-empty unique ordered weekday set, a valid IANA timezone, unique ordered explicit holidays not beyond the horizon, and a named profile/version. Do not read host locale/timezone or the v1 calendar implementation.
- Convert fixed UTC instants through `zoneinfo` for local comparison. When resolving a configured local work/cadence boundary, validate it by UTC round-trip; reject a nonexistent local time and reject an ambiguous local time without an explicit authority-approved fold rather than attaching a timezone silently.
- A positive business-time addition begins at the supplied instant when it is inside a working interval, otherwise at the next working instant; it skips non-working portions exactly. Adding zero returns the normalized supplied instant unchanged. Negative duration is invalid.
- `next_working_instant` returns the normalized input when it is inside `[workday_start, workday_end)`, otherwise the next valid workday start. A working interval is absent on a non-working weekday/holiday. Business date is the instant's team-local calendar date; business-day end is the aware UTC end for a working date or `None`.
- Cadence boundaries are planned fixed instants. Add `ordinal * cadence_days` to the anchor's team-local calendar date while retaining its local clock, resolve to UTC, and never shift for a weekend, holiday, work interval, or amount of completed work. The first boundary remains ordinal `0`; ordinals are true non-negative integers.
- Ordinary business-calendar calculations must never mutate/replace `ScrumBlueprint.first_boundary` or impose a carryover penalty. This task does not implement sprint lifecycle, manual boundary overrides, or downtime rebase.

**Exact `US_FEDERAL_V1` contract:**

- Include New Year's Day, MLK Day (third Monday in January), Washington's Birthday (third Monday in February), Memorial Day (last Monday in May), Juneteenth, Independence Day, Labor Day (first Monday in September), Columbus Day (second Monday in October), Veterans Day, Thanksgiving (fourth Thursday in November), and Christmas.
- A fixed-date holiday on Saturday is observed on Friday; one on Sunday is observed on Monday. Exclude Inauguration Day. Include cross-year observed dates correctly when materializing a bounded horizon.
- The starter materialization spans January 1 of the year before first start through December 31 ten years after its year. When fewer than two complete local calendar years remain, pure extension appends another ten years using the same `US_FEDERAL_V1` version and returns a new immutable horizon; otherwise it returns the existing value unchanged. Reapplying extension after one extension is idempotent.
- This task returns data only. A future service/transaction must persist a new calendar-policy/ground-truth revision; do not add that persistence here.

**RED command and required failures:**

- [ ] Write tests first. From `backend/`, run exactly:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/red.txt
  ```

- [ ] Confirm the command exits non-zero because the new calendar modules/interfaces are absent, not because the timezone database, fixtures, or assertions are malformed.
- [ ] Cover naive/reversed intervals, invalid timezone/weekday/local interval/holiday horizon, exact zero and negative additions, start/middle/end-of-day behavior, partial day, an elapsed interval spanning overnight, weekend, explicit holiday, multi-day addition, and intervals containing no business time.
- [ ] Cover `America/Los_Angeles` spring-forward and fall-back with fixed UTC inputs, UTC/local round-trip, exact calendar-versus-business elapsed results, and configured nonexistent/ambiguous local boundaries failing explicitly.
- [ ] Cover business date/end and next-working behavior at boundaries, weekends, holidays, and year change.
- [ ] Cover cadence ordinal `0`, positive ordinals, invalid bool/negative ordinal, 14-local-day boundaries across both DST changes, and proof that weekend/holiday boundaries retain the anchored local clock without adjustment.
- [ ] Cover every exact `US_FEDERAL_V1` rule, Saturday/Sunday observation, cross-year New Year observation, Inauguration exclusion, initial starter horizon, no-op threshold, ten-year extension, uniqueness/order, and idempotent repeated extension.
- [ ] AST/import tests reject v1 calendar/engine/scheduler, database/ORM, Jira/OpenAI, host-local timezone state, and external network dependencies.

**Implementation steps:**

- [ ] Implement frozen aware interval, duration request, dual elapsed, cadence, and holiday-horizon value contracts with strict validation and at most three public arguments.
- [ ] Implement one resolved immutable `BusinessCalendar` factory from the team timezone plus `CalendarBlueprint`; cache no mutable global calendar state.
- [ ] Implement short local-boundary resolution, working-date/interval enumeration, dual elapsed, next-working, and forward-addition helpers using `ZoneInfo` plus UTC round-trip validation.
- [ ] Implement fixed cadence arithmetic separately from workday selection so no working-calendar adjustment can alter sprint instants.
- [ ] Implement the exact federal rules and pure horizon extension with named constants instead of magic dates/thresholds.
- [ ] Add only approved exports/boundary checks. Do not implement member capacity, availability overlays, status visits, sprint state, persistence revisions, or scheduler behavior.
- [ ] Run the identical test selection after implementation, retaining GREEN with:

  ```bash
  set -o pipefail
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/green.txt
  ```

- [ ] Refactor only while the same focused selection stays green and every touched/new function remains within project limits.

**Verification, documentation, and evidence:**

- [ ] Run the focused GREEN selection, Task 3 focused selection, `tests/v2 -q`, full safe backend `tests -q`, Ruff `../.venv/bin/python -B -m ruff check --no-cache .`, Alembic `heads --verbose`, `branches --verbose`, and `history`, an AST touched-function scan, and `git diff --check`; retain exact commands/output under `evidence/v2/M1-T04/`.
- [ ] Record Python/tzdata environment, RED reason, DST vectors, holiday/cadence cases, Task 3 regression, full counts/warnings, sole `014` head, no migration, and no external call in `evidence/v2/M1-T04/README.md` without secrets.
- [ ] Update mandatory current-state documents and this plan's checklist. Keep M1 in progress; work/sprint/status-visit persistence is the next plan decision, not part of Task 4.
- [ ] Inspect/stage only Task 4 files and commit exactly `feat(v2): add dual-clock business calendar`.

**Done condition:** Pure tests prove exact calendar/business elapsed time, deterministic forward business-time addition, DST-safe local/UTC resolution, fixed unadjusted local cadence, and exact/idempotent `US_FEDERAL_V1` materialization; no persistence/schema/external boundary changed; Alembic remains sole head `014`; Task 3 plus focused/v2/full tests and Ruff pass with truthful evidence and the exact Task 4 commit; M1 remains in progress.

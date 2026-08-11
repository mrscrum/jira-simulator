# M1-T05 Evidence — authoritative Scrum state persistence

Date: 2026-08-11

Implementation base: `5e5fac547659` (`docs: define durable Scrum state slices`), a plan-only
descendant of reviewed Task 4 head `11f3663`.

Commit history: original Task 5 implementation `a46b615` (`feat(v2): persist authoritative scrum
state`); review fix round 1 `b44d74a` (`fix(v2): bind authoritative scrum state`); review fix round
2 `234397c` (`fix(v2): support sparse scrum after-images`); review fix round 3 `e9dd4cf`
(`fix(v2): harden scrum mapper boundaries`). Review fix round 4 has focused GREEN on committed base
`e9dd4cf` and final verification is complete. The exact commit
`fix(v2): refresh authoritative scrum reads` is pending, so no final hash is claimed here.

Scope: immutable authoritative Scrum-state values, eleven relational mappings, a detached
caller-owned-session mapper, and reversible Alembic revision 015. This task does not implement a
lifecycle transition, runtime advance, semantic-counter claim, allocation formula, ledger append,
projection delivery, scheduler/engine service, API, frontend, Jira/OpenAI call, deployment, UAT,
Task 6, or revision 016.

## Environment and command discipline

Verification ran from `backend/` using the repository virtual environment, Python 3.12, file-backed
disposable SQLite for integration tests, `PYTHONDONTWRITEBYTECODE=1`,
`INTEGRATION_TESTS=false`, pytest cache disabled, and `set -o pipefail` for retained pipelines.
The shared Task 5 v2 session fixture and every Task 5 ad hoc SQLite engine explicitly execute
`PRAGMA foreign_keys=ON`; fresh-process schema creation and disposed-engine restart tests also
assert or configure that pragma.

No secret is present in these artifacts. No external provider, live Jira/OpenAI service, production
database, deployment target, remote Git branch, or UAT environment was accessed.

## Strict RED -> GREEN -> REFACTOR

All initial Task 5 unit, mapper, migration, import, and architecture tests were written before the
Task 5 domain, ORM, mapper, or revision existed. The exact initial RED command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/red.txt
```

Exact initial RED: exit `2`, three collection errors in `0.32s`. Every error was the expected
`ModuleNotFoundError: No module named 'app.v2.domain.scrum_state'` from the absent Task 5 surface.
There was no malformed test, fixture failure, migration/import cycle, or Task 1-4 regression.

Self-review added further tests before the corresponding production fixes. The retained REDs are:

- `self-review-red.txt`: exit `1`, `3 failed in 0.27s`. SQLite still accepted a sample whose
  `required_work_microseconds` did not match its visit, an unknown natural-decision counter key,
  and an unknown natural-evaluation decision type. The fix added the composite visit/sample work
  identity and exact closed decision-type checks to both ORM metadata and revision 015.
- `hardening-red.txt`: exit `1`, `3 failed, 5 passed in 0.42s`. Draw provenance could be forged to
  another entity, domain microseconds accepted `2^63`, and SQLite accepted infinite sampled hours.
  The fix bound both Task 3 draw documents to the exact visit/team/run/type/occurrence/draw
  coordinate and added non-negative signed-SQLite-integer plus finite-float checks.
- `nested-coordinate-red.txt`: exit `1`, `2 failed in 0.18s`. Boolean `occurrence` and `draw_index`
  values inside the nested canonical message were accepted because booleans compare as integers.
  The fix applies strict `type(value) is int` safe-integer validation to nested coordinates.
- `utc-normalization-red.txt`: exit `1`, `1 failed in 0.18s`. A valid aware `-07:00` instant was
  rejected rather than normalized. The fix now rejects naive instants but normalizes every aware
  representation to UTC before validation and persistence.

The focused hardening selection then passed `101` tests (`hardening-green.txt`), and the expanded
migration/import/FK/config/v1 proof selection passed `133` tests (`proof-expansion.txt`). The final
identical Task 5 focused command above, changing only the output target to `green.txt`, produced:

```text
184 passed in 14.49s
```

## Authoritative state contract

The public state is detached, frozen, slotted, tuple-only at aggregate boundaries, copy/deepcopy
stable, and rejects unsupported reconstruction. Direct construction and `dataclasses.replace`
revalidate exact enums, UUID types and semantic UUID coordinates, safe integer coordinates,
Fibonacci points, lifecycle/time coherence, interval ordering, microsecond balance, canonical JSON,
SHA-256 digests, and Task 3 sampling provenance.

Important numeric boundaries are explicit:

- ordinary deterministic coordinates are non-negative safe integers through `2^53 - 1`;
- semantic-counter `next_value` alone may equal `2^53` as the exhausted sentinel;
- persisted durations use SQLite integer storage in `0..2^63 - 1`; public validation rejects
  booleans, and SQL checks reject real storage values;
- factor/unit fractions are finite and bounded to `[0, 1]`; sampled hours are finite and
  non-negative;
- aware instants normalize to UTC; naive instants reject.

`ScrumStateWriteSet` contains sparse after-images for rows touched by a slice, while every
`ScrumStateSnapshot` is a complete detached aggregate in deterministic semantic order. Neither
type carries SQLAlchemy state, callables, external intents, lifecycle decisions, allocation
behavior, or counter-claim behavior.

## Revision 015 schema and constraint inventory

Revision 015 owns exactly these eleven tables:

- `v2_member_identities`: team-stable semantic member UUID and blueprint array index, unique by
  team/index and by team/id.
- `v2_member_availability_overlays`: run-owned member overlay interval, fraction, optional exact
  daily-capacity ceiling, reason, and canonical provenance/hash.
- `v2_member_business_date_consumption`: run/member/business-date identity with exact consumed
  labor microseconds.
- `v2_work_items`: semantic creation coordinate, issue type, Fibonacci points, priority/rank,
  lifecycle, canonical status key, and created/updated instants.
- `v2_work_item_factors`: one immutable canonical factor of each closed kind per work item.
- `v2_sprints`: semantic ordinal, lifecycle, immutable planned interval, coherent observed times,
  and one partial-unique active sprint per team/run.
- `v2_sprint_scope`: sprint/item membership interval, unique sprint/item pair, and one
  partial-unique current membership per item.
- `v2_status_visits`: semantic item ordinal, lifecycle/status/activity/owner, coherent enter/close
  times, balanced exact work clocks, and one partial-unique open visit per item.
- `v2_status_visit_samples`: immutable one-to-one Task 3 dwell/touch parameters, explicit draws,
  canonical provenance/hashes, finite sampled hours, and required-work identity matching the
  visit through a composite foreign key.
- `v2_semantic_counters`: exact closed scope identity and checked `next_value`, with no server
  default or autoincrement allocation.
- `v2_natural_decision_evaluations`: closed decision type, natural eligibility identity, committed
  occurrence coordinate, commit UUID, and recorded instant, with separate unique constraints for
  eligibility and occurrence.

The schema uses real composite foreign keys to preserve team/run ownership through member, work,
sprint, scope, visit, sample, counter, and evaluation rows. Raw-SQL/ORM constraint tests reject
mixed team/run references, cross-team member ownership, mismatched sample work, unknown enum and
decision values, invalid lifecycle/time combinations, negative/out-of-range/non-integer numeric
values, infinite sampled hours, duplicate member/work/sprint/visit coordinates, duplicate factor or
sample identities, duplicate natural eligibility/occurrence, and second active-sprint/open-visit/
current-scope rows.

The migration and ORM definitions are compared table-by-table for columns, nullability, defaults,
primary keys, named indexes including SQLite partial predicates, unique constraints, foreign keys
including delete behavior, and normalized check SQL. They match for all eleven Task 5 tables.

## Mapper transaction, rollback, order, and restart proof

`SqlAlchemyScrumStateMapper` receives a caller-owned `Session`. Static and behavioral tests prove
it does not create a session and never calls `begin`, `commit`, `rollback`, `close`, or an external
adapter. `add` validates the sparse write set, loads omitted persisted owners under
`session.no_autoflush`, validates a complete merged snapshot before Task 5 DML, applies only the
touched Task 5 rows, flushes inside the caller transaction, and returns that complete detached
snapshot. `load` returns the same state in deterministic semantic order.

The transaction tests prove:

- all eleven rows are visible after mapper flush while the caller transaction remains active;
- explicit caller rollback leaves every Task 5 table empty;
- a real integrity failure leaves rollback ownership with the caller and leaves no committed rows;
- a deliberately corrupted write set is rejected with zero SQL statements;
- shuffled input is returned in the same semantic order used by a later load.

The restart test commits representative values for every state type to file-backed SQLite, disposes
the first engine, creates a fresh engine/session, and reloads an exactly equal snapshot. UUIDs,
aware UTC instants, dates, exact microseconds, provenance JSON/hashes, sampled values, counters,
natural eligibility assignments, and collection order all survive the restart.

## Configuration, import, and v1 isolation

Member identity stores only the semantic member UUID, owning team UUID, and persisted-blueprint
array index. A persisted-team integration test derives the member UUID from that exact array
position. Domain and relational inspection prove Task 5 state contains no member name, role,
responsibility, proficiency, configured capacity/WIP, route, timing grid, calendar, or policy
configuration; those values remain in the immutable resolved blueprint.

Fresh subprocesses cold-import every team/live/Scrum-state model and every direct or lazy mapper/UOW
export first. Each permutation registers all eighteen v2 tables, creates the complete schema using
`Base.metadata.create_all()`, enables real SQLite foreign keys, and terminates without an import
cycle. Task 5 domain AST checks also exclude persistence, ORM, engine/integration, hidden clock,
randomness, allocation, claim, advance, and transition dependencies.

Legacy isolation is covered in two directions: no legacy table has a foreign key to a Task 5 table,
and the populated migration round trip compares every pre-015 legacy and v2 table before and after
downgrade. No v1 route/model behavior or external integration was changed; the legacy model-package
edit is limited to additive, cycle-aware v2 mapping registration.

## Migration proof

The retained migration selection is `alembic-roundtrip.txt`:

```text
3 passed in 1.29s
```

It proves:

- a fresh CLI graph has one linear `015 (head)`;
- revision-created and ORM-created Task 5 schemas match exactly;
- a database populated across every legacy table, Task 1 team/blueprint/run/runtime state, runtime
  version, and all three Task 2 ledgers survives `014 -> 015 -> 014 -> 015` with ordered rows and
  pre-existing column/index/FK/check metadata unchanged;
- downgrade drops only the eleven Task 5 tables and its supporting run-ownership index, returning
  exact revision-014 state;
- re-upgrade recreates all Task 5 tables empty and finishes at revision 015.

Recorded Alembic outputs show sole `Rev: 015 (head)` with parent `014`, empty branch output, and a
linear history from `001` through `015`.

## Regression and static verification

All saved pytest outputs used pipeline failure propagation:

- Task 1 focused: `56 passed, 1 warning in 1.93s`.
- Task 2 focused: `186 passed in 11.13s`.
- Task 3 focused: `251 passed in 0.58s`.
- Task 4 focused: `146 passed in 0.36s`.
- Task 5 focused: `184 passed in 14.49s`.
- All v2: `722 passed, 1 warning in 17.59s`.
- Full safe backend: `1240 passed, 43 skipped, 15 warnings in 42.94s`.

The 15 full-suite warnings are the unchanged baseline categories: one Starlette/httpx deprecation,
13 Jira-bootstrapper unawaited-`AsyncMock` warnings, and one SQLAlchemy identity-map conflict
warning. No warning was suppressed or broadened.

Static results:

- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole 015 head, parent 014, no branches, linear history.
- Populated migration/metadata round trip: `3 passed`.
- Shape scan: `17` touched/new Python files; no function over 30 lines and no function accepting
  more than three arguments.
- Repository `git diff --check`: exit `0` with empty output.

The exact outputs are retained beside this README. The original Task 5 evidence was committed in
`a46b615`, review fix round 1 in `b44d74a`, review fix round 2 in `234397c`, and review fix round 3
in `e9dd4cf`. No push,
deployment, live-system access, Jira/OpenAI access, UAT, Task 6 implementation, or revision 016
occurred during these verification rounds.

## Fix round 1 — authoritative binding evidence

Review-fix base: `a46b615` (`feat(v2): persist authoritative scrum state`). This round hardens only
Task 5 domain and persistence boundaries plus the existing revision 015. It creates no revision 016
and implements no Task 6 operation, UI, adapter, external call, deployment, push, or UAT action.

### RED evidence

The review regressions were written before production changes. The exact consolidated command,
executed from `backend/`, was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-1-red.txt
```

`review-fix-round-1-red.txt` records exit `1` and `141 failed, 97 passed in 14.88s`. The expected
failures covered exact/sealed type enforcement, subclass and `isinstance` bypasses, authenticated
Task 3 sample origin, typed natural owners, exact microsecond rounding, persisted-blueprint graph
validation, reference/aggregate coherence, load-time authority checks, and pre-DML uniqueness.

Supplemental tests also preceded their fixes:

- `review-fix-round-1-export-red.txt`: `1 failed in 0.11s` because
  `StatusVisitSampleInput` was not yet in the closed public domain export.
- `review-fix-round-1-aggregate-red.txt`: `4 failed in 0.94s` because active-sprint, open-visit,
  current-scope, and evaluation-occurrence conflicts reached SQLite rather than rejecting before
  Task 5 DML.
- `review-fix-round-1-scalar-red.txt`: `1 failed in 0.17s` because a forged `UUID` subclass was
  accepted.
- `review-fix-round-1-route-red.txt`: `1 failed in 0.20s` because repeated status keys exposed a
  status-only route lookup rather than exact status/activity-step matching.

### Binding and integrity proof

- Every public and nested Task 5 record, trusted factory input, aggregate tuple member, write set,
  snapshot, query, enum, UUID, integer, and floating boundary is exact-type checked. Task 5 values
  cannot be runtime-subclassed, yet remain frozen/slotted, copy/deepcopy stable, replace-validating,
  and pickle/reconstruction resistant.
- A status-visit sample can be created only through the sealed trusted input. Its Task 3
  `UniformDraw` origins are regenerated with the persisted blueprint seed and exact
  team/run/entity/decision/occurrence/draw coordinates. The precise timing-grid cell,
  linear-uniform algorithm/version/parameters, canonical messages, HMAC-derived integers/unit
  values, inner and outer hashes, sampled hours, and required-work digest all authenticate on create
  and reload. Mutation of low/high bounds, messages, coordinates, algorithms, versions, parameters,
  results, or hashes rejects.
- Natural counter/evaluation rows now carry nullable typed `work_item_id`/`member_id` ownership in
  the ORM and the existing revision 015. Composite foreign keys and row-shape checks bind visit and
  cancellation semantics to work items and member-unavailable semantics to members. Only
  cancellation and member-unavailable outcome evaluations are supported. No revision 016 exists.
- Hours-to-microseconds conversion uses `float.as_integer_ratio()` and integer nearest-ties-to-even
  rounding into the non-negative signed-64-bit range. Exact vectors include
  `2**-11 -> 1_757_812` and `3 * 2**-11 -> 5_273_438`. Required visit work equals the authenticated
  touch sample exactly.
- Before emitting Task 5 DML, the caller-session mapper validates the actual persisted team,
  blueprint, and optional run; member indexes/responsibilities; exact status/activity route steps;
  timing cells; references; duplicate or mixed team/run identities; open-state relationships; and
  semantic plus partial uniqueness. Loading rejects missing/mixed authority and reauthenticates all
  sample evidence against that blueprint.

SQLite boolean-storage correction: SQLite stores a bound Python boolean with integer storage class.
Consequently, raw SQL cannot distinguish bound `True` from stored integer `1`. Exact boolean
rejection is proved at the public domain and mapper validation boundaries; SQL checks prove true
integer storage and reject non-boolean real values. This correction supersedes earlier language in
this evidence file that could be read as claiming SQLite itself rejects a bound boolean.

### GREEN and final command results

The final Task 5 command was identical to the consolidated RED command except that it wrote
`review-fix-round-1-green.txt`:

```text
245 passed in 14.09s
```

All final pytest commands used `set -o pipefail`, `PYTHONDONTWRITEBYTECODE=1`,
`INTEGRATION_TESTS=false`, the repository virtual environment, `-B`, and pytest cache disabled.
Their retained outputs are:

- `review-fix-round-1-task1-focused.txt`: `56 passed, 1 warning in 1.34s`.
- `review-fix-round-1-task2-focused.txt`: `186 passed in 10.41s`.
- `review-fix-round-1-task3-focused.txt`: `251 passed in 0.43s`.
- `review-fix-round-1-task4-focused.txt`: `146 passed in 0.27s`.
- `review-fix-round-1-green.txt`: `245 passed in 14.09s`.
- `review-fix-round-1-v2-suite.txt`: `783 passed, 1 warning in 16.89s`.
- `review-fix-round-1-full-suite.txt`: `1301 passed, 43 skipped, 15 warnings in 44.96s`.
- `review-fix-round-1-ruff.txt`: exit `0`, `All checks passed!`.
- `review-fix-round-1-alembic-heads.txt`: sole `015 (head)` with parent `014`;
  `review-fix-round-1-alembic-branches.txt`: empty; history remains linear.
- `review-fix-round-1-alembic-roundtrip.txt`: `4 passed in 1.35s`, covering populated round trip and
  ORM/revision-015 parity.
- `review-fix-round-1-code-shape.txt`: `11` changed Python files, no function over 30 lines and no
  function accepting more than three arguments.
- `review-fix-round-1-architecture.txt`: `15 passed in 0.23s`.
- `review-fix-round-1-cold-import.txt`: `41 passed in 8.76s`.

The 15 full-suite warnings remain the prior baseline categories. No secret, external provider,
Jira/OpenAI account, production database, live system, deployment target, or remote Git branch was
accessed during this fix or its verification.

## Fix round 2 — sparse after-image and zero-touch evidence

Review-fix base: `b44d74a` (`fix(v2): bind authoritative scrum state`). This verified round was
committed as `234397c` (`fix(v2): support sparse scrum after-images`). Scope is limited to the
reviewed Task 5 domain, mapper, ORM, tests, and existing revision 015. It adds no broad Task 6
upsert/CAS operation, revision 016, frontend, adapter, external call, deployment, push, or UAT
action.

### Consolidated RED

The regression tests preceded production changes. The exact standard five-file Task 5 command,
executed from `backend/`, was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-2-red.txt
```

`review-fix-round-2-red.txt` records exit `1` and `22 failed, 247 passed in 14.99s`. The expected
failures covered four findings: null-activity zero-touch workflow steps, sparse touched-row
after-images referencing omitted persisted owners, exact visit/sample cardinality and restart
authentication, and strict required-work SHA-256 representation resistant to equality-spoofing
string subclasses. A supplemental intrinsic zero-touch RED was separately witnessed as
`4 failed in 0.23s`; the
consolidated command and result above remain the primary TDD record.

### Contract and persistence proof

- `StatusVisitState.activity_key` is exactly `str | None`. An approved route step whose
  `required_activity` is null accepts and restarts only with `activity_key=None`, no member owner,
  and zero touch microseconds. Activity-bearing steps reject null activity, and null-activity steps
  reject a substituted activity or member. Zero-touch visits still carry one authenticated sample.
- A `ScrumStateWriteSet` may contain only touched consumption, factor, visit/sample, or
  visit-counter rows while their unchanged member/work owners are omitted. Under the caller's
  `Session` and `no_autoflush`, the mapper resolves persisted owners for the same team/run and merges
  them with touched rows into a complete candidate snapshot before Task 5 DML. Missing and alien
  owners reject without a new Task 5 write.
- Every complete snapshot and every newly inserted visit has exactly one authenticated sample. An
  updated existing visit may omit its unchanged sample only after the persisted sample is resolved
  and reauthenticated. Direct snapshots, raw/restart loads, new visits, and sparse updates all
  reject missing sample evidence at the appropriate pre-DML/load boundary.
- `required_work_sha256` accepts only an exact plain lower-case 64-character hexadecimal string
  equal to the authenticated required-work document digest. Upper-case, short, non-hex, wrong
  content, and equality-spoofing `str` subclasses reject in value, aggregate, and mapper paths
  before SQL.
- The mapper narrowly updates an already persisted status visit after-image. It does not introduce
  generalized Task 5 upsert, counter claim, runtime CAS, or Task 6 behavior; other Task 5 rows retain
  their reviewed insert semantics.
- ORM and revision 015 agree that `v2_status_visits.activity_key` is nullable. Migration parity,
  populated downgrade/re-upgrade, and a disposed-engine zero-touch restart all pass. Revision 015
  remains the sole linear head; no revision 016 exists.

### Final GREEN and retained verification

The final focused command was identical to the consolidated RED command except for the tee target
`review-fix-round-2-green.txt`:

```text
273 passed in 18.70s
```

All retained pytest pipelines used `set -o pipefail`, `PYTHONDONTWRITEBYTECODE=1`,
`INTEGRATION_TESTS=false`, the repository virtual environment, `-B`, and disabled pytest cache.

- `review-fix-round-2-task1-focused.txt`: `56 passed, 1 warning in 2.30s`.
- `review-fix-round-2-task2-focused.txt`: `171 passed in 13.42s`.
- `review-fix-round-2-task3-focused.txt`: `251 passed in 0.86s`.
- `review-fix-round-2-task4-focused.txt`: `146 passed in 0.50s`.
- `review-fix-round-2-green.txt`: `273 passed in 18.70s`.
- `review-fix-round-2-v2-suite.txt`: `811 passed, 1 warning in 22.68s`.
- `review-fix-round-2-full-suite.txt`: `1329 passed, 43 skipped, 15 warnings in 50.93s`.
- `review-fix-round-2-ruff.txt`: exit `0`, `All checks passed!`.
- Alembic outputs: sole `015 (head)`, parent `014`, empty branch output, linear history.
- `review-fix-round-2-alembic-roundtrip.txt`: `4 passed in 1.79s` for populated round trip and
  ORM/revision-015 parity.
- `review-fix-round-2-cold-import.txt`: `39 passed in 10.97s`.
- `review-fix-round-2-architecture.txt`: `15 passed in 0.27s`.
- `review-fix-round-2-code-shape.txt`: `8` changed Python files with no function over 30 lines and
  no function accepting more than three arguments.
- `review-fix-round-2-diff-check.txt`: exit `0` with empty output.

The 15 full-suite warnings remain the existing baseline categories. No secret, external provider,
Jira/OpenAI account, production database, live system, deployment target, remote push, UAT action,
Task 6 implementation, or revision 016 was accessed or introduced.

## Fix round 3 — clean-session and sample-authentication evidence

Review-fix base: `234397c` (`fix(v2): support sparse scrum after-images`). The round-3 fix is
committed as `e9dd4cf` (`fix(v2): harden scrum mapper boundaries`). Scope remains limited to Task 5
domain validation, caller-session mapping, tests, and documentation. It adds no Task 6
upsert/CAS behavior, revision 016, frontend, adapter, external call, deployment, push, or UAT action.

### Consolidated and supplemental RED

The regression tests preceded production changes. From `backend/`, the exact standard selection was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-3-red.txt
```

It recorded
`34 failed, 273 passed in 15.99s` in `review-fix-round-3-red.txt`. Those failures reproduced caller
sessions with pending new, dirty, or deleted ORM state; coordinate-free empty write sets returning
false complete snapshots; nested `UniformDraw` scalar/equality forgeries; and retained sample-unit
float subclasses that could diverge between validation and persistence.

A supplemental load-boundary selection preceded the shared session fix:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/integration/test_scrum_state_mapper.py -q -k 'mapper_load_rejects_caller_pending_state' 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-3-load-red.txt
```

It recorded
`3 failed, 131 deselected in 0.48s` in `review-fix-round-3-load-red.txt`, proving that pending deleted
samples, dirty visits, and unrelated new rows also had to reject before `load` authority SQL rather
than influence or coexist with a detached snapshot.

### Corrected boundary

- Both mapper entry points require a clean caller ORM unit of work: `Session.new`, `Session.dirty`,
  and `Session.deleted` must all be empty before authority or candidate loading and before Task 5
  DML. Rejection leaves rollback ownership and pending state with the caller.
- `add` rejects an empty, coordinate-free `ScrumStateWriteSet` before SQL on both empty and populated
  databases. It cannot return an empty value falsely presented as the complete persisted snapshot;
  Task 6 must skip the mapper when it has no Task 5 after-images.
- Trusted status-sample inputs revalidate every nested `UniformDraw` scalar exactly: algorithm text,
  `DecisionOccurrence` and its UUID/decision/safe-integer fields, draw index, canonical-message
  bytes, lower-case HMAC text, U53 integer, and finite unit float. Authentication compares the full
  keyed draw, so a low-bit HMAC nibble change that preserves U53 still rejects even when wrapped in
  equality-spoofing subclasses. The sealed sample factory repeats this validation for a
  low-level reconstructed input.
- Retained dwell and touch unit values are exact finite built-in floats in `[0, 1]`. Stateful or
  equality-spoofing float subclasses reject during value validation, aggregate validation, and the
  mapper boundary before SQL conversion or binding.
- Revision 015 remains unchanged and is still the sole linear head. Generalized after-image upsert,
  runtime CAS, counter claims, lifecycle/allocation behavior, and atomic Task 6 integration remain
  deferred.

### Final GREEN and retained verification

The exact focused GREEN command changed only the standard command's tee target:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-3-green.txt
```

- `review-fix-round-3-green.txt`: `311 passed in 15.54s`.
- `review-fix-round-3-task1-focused.txt`: `56 passed, 1 warning in 1.69s`.
- `review-fix-round-3-task2-focused.txt`: `186 passed in 10.69s`.
- `review-fix-round-3-task3-focused.txt`: `251 passed in 0.61s`.
- `review-fix-round-3-task4-focused.txt`: `146 passed in 0.39s`.
- `review-fix-round-3-v2-suite.txt`: `849 passed, 1 warning in 18.39s`.
- `review-fix-round-3-full-suite.txt`: `1367 passed, 43 skipped, 15 warnings in 45.84s`.
- `review-fix-round-3-ruff.txt`: exit `0`, `All checks passed!`.
- Alembic outputs: sole `015 (head)`, empty branches, and linear history.
- `review-fix-round-3-alembic-roundtrip.txt`: `4 passed in 1.48s`.
- `review-fix-round-3-cold-import.txt`: `39 passed, 2 deselected in 8.63s`.
- `review-fix-round-3-architecture.txt`: `15 passed in 0.24s`.
- `review-fix-round-3-code-shape.txt`: four touched Python files, with no function over 30 lines and
  no function accepting more than three arguments.
- `review-fix-round-3-diff-check.txt`: exit `0` with empty output.

The 15 full-suite warnings remain the existing baseline categories. No secret, external provider,
Jira/OpenAI account, production database, live system, deployment target, remote push, UAT action,
Task 6 implementation, or revision 016 was accessed or introduced.

## Fix round 4 — authoritative identity-map refresh evidence

Review-fix base: `e9dd4cf` (`fix(v2): harden scrum mapper boundaries`). The exact pending round-4
commit subject is `fix(v2): refresh authoritative scrum reads`; no commit hash is claimed before
that commit exists. Scope remains limited to Task 5 caller-session reads, deleted-visit identity
handling, tests, evidence, and documentation. It adds no Task 6 CAS/counter claim, revision 016,
external call, deployment, push, or UAT action.

### Genuine and supplemental RED

The standard five-file Task 5 regression selection was extended before production changes and
retained in `review-fix-round-4-red.txt`. It recorded exactly:

```text
11 failed, 314 passed in 18.46s
```

Those failures proved that a clean caller `Session` could retain unexpired ORM identities after a
separate committed update: cached team, run, blueprint, sample, and ordinary state attributes hid
persisted corruption or valid changes from both `load` and sparse `add`; a cached deleted run could
produce a false partial snapshot instead of rejecting. The failures were not pending-unit-of-work
cases: `Session.new`, `Session.dirty`, and `Session.deleted` remained empty.

The independently identified member-only and deleted-visit branches were added before their fixes.
`review-fix-round-4-supplemental-red.txt` recorded exactly `2 failed in 0.74s`: the member-only
candidate read trusted a cached externally corrupted member, and a cached externally deleted visit
raised `StaleDataError` instead of accepting its complete visit/sample after-image. After the fresh
visit lookup was added, `review-fix-round-4-identity-red.txt` recorded exactly `1 failed in 0.33s`
because reinsertion still emitted SQLAlchemy identity-map conflict warnings. That warning RED
preceded explicit stale-identity detachment.

### Corrected boundary

- Team, run, and visit primary-key reads force `populate_existing`; blueprint, member-only, and all
  eleven ordered state-collection selects also populate existing identities from the current
  transaction's visible database state.
- Persisted authority/sample corruption and a deleted run can no longer be hidden by a clean
  unexpired identity-map entry. Valid external state updates appear in complete returned snapshots,
  while unrelated cached identities remain unexpired and untouched.
- Expired, detached, and post-rollback caller objects remain supported. The existing pre-SQL gate
  still rejects genuine ORM `new`, `dirty`, or `deleted` work and preserves caller rollback
  ownership.
- When a complete visit/sample after-image recreates an externally deleted visit, the mapper
  removes only that confirmed-missing stale visit identity before adding the replacement. The
  reinsert succeeds without `SAWarning`, preserves complete restart state, and does not broaden the
  narrow Task 5 visit-after-image behavior into Task 6 CAS/upsert semantics.

### Focused GREEN and final verification

The identical standard five-file selection first reached behavioral GREEN at exactly:

```text
327 passed in 18.79s
```

The supplemental member-only/deleted-visit selection is retained separately in
`review-fix-round-4-supplemental-green.txt`. After the warning-specific RED and fix, a fresh final
standard run overwrote `review-fix-round-4-green.txt` with `327 passed in 20.84s`.

Retained final verification:

- Task 1 focused: `56 passed, 1 warning in 2.32s`.
- Task 2 focused: `186 passed in 14.02s`.
- Task 3 focused: `251 passed in 0.92s`.
- Task 4 focused: `146 passed in 0.62s`.
- Task 5 focused: `327 passed in 20.84s`.
- All v2: `865 passed, 1 warning in 23.38s`.
- Full safe backend: `1383 passed, 43 skipped, 15 warnings in 53.57s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole head `015` with parent `014`, empty branches, and linear history.
- Migration parity and populated round trip: `4 passed in 1.72s`.
- Cold-import selection: `39 passed, 2 deselected in 10.54s`.
- Architecture boundary selection: `15 passed in 0.28s`.
- Shape scan: two touched Python files, no function over 30 lines, and no function accepting more
  than three arguments.

The 15 full-suite warnings remain the existing baseline categories. No final round-4 commit hash
is claimed yet.

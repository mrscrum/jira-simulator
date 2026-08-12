# Task 5 implementation report — authoritative Scrum state persistence

## Status and scope

Status: original implementation committed as `a46b615`; review fix round 1 committed as
`b44d74a`; review fix round 2 committed as `234397c`; review fix round 3 committed as `e9dd4cf`
(`fix(v2): harden scrum mapper boundaries`); review fix round 4 committed as `9049e1a`
(`fix(v2): refresh authoritative scrum reads`); review fix round 5 committed as `0782070`
(`fix(v2): detach cascaded scrum identities`). The subsequent independent Ultra technical review
reported CLEAN with no Critical or Important findings. Task 5 is accepted; Task 6 remains open and
M1 remains in progress.

Implementation base: `5e5fac547659` (`docs: define durable Scrum state slices`), a plan-only
descendant of reviewed Task 4 head `11f3663`.

Original implementation commit subject: `feat(v2): persist authoritative scrum state`.

This task implements only frozen authoritative Scrum state, its relational persistence, detached
caller-owned-session mapping, and reversible revision 015. It adds no lifecycle transition,
allocation formula, counter claim, runtime advance, ledger append, scheduler/engine service, API,
frontend, Jira/OpenAI call, deployment, push, UAT, Task 6 behavior, or revision 016.

## Implemented behavior

- Added exact closed lifecycle, priority, factor, and semantic-counter enums plus frozen/slotted
  member, overlay, consumption, work item/factor, sprint/scope, status visit/sample, counter,
  natural-evaluation, query, write-set, and snapshot values.
- Reused Task 1-4 semantic UUID, canonical JSON/SHA-256, immutable-value, deterministic draw,
  sampling, blueprint, and aware-time contracts. Constructors and replacement strictly revalidate
  semantic coordinates, scalars, enums, Fibonacci points, lifecycle/time coherence, balanced exact
  microseconds, canonical provenance, draw coordinates, digests, and UTC normalization.
- Added `SimulatorRank` ordering by exact priority order, relative rank, and work-item UUID. Added
  exact kind-specific semantic-counter scopes and the persisted `2^53` exhausted sentinel without
  exposing an allocator or claim operation.
- Added eleven Task 5 SQLAlchemy mappings with named checks, semantic/composite unique constraints,
  partial unique active/current/open indexes, and real composite foreign keys that preserve
  team/run/member/work/sprint/visit ownership.
- Added `SqlAlchemyScrumStateMapper.load()` and `.add()` over a caller-supplied `Session`. The mapper
  validates before SQL, flushes constraint failures inside the caller transaction, never opens or
  resolves a transaction, and returns detached values in deterministic semantic order.
- Added revision `015` over `014`, creating parents before children and dropping children before
  parents. ORM and migration metadata match exactly for every Task 5 table.
- Enabled SQLite foreign keys on the shared Task 5 v2 fixture and every Task 5 ad hoc engine, then
  extended cycle-aware model registration plus direct/lazy cold-import coverage to all eighteen v2
  tables.

## Files

Production and migration:

- `backend/app/v2/domain/scrum_state.py`
- `backend/app/v2/domain/__init__.py`
- `backend/app/v2/persistence/scrum_state_models.py`
- `backend/app/v2/persistence/scrum_state_mapper.py`
- `backend/app/v2/persistence/__init__.py`
- `backend/app/v2/persistence/team_models.py`
- `backend/app/v2/persistence/team_repository.py`
- `backend/app/models/__init__.py`
- `backend/alembic/versions/015_add_v2_authoritative_scrum_state.py`

Tests:

- `backend/tests/v2/scrum_state_support.py`
- `backend/tests/v2/unit/test_scrum_state.py`
- `backend/tests/v2/integration/test_scrum_state_mapper.py`
- `backend/tests/v2/integration/test_migration_015.py`
- `backend/tests/v2/conftest.py`
- `backend/tests/v2/integration/test_projection_boundary.py`
- `backend/tests/v2/unit/test_architecture_boundaries.py`
- `backend/tests/v2/integration/test_migration_014.py`

Documentation and evidence:

- `README.md`, `changelog.md`, `assumptions.md`, `agent_instruction.md`
- `backlog/v2/README.md`, `backlog/v2/m1-scrum-state.md`
- `evidence/v2/M1-T05/README.md` and retained command outputs
- This implementation report

## Strict RED -> GREEN -> REFACTOR

All initial Task 5 tests preceded the Task 5 production and migration files. From `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/red.txt
```

Initial RED: exit `2`, three collection errors in `0.32s`, all caused solely by the absent
`app.v2.domain.scrum_state` module. There was no malformed test, fixture failure, import cycle, or
prior-task regression.

Review regressions were also written before their fixes:

- `self-review-red.txt`: `3 failed in 0.27s` for missing sample/visit required-work identity and
  open-ended natural decision types in raw SQLite rows.
- `hardening-red.txt`: `3 failed, 5 passed in 0.42s` for forged draw entity provenance, a domain
  duration beyond SQLite's signed range, and an infinite persisted sample.
- `nested-coordinate-red.txt`: `2 failed in 0.18s` for boolean occurrence/draw coordinates nested
  in the canonical decision message.
- `utc-normalization-red.txt`: `1 failed in 0.18s` because a valid aware offset instant was rejected
  instead of normalized to UTC.

The fixes added the composite sample work foreign key, exact decision checks, complete draw
coordinate binding and internal coherence validation, strict nested safe integers, true
signed-SQLite-integer and finite-float
checks, and aware-offset normalization. Intermediate hardening passed `101` tests, and the expanded
proof selection passed `133` tests.

Final identical focused GREEN, with only the tee target changed to `green.txt`:

```text
184 passed in 14.49s
```

## Domain and persistence proof

- Exact closed enums, strict scalar/UUID/date/aware-instant validation, semantic UUID derivation,
  Fibonacci points, every rank tie, boolean/negative/unsafe integer rejection, counter sentinel,
  lifecycle/time coherence, status-work balance, canonical payloads/digests, draw formulas, tuple
  immutability, copy/deepcopy identity, replacement validation, and reconstruction rejection are
  covered directly.
- Task 3 draw provenance is bound to the exact team, run, visit, decision type, occurrence zero,
  draw index, HMAC-derived U53 integer, and unit value. Required-work microseconds and hash are
  reproduced from the stored sample inputs.
- Persisted durations are true integers in `0..2^63 - 1`; safe semantic coordinates remain within
  `0..2^53 - 1`, except the counter's exact `2^53` exhausted sentinel. SQLite rejects real-valued
  integers and non-finite sampled hours even when raw ORM construction bypasses domain objects.
- Member identity is derived from the persisted-blueprint array position. Domain and column
  inspection prove names, roles, responsibilities, proficiency, nominal capacity/WIP, routes,
  timing grids, calendars, and policies remain exclusively in the canonical blueprint.
- All eleven state types round-trip exactly through the mapper. A shuffled write set and restart
  load use the same semantic ordering, and returned snapshots contain no SQLAlchemy instance state.

## Transaction, FK, constraint, and restart proof

- The mapper has no session factory and no `begin`, `commit`, `rollback`, `close`, engine,
  integration, Jira, or OpenAI call. It uses the caller's session and deliberately calls `flush`.
- Full write-set validation occurs before the first SQL statement. Caller rollback after a
  successful flush empties every Task 5 table; rollback after a genuine integrity failure remains
  the caller's responsibility and also leaves no committed Task 5 state.
- `PRAGMA foreign_keys=ON` is installed for all v2 SQLite connections. Composite FK tests reject
  mixed team/run ownership for every run table and cross-team member references for every member
  child. Sample required work is FK-bound to its owning visit.
- Raw database tests cover every check category plus true-integer columns, finite sample values,
  semantic identity uniqueness, one factor/sample, separate natural eligibility/occurrence
  uniqueness, and partial uniqueness for one active sprint, one current scope, and one open visit.
- A file-backed restart commits all eleven record types, disposes the engine, constructs a fresh
  engine/session, and reloads the exact detached snapshot including dates, UTC instants,
  microseconds, provenance/hashes, counters, evaluations, and order.

## Migration, import, and v1 isolation proof

The retained migration selection passed `3 passed in 1.29s` and proves:

- sole linear Alembic head 015 with parent 014 and empty branches;
- exact ORM/migration parity for columns, defaults/nullability/PKs, indexes and partial predicates,
  unique constraints, FKs/delete behavior, and checks across all eleven tables;
- populated `014 -> 015 -> 014 -> 015` preservation for every legacy table, Task 1
  team/blueprint/run/runtime data and runtime version, and all three Task 2 ledgers;
- downgrade removes only Task 5 state/supporting ownership metadata and restores exact revision-014
  rows/schema; re-upgrade recreates Task 5 tables empty at revision 015.

Fresh-process tests cold-import every direct team/live/Scrum-state model and every lazy model,
mapper, and UOW export first. Every permutation registers and creates all eighteen v2 tables with
foreign keys enabled and no import cycle. Legacy-table inspection proves no v1 table references a
Task 5 table, while the populated migration comparison proves pre-015 content/schema isolation.

## Final verification

- Task 1 focused: `56 passed, 1 warning in 1.93s`.
- Task 2 focused: `186 passed in 11.13s`.
- Task 3 focused: `251 passed in 0.58s`.
- Task 4 focused: `146 passed in 0.36s`.
- Task 5 focused: `184 passed in 14.49s`.
- All v2: `722 passed, 1 warning in 17.59s`.
- Full safe backend: `1240 passed, 43 skipped, 15 warnings in 42.94s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole `015 (head)`, parent `014`, empty branches, linear history.
- Populated migration/metadata round trip: `3 passed`.
- Shape: 17 touched/new Python files; no function over 30 lines or more than three arguments.
- Repository whitespace: `git diff --check` exited `0` with empty output.

The 15 warnings are exactly the preserved baseline: one Starlette/httpx deprecation, 13 existing
Jira-bootstrapper unawaited-`AsyncMock` warnings, and one existing SQLAlchemy identity-map warning.
No warning was suppressed or broadened.

## Self-review and concerns

- Rechecked every Task 5 domain record, mapper interface, table, FK/check/unique/index predicate,
  migration order, public export, and prohibited boundary against the brief.
- Converted each discovered gap into a witnessed RED before production changes: sample work
  identity, decision closure, draw coordinate binding, signed integer/finite-float storage, nested
  boolean coordinates, semantic add/load order, and aware-offset UTC normalization.
- Confirmed revision 015 contains no server-side allocation/default that could claim a counter,
  mapper mutation does not advance runtime or append a ledger, and domain objects expose no
  transition/claim/advance operation.
- Confirmed no v1 behavior, external boundary, live system, Jira/OpenAI account, deployment, push,
  UAT state, Task 6 implementation, or revision 016 entered the work.

No unresolved implementation concern. The original implementation was committed as `a46b615`,
review fix round 1 as `b44d74a`, and review fix round 2 as `234397c`. M1 remains in progress; Task 6
stays unchecked.

## Fix round 1 — authoritative binding review

Review-fix base: `a46b615` (`feat(v2): persist authoritative scrum state`). This round is limited to
hardening the reviewed Task 5 state contract in place, including Alembic revision 015. It adds no
revision 016, Task 6 behavior, frontend, external integration, deployment, push, or live-system
access.

### Review REDs

All consolidated regression tests were written before their fixes. From `backend/`, the exact
consolidated RED command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-1-red.txt
```

The expected result was exit `1`: `141 failed, 97 passed in 14.88s`. The failures demonstrated the
unsealed runtime-subclass/`isinstance` paths, samples that were structurally self-consistent but not
authenticated against the persisted blueprint seed and timing cell, missing typed natural-owner
columns and foreign keys, inexact float-to-microsecond conversion, incomplete blueprint graph and
reference validation, and conflicts that reached SQL instead of rejecting before Task 5 DML.

Four smaller witnessed REDs cover fixes discovered while making that selection green:

- `review-fix-round-1-export-red.txt`: `1 failed in 0.11s`; the new trusted sample input was absent
  from the additive closed public export.
- `review-fix-round-1-aggregate-red.txt`: `4 failed in 0.94s`; active-sprint, open-visit,
  current-scope, and natural-evaluation occurrence conflicts reached SQLite uniqueness constraints.
- `review-fix-round-1-scalar-red.txt`: `1 failed in 0.17s`; a `UUID` subclass could exploit equality
  behavior to bypass exact scalar validation.
- `review-fix-round-1-route-red.txt`: `1 failed in 0.20s`; a repeated status in a blueprint route
  exposed status-only lookup instead of exact status/activity-step matching.

### Hardened contract

- Every Task 5 public or nested value, tuple member, query, write set, snapshot, trusted factory
  input, and scalar boundary now requires its exact type. Runtime subclass creation and
  `isinstance`-style bypasses reject while frozen/slotted behavior, copy/deepcopy identity,
  replacement revalidation, and pickle/reconstruction rejection remain intact.
- `StatusVisitSample` is created only from a sealed trusted input containing the resolved blueprint,
  work item, visit, and the exact Task 3 dwell/touch `UniformDraw` values. Creation and reload
  regenerate HMAC draws from the blueprint seed and exact team/run/entity/decision/occurrence/draw
  coordinates, bind the exact issue-type/story-point/status/activity timing cell, and verify
  algorithm, version, parameters, canonical messages, inner digests, sampled results, required-work
  digest, and enclosing persisted values. Mutating any bound field rejects.
- Counter and natural-evaluation ownership is explicit in both the ORM and revision 015, with no
  revision 016: nullable `work_item_id` and `member_id` columns, composite owner foreign keys, and
  shape checks bind visit/cancellation records to work items and member-unavailable records to
  members. Natural evaluations are closed to cancellation and member-unavailable outcomes.
- Hours convert to non-negative signed-64-bit microseconds through `float.as_integer_ratio()` and
  exact nearest-ties-to-even integer arithmetic. Boundary proofs include `2**-11 -> 1_757_812` and
  `3 * 2**-11 -> 5_273_438`; visit required work must equal the authenticated touch sample exactly.
- Before any Task 5 write, the mapper loads the actual persisted team blueprint/run in the caller's
  session and validates team/run ownership, member bounds and responsibility, status/activity route
  pairs, timing cells, references, duplicate identities, mixed aggregates, open-state rules, and
  semantic/partial uniqueness conflicts. Load likewise rejects missing or mixed authority and
  reauthenticates persisted samples.

SQLite boolean-storage correction: SQLite binds Python booleans as integer storage, so raw SQL
cannot prove that a bound `True` was not an integer `1`. Exact boolean rejection is therefore proven
at the public domain and mapper validation boundaries. SQL checks prove integer storage class and
reject non-boolean real values. This statement supersedes any earlier wording that implied raw SQL
or SQLite checks distinguish booleans from their stored integer representation.

### Fix-round verification

The final focused command was identical to the consolidated RED command except for the tee target
`review-fix-round-1-green.txt`; it passed `245 passed in 14.09s`. Retained regression and static
results are:

- Task 1 focused: `56 passed, 1 warning in 1.34s`.
- Task 2 focused: `186 passed in 10.41s`.
- Task 3 focused: `251 passed in 0.43s`.
- Task 4 focused: `146 passed in 0.27s`.
- All v2: `783 passed, 1 warning in 16.89s`.
- Full safe backend: `1301 passed, 43 skipped, 15 warnings in 44.96s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole head `015`, parent `014`, empty branch output, linear history; revision-015
  populated round trip and ORM parity: `4 passed in 1.35s`.
- Shape scan: `11` changed Python files and no function over 30 lines or accepting more than three
  arguments.
- Architecture boundary selection: `15 passed in 0.23s`.
- Cold-import permutations: `41 passed in 8.76s`.

The warning inventory remains the existing baseline categories. No external provider, Jira/OpenAI
account, production database, live environment, deployment target, or remote Git branch was
accessed.

## Fix round 2 — sparse after-image and zero-touch review

Review-fix base: `b44d74a` (`fix(v2): bind authoritative scrum state`). This verified round was
committed as `234397c` (`fix(v2): support sparse scrum after-images`). It remains inside Task 5 and
revision 015 and adds no broad Task 6 upsert, atomic UOW integration, counter claim,
lifecycle/allocation behavior, revision 016, frontend, external call, deployment, push, UAT, or
live-system access.

### Review RED

The consolidated regressions were written before the corresponding production fixes. From
`backend/`, the exact command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-2-red.txt
```

The expected result was exit `1`: `22 failed, 247 passed in 14.99s`. The failures mapped to the
four supplied findings: nullable zero-touch workflow steps, sparse after-images whose persisted
owners were omitted from the write set, missing exact sample cardinality/authentication, and
forged or non-canonical required-work SHA-256 values. A supplemental intrinsic zero-touch RED was
separately witnessed as `4 failed in 0.23s` without changing the consolidated command above.

### Corrected Task 5 contract

- `StatusVisitState.activity_key` is exactly `str | None`. Approved `TO_DO`/`DONE` route steps with
  no required activity persist and restart with no activity, no member, and zero touch work while
  still retaining exactly one authenticated timing sample. Activity-bearing steps require their
  exact activity/member binding, and zero-touch steps reject both.
- `ScrumStateWriteSet` is a sparse collection of touched after-images. Before Task 5 DML, the
  mapper resolves omitted persisted member/work/visit/sample owners in the caller's session under
  `no_autoflush`, merges them into a complete candidate `ScrumStateSnapshot`, and validates that
  snapshot against the persisted blueprint. Missing or alien team/run owners reject pre-DML.
- Every complete snapshot and every newly inserted visit has exactly one authenticated sample.
  An existing visit after-image may omit its unchanged persisted sample only after the mapper has
  loaded and reauthenticated that sample; raw/restart loads reject missing samples.
- `required_work_sha256` is an exact plain lower-case SHA-256 string. Wrong length, upper-case,
  non-hex, and equality-spoofing `str` subclasses reject in the value, aggregate, and mapper paths
  before SQL.
- Existing visit rows alone receive the narrow Task 5 after-image update needed by this review.
  Other Task 5 rows preserve their existing insert behavior; broad generalized upsert/CAS behavior
  remains explicitly deferred to Task 6.
- ORM metadata and migration 015 both make only `v2_status_visits.activity_key` nullable, and the
  populated `014 -> 015 -> 014 -> 015` round trip plus parity checks remain green. No revision 016
  exists.

### Final verification

- Task 5 focused: `273 passed in 18.70s`.
- Task 1 focused: `56 passed, 1 warning in 2.30s`.
- Task 2 focused: `171 passed in 13.42s`.
- Task 3 focused: `251 passed in 0.86s`.
- Task 4 focused: `146 passed in 0.50s`.
- All v2: `811 passed, 1 warning in 22.68s`.
- Full safe backend: `1329 passed, 43 skipped, 15 warnings in 50.93s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole head `015`, parent `014`, empty branches, and linear history.
- Migration round trip and ORM parity: `4 passed in 1.79s`.
- Cold-import selection: `39 passed in 10.97s`; restart behavior is covered by the focused suite.
- Architecture boundary selection: `15 passed in 0.27s`.
- Shape scan: `8` changed Python files, with no function over 30 lines and no function accepting
  more than three arguments.
- Repository diff check: exit `0` with empty output.

The warning inventory remains the existing baseline categories. No secret, external provider,
Jira/OpenAI account, production database, live system, deployment target, remote push, UAT action,
Task 6 implementation, or revision 016 entered this fix round.

## Fix round 3 — clean-session and sample-authentication review

Review-fix base: `234397c` (`fix(v2): support sparse scrum after-images`). The round-3 fix is
committed as `e9dd4cf` (`fix(v2): harden scrum mapper boundaries`). This round remains inside Task 5
and revision 015. It adds no Task 6 upsert/CAS behavior, lifecycle/allocation behavior,
frontend, external integration, deployment, push, UAT, live-system access, or revision 016.

### Review RED

The consolidated Task 5 regression selection was written before production changes. From
`backend/`, the exact command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-3-red.txt
```

It recorded
`34 failed, 273 passed in 15.99s` in `review-fix-round-3-red.txt`. The failures reproduced pending
caller ORM state flushed or reflected by the mapper, empty coordinate-free write sets returning a
false complete snapshot, nested deterministic-draw scalar and HMAC equality forgeries, and retained
sample-unit float subclasses that could change behavior across validation and SQL binding.

The supplemental load selection used:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/integration/test_scrum_state_mapper.py -q -k 'mapper_load_rejects_caller_pending_state' 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-3-load-red.txt
```

It recorded `3 failed, 131 deselected in 0.48s` in
`review-fix-round-3-load-red.txt`. It proved that dirty visits, deleted retained samples, and
unrelated new rows must reject before load authority SQL as well as before add candidate loading.

### Corrected Task 5 contract

- `add` and `load` now require the caller's ORM unit of work to have empty `new`, `dirty`, and
  `deleted` collections before any authority/candidate query or Task 5 DML. The mapper performs no
  implicit flush or rollback of caller work; the caller retains the pending objects and rollback
  decision after rejection.
- `add` rejects an empty `ScrumStateWriteSet` before SQL on both empty and populated stores. With no
  team/run coordinate it cannot load or truthfully return a complete snapshot; Task 6 skips this
  mapper when its Task 5 after-image set is empty.
- Trusted sample input validation checks the exact nested `UniformDraw` representation and then
  authenticates it against the full keyed draw. Exact algorithm text, decision type/UUID/safe
  integers, draw index, canonical-message bytes, lower-case HMAC, U53 integer, and finite unit float
  prevent subclass equality tricks. A changed low HMAC nibble rejects even though the retained
  U53 is unchanged, and the sealed factory revalidates low-level reconstructed inputs.
- Retained dwell/touch unit values are exact finite built-in floats in `[0, 1]`. Mutable,
  stateful, or equality-spoofing float subclasses reject at the value, aggregate, and mapper
  pre-SQL boundaries.
- Revision 015 remains the sole linear head and no migration changed. Generalized upsert/CAS,
  runtime mutation, counter claims, lifecycle/allocation behavior, and Task 6 atomic integration
  remain deferred.

### Final verification

The exact focused GREEN command changed only the standard command's tee target:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_scrum_state.py tests/v2/integration/test_scrum_state_mapper.py tests/v2/integration/test_migration_015.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T05/review-fix-round-3-green.txt
```

- Task 5 focused: `311 passed in 15.54s`.
- Task 1 focused: `56 passed, 1 warning in 1.69s`.
- Task 2 focused: `186 passed in 10.69s`.
- Task 3 focused: `251 passed in 0.61s`.
- Task 4 focused: `146 passed in 0.39s`.
- All v2: `849 passed, 1 warning in 18.39s`.
- Full safe backend: `1367 passed, 43 skipped, 15 warnings in 45.84s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole `015 (head)`, empty branches, and linear history.
- Migration round trip and ORM parity: `4 passed in 1.48s`.
- Cold-import selection: `39 passed, 2 deselected in 8.63s`.
- Architecture boundary selection: `15 passed in 0.24s`.
- Shape scan: four touched Python files, no function over 30 lines, and no function accepting more
  than three arguments.
- Staged-candidate diff check: exit `0` with empty output.

The warning inventory remains the existing baseline categories. No secret, external provider,
Jira/OpenAI account, production database, live system, deployment target, remote push, UAT action,
Task 6 implementation, or revision 016 entered this fix round.

## Fix round 4 — authoritative identity-map refresh review

Review-fix base: `e9dd4cf` (`fix(v2): harden scrum mapper boundaries`). The verified change was
committed as `9049e1a` (`fix(v2): refresh authoritative scrum reads`). It remains inside Task 5 and
revision 015.

### Review RED

The expanded standard five-file Task 5 selection preceded production changes and is retained in
`review-fix-round-4-red.txt`. It recorded exactly `11 failed, 314 passed in 18.46s`. Clean,
unexpired caller identity-map entries masked externally committed authority/sample corruption,
ordinary valid state changes, and run deletion from both `load` and sparse `add` even though the
caller's ORM `new`, `dirty`, and `deleted` collections were empty.

Two separately inventoried read branches also received tests before their fixes.
`review-fix-round-4-supplemental-red.txt` recorded exactly `2 failed in 0.74s`: member-only add
trusted a cached corrupted member, while a complete visit/sample after-image for a cached deleted
visit raised `StaleDataError`. After fresh missing-row detection,
`review-fix-round-4-identity-red.txt` recorded exactly `1 failed in 0.33s` because the replacement
visit still produced SQLAlchemy identity-map conflict warnings.

### Corrected Task 5 contract

- Every authoritative ORM read populates an existing identity from the current transaction's
  database view: primary-key team/run/visit reads and blueprint/member/all-state selects no longer
  trust clean unexpired cached attributes.
- Cached corruption and deleted run authority reject; valid external updates appear in the returned
  complete snapshot without broadly expiring unrelated caller identities. Expired, detached, and
  post-rollback objects continue to work, while the earlier pending-ORM gate remains unchanged.
- A confirmed-missing cached visit identity is narrowly expunged before its complete visit/sample
  after-image is inserted. This avoids both `StaleDataError` and identity-map `SAWarning` while
  preserving caller transaction ownership and restart completeness.
- The fix adds no generalized Task 6 upsert, runtime CAS, counter allocation, lifecycle behavior,
  schema change, revision 016, external access, deployment, push, or UAT.

### Focused GREEN and final verification

The identical standard five-file selection first reached behavioral GREEN at exactly
`327 passed in 18.79s`. Supplemental GREEN is retained in
`review-fix-round-4-supplemental-green.txt`. After the warning-specific RED and fix, a fresh final
standard run overwrote `review-fix-round-4-green.txt` with `327 passed in 20.84s`.

- Task 1 focused: `56 passed, 1 warning in 2.32s`.
- Task 2 focused: `186 passed in 14.02s`.
- Task 3 focused: `251 passed in 0.92s`.
- Task 4 focused: `146 passed in 0.62s`.
- Task 5 focused: `327 passed in 20.84s`.
- All v2: `865 passed, 1 warning in 23.38s`.
- Full safe backend: `1383 passed, 43 skipped, 15 warnings in 53.57s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole `015` head with parent `014`, empty branches, and linear history.
- Migration parity and populated round trip: `4 passed in 1.72s`.
- Cold-import selection: `39 passed, 2 deselected in 10.54s`.
- Architecture selection: `15 passed in 0.28s`.
- Shape scan: two touched Python files, no function over 30 lines, and no function accepting more
  than three arguments.

The warning inventory remains the existing baseline categories. Round 4 was committed as `9049e1a`
(`fix(v2): refresh authoritative scrum reads`).

## Fix round 5 — cascaded identity detachment review

Review-fix base: `9049e1a` (`fix(v2): refresh authoritative scrum reads`). The verified fix was
committed as `0782070` (`fix(v2): detach cascaded scrum identities`). Scope remained limited to
Task 5 target-local identity-map handling, its regression, evidence, and documentation.

### Isolated RED

The same-key visit/sample cascade-restoration regression preceded the production change and is
retained in `review-fix-round-5-red.txt`. It recorded exactly `1 failed in 0.28s`: a complete
visit/sample after-image could restore its externally cascade-deleted visit, but the caller's
retained cached sample caused two SQLAlchemy identity-conflict `SAWarning`s.

### Corrected Task 5 contract

- Confirmed-missing restoration now detaches the target-local same-key visit and sample identities
  before inserting their complete after-images.
- The detachment is limited to those restored identities. Unrelated caller cache entries remain
  preserved and are neither expired nor detached.
- The change adds no generalized upsert/CAS, lifecycle or allocation behavior, schema change,
  revision 016, external access, deployment, push, UAT, or other scope broadening.

### Isolated GREEN and final verification

The identical isolated regression is retained in `review-fix-round-5-green.txt` and recorded
exactly `1 passed in 0.27s`.

- Direct target-local/unrelated-cache self-probe: `PASS`.
- Targeted mapper selection: `16 passed, 134 deselected in 1.38s`.
- Task 5 focused: `327 passed in 21.60s`.
- All v2, including Tasks 1-5: `865 passed, 1 warning in 25.29s`.
- Full safe backend: `1383 passed, 43 skipped, 15 warnings in 51.39s`.
- Ruff: exit `0`, `All checks passed!`.
- Alembic: sole `015` head with parent `014`, empty branches, and linear history.
- Migration parity and populated round trip: `4 passed in 1.81s`.
- Cold-import selection: `39 passed, 2 deselected in 10.98s`.
- Architecture selection: `15 passed in 0.25s`.
- Shape scan: two touched Python files, no function over 30 lines, and no function accepting more
  than three arguments.

The full-suite warnings remain the existing baseline categories. Round 5 was committed as
`0782070` (`fix(v2): detach cascaded scrum identities`). The subsequent independent Ultra
technical review reported CLEAN with no Critical or Important findings, completing Task 5
technical acceptance. Task 6 remains open and M1 remains in progress.

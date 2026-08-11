# Task 5 implementation report — authoritative Scrum state persistence

## Status and scope

Status: implementation, review, and verification DONE; exact Task 5 commit pending.

Implementation base: `5e5fac547659` (`docs: define durable Scrum state slices`), a plan-only
descendant of reviewed Task 4 head `11f3663`.

Required commit subject: `feat(v2): persist authoritative scrum state`.

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

No unresolved implementation concern. The exact commit remains intentionally pending until this
report and the mandatory current-state documentation are included in it. M1 remains in progress;
Task 6 stays unchecked.

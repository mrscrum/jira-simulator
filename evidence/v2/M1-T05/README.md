# M1-T05 Evidence — authoritative Scrum state persistence

Date: 2026-08-11

Implementation base: `5e5fac547659` (`docs: define durable Scrum state slices`), a plan-only
descendant of reviewed Task 4 head `11f3663`.

Verification head: the Task 5 working tree based on `5e5fac547659`. This evidence file is part of
the required commit, so its commit hash cannot truthfully be recorded before that commit is made.
The required exact subject is `feat(v2): persist authoritative scrum state`.

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
- persisted durations are true SQLite integers in `0..2^63 - 1`, never booleans or reals;
- factor/unit fractions are finite and bounded to `[0, 1]`; sampled hours are finite and
  non-negative;
- aware instants normalize to UTC; naive instants reject.

`ScrumStateWriteSet` contains only complete after-images. `ScrumStateSnapshot` contains only
detached domain values in deterministic semantic order. Neither type carries SQLAlchemy state,
callables, external intents, lifecycle decisions, allocation behavior, or counter-claim behavior.

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
adapter. `add` recursively validates the complete write set before the first SQL statement, inserts
only Task 5 state, flushes inside the caller transaction, and returns a detached snapshot. `load`
returns the same state in deterministic semantic order.

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

The exact outputs are retained beside this README. No staging, commit, push, deployment, live-system
access, Jira/OpenAI access, UAT, Task 6 implementation, or revision 016 occurred during verification.

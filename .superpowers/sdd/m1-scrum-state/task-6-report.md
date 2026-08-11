# Task 6 implementation report — commit authoritative Scrum state atomically

## Status

Implementation, strict TDD, verification, documentation, and the bounded non-Ultra precommit audit
are complete on reviewed base `b449ca0`. The exact task commit subject is
`feat(v2): commit scrum state atomically`. Independent technical review remains pending; Task 6 and
M1 therefore remain open. No live system, deployment, push, UAT, or external provider was used.

## Implemented behavior

Task 6 adds four immutable public values:

- `SemanticCounterClaim(scope, expected_next, count)` with strict safe-integer half-open ranges;
- `EligibleNaturalDecisionClaim(decision, business_date)` for the two approved natural owner types;
- `AuthoritativeTickSliceCommit`, which wraps the existing live slice, sparse Task 5 after-images,
  counter claims, and eligible natural decisions;
- `CommittedAuthoritativeTickSlice`, which returns the existing committed live slice, complete
  detached state, claimed counter results, and resolved natural evaluations.

`SqlAlchemyV2UnitOfWork.commit_authoritative_slice` requires the exact immutable command and
revalidates it before the session factory is called. One short transaction performs runtime CAS,
Task 5 after-images, zero child-counter seeds for newly inserted owners, semantic-counter CAS,
natural eligibility resolution, existing activity/ground-truth/projection persistence, final flush,
and one commit. Every exception owns one rollback. The existing `commit_tick_slice` remains public
and shares only private runtime/ledger helpers; it is never called from the new UOW operation.

The mapper distinguishes persisted sparse after-images from declared new allocations. Claims bind
only exact contiguous new coordinates and semantic IDs. If an unclaimed ordinal proves missing in
the database, the slice raises typed `StaleSemanticCounter` and rolls back. New work items seed visit
and cancellation counters at zero, and new members seed member-unavailability counters at zero, so
first claims may occur in a later transaction or after restart. Missing/deleted established counters
are never recreated. Sprint planning coordinates and all existing immutable Task 5 records remain
conflict-checked. Natural replay is monotonic and cannot double-consume or regress a counter.

Projection delivery stays outside the transaction. No allocator, transition, lifecycle engine,
scheduler, Jira/OpenAI client, probability/eligibility logic, migration `016`, API, or frontend was
added.

## Files

Production:

- `backend/app/v2/domain/authoritative_slice.py` (new)
- `backend/app/v2/domain/__init__.py`
- `backend/app/v2/persistence/scrum_state_mapper.py`
- `backend/app/v2/persistence/unit_of_work.py`
- `backend/app/v2/persistence/__init__.py`

Tests/support:

- `backend/tests/v2/authoritative_slice_support.py` (new)
- `backend/tests/v2/unit/test_authoritative_slice.py` (new)
- `backend/tests/v2/integration/test_authoritative_unit_of_work.py` (new)
- `backend/tests/v2/integration/test_projection_boundary.py`
- `backend/tests/v2/unit/test_architecture_boundaries.py`

Evidence/documentation:

- `evidence/v2/M1-T06/*`
- `README.md`, `changelog.md`, `assumptions.md`, `agent_instruction.md`
- `backlog/v2/README.md`, `backlog/v2/m1-scrum-state.md`
- `.superpowers/sdd/m1-scrum-state/task-6-report.md`

Revision 015 and every earlier migration are byte-for-byte unchanged from `b449ca0`.

## RED → GREEN → REFACTOR

The complete focused tests existed before production. Exact RED command from `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_authoritative_slice.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T06/red.txt
```

Exact expected result: exit non-zero, three collection errors in 0.36s. The unit, UOW integration,
and projection-boundary tests all failed because `app.v2.domain.authoritative_slice` did not exist.
This directly witnessed the missing Task 6 interface.

The identical final GREEN command, with only `red.txt` replaced by `green.txt`, produced 189 passed
in 13.95s.

Three supplemental review-driven cycles were also witnessed before their production changes:

1. Sparse allocation/claim/replay/immutability/public-type regressions: 11 failed/82 deselected in
   0.93s → 11 passed/82 deselected in 0.74s.
2. Owner-only child-counter persistence: 2 failed, 1 passed/46 deselected in 0.36s → 3 passed/46
   deselected in 0.36s.
3. Deleted sprint/item counter recreation: 2 failed/49 deselected in 0.32s → 2 passed/49 deselected
   in 0.40s.

After GREEN, the mapper/test helpers were decomposed until the retained AST scan reported all eight
touched/new Python files at no more than 30 lines per function and three arguments. Focused tests and
Ruff remained green.

## Atomicity, restart, and isolation evidence

- Successful SQL ordering is asserted from the runtime update through every state class, counter
  update, natural evaluation, all three ledgers, and final flush.
- The final atomic/stale/conflict selection is 33 passed, 18 deselected in 2.27s. Independent
  injection covers runtime, each Task 5 write class, counter updates/seeds, natural insert, activity,
  ground truth, projection, final flush, and commit. Fresh reads equal the exact pre-slice state.
- Winner/loser UOWs prove runtime and counter CAS reject stale writers without loser state or ledgers.
- Disabled/ineligible/absent natural claims consume nothing; successful claims consume once; failure
  after counter advance creates no gap.
- Identical replay returns existing immutable rows and current monotonic counters. Differing state,
  eligibility/occurrence, or canonical evidence raises its typed conflict and rolls back.
- The final restart selection is 2 passed, 49 deselected in 0.45s. A disposed engine reloads exact
  runtime, complete state, samples/provenance, counter values, eligibility assignments, append
  cursors, and pending intents, then continues occurrence allocation.
- An exploding adapter runs only after commit returns and cannot undo any persisted class.
- V1 tables/routes remain unchanged/invisible, cold imports still register all v2 tables, and Task 6
  adds no migration.

## Final verification

Final retained results after the last production change:

- Task 1 focused: 62 passed, 1 baseline warning in 1.58s.
- Task 2 accepted focused: 197 passed in 11.73s; its original four-file command also passed 176.
- Task 3 focused: 257 passed in 0.50s.
- Task 4 focused: 152 passed in 0.34s.
- Task 5 focused: 338 passed in 17.42s.
- Task 6 focused: 189 passed in 13.95s.
- All v2: 974 passed, 1 baseline warning in 24.42s.
- Single fresh full backend: 1492 passed, 43 skipped, 15 warnings in 52.33s.
- Ruff: all checks passed.
- Static architecture/import boundary: 67 passed in 10.06s.
- Function/argument scan: clean for eight files at `<=30` lines and `<=3` arguments.
- Populated revision-015 migration round trip/parity: 4 passed in 1.68s.
- Alembic: sole `015 (head)`, empty branches, linear 001→015 history.
- `git diff --exit-code b449ca0 -- backend/alembic/versions`: empty, exit 0.
- Repository and staged diff checks: clean before commit.

Warnings are the existing inventory: one Starlette/httpx deprecation, thirteen unawaited-AsyncMock
warnings in the frozen Jira bootstrap tests, and one SQLAlchemy identity warning. The 43 skipped
integration tests are expected with `INTEGRATION_TESTS=false`. No test was weakened or warning
suppressed.

## Self-review

The bounded non-Ultra audit initially found sparse allocation handling, later owner-counter use,
natural replay, immutable sprint planning, and exact public-boundary defects. Each became a witnessed
RED and was fixed. A second pass found claim-time recreation of deleted team counters; its two-case
RED led to removal of all claim-time counter creation. The final audit reported CLEAN and ran five
targeted counter lifecycle probes successfully.

The final diff was checked for transaction ownership, exact error translation, deterministic order,
semantic-ID/range binding, new-owner seed authorization, deleted-counter staleness, replay
monotonicity, adapter/import isolation, no migration, function/argument shape, and documentation
truthfulness. No Critical or Important concern remains from the bounded audit.

## Concerns

No implementation concern is known. Independent technical review is still required before Task 6
or this plan is marked complete. M1 remains in progress, and no next slice was inferred.

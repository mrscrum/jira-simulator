# Task 6 implementation report — commit authoritative Scrum state atomically

## Status

The original Task 6 implementation is commit `4cfaa65` (`feat(v2): commit scrum state atomically`).
Review-fix round 1 is commit `6bac956` (`fix(v2): enforce authoritative after-image identity`).
Review-fix round 2 is commit `47f9e55` (`fix(v2): normalize authoritative result instants`). Its
verification matrix and direct probe are GREEN, and the independent Ultra technical review reported
CLEAN with no Critical or Important findings. Task 6 and this plan are complete; M1 remains in
progress and no next detailed slice was inferred. No live system, deployment, push, UAT, or external
provider was used.

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
and cancellation counters at zero so first claims may occur later or after restart. Blueprint
members and their unavailable-member counters are established by Task 5/bootstrap; Task 6 rejects
missing established members and never recreates their identity or counter history. Missing/deleted
established counters are never recreated. Sprint planning coordinates and all existing immutable
Task 5 records remain conflict-checked. Natural replay is monotonic and cannot double-consume or
regress a counter.

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

## Original Task 6 verification

Results retained after the original Task 6 implementation:

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

## Original implementation self-review

The bounded non-Ultra audit initially found sparse allocation handling, later owner-counter use,
natural replay, immutable sprint planning, and exact public-boundary defects. Each became a witnessed
RED and was fixed. A second pass found claim-time recreation of deleted team counters; its two-case
RED led to removal of all claim-time counter creation. The final audit reported CLEAN and ran five
targeted counter lifecycle probes successfully.

The final diff was checked for transaction ownership, exact error translation, deterministic order,
semantic-ID/range binding, new-owner seed authorization, deleted-counter staleness, replay
monotonicity, adapter/import isolation, no migration, function/argument shape, and documentation
truthfulness. No Critical or Important concern remains from the bounded audit.

## Original implementation concerns

No implementation concern was known at the original-implementation checkpoint. Independent review
was still required then; the final accepted outcome is recorded in the review-fix sections below.

## Review fix round 1 — authoritative after-image identity

### RED

All review regressions were added before production edits. The exact five-file Task 6 command shown
above, targeting `fix-round-1-red.txt`, exited non-zero with `32 failed, 199 passed in 21.04s`.
Failures covered global/composite row theft, forbidden coordinate mutation for every mutable model,
advanced-claim state/ledger/natural replay, deleted established-member recreation, malformed nested
committed results, contradictory result membership, and visible owner-kind cross-binding before
session creation. A corrected five-case scope selection separately witnessed `1 failed, 4
deselected`, then `1 passed, 4 deselected` after the production guard was restored.

### GREEN and behavior

The identical focused command targeting `fix-round-1-green.txt` produced `231 passed in 19.61s`.
The repair freezes the required ownership/history coordinates for overlay, consumption, work,
sprint, scope, and visit after-images; member, factor, and sample remain fully immutable. Any advanced
allocation claim now authenticates the entire replay: all allocation claims must already be
consumed, all supplied after-images and natural occurrences must exist exactly, and every submitted
ledger semantic key must resolve to identical persisted content. A changed or mixed replay raises a
typed stale/semantic conflict and the runtime CAS rolls back with every state and ledger write.

Task 6 no longer inserts a missing member or resets its natural counter. Returned runtime/ledger
values are deeply revalidated, and unique returned counter/evaluation values must be exact members
of the complete snapshot. Visible natural-owner cross-binding rejects before the session factory.
The bounded non-Ultra post-GREEN audit independently rechecked all six seams and reported CLEAN.

### Final verification

- Task 1: 62 passed, 1 baseline warning; Task 2: 197 passed; Task 3: 257 passed; Task 4:
  152 passed; Task 5: 338 passed; Task 6: 231 passed.
- All v2: 1016 passed, 1 baseline warning in 30.34s.
- Single fresh full backend after the final production change: 1534 passed, 43 skipped, exactly 15
  baseline warnings in 58.64s.
- Atomic stale/conflict/rollback selection: 48 passed, 26 deselected; disposed-engine restart:
  1 passed, 73 deselected.
- Ruff: all checks passed. Static import/architecture: 67 passed. Migration parity/round trip,
  cold import, restart, and adapter boundary: 49 passed.
- Shape: six changed Python files, no function over 30 lines or three arguments.
- Alembic: sole 015 head, empty branches, fresh upgrade/current at 015; migration diff from
  `4cfaa65` empty.
- `git diff --check` reported no whitespace errors. No test, warning, or scope was weakened.

## Review fix round 2 — normalize authoritative result instants

### RED

Before production edits, direct construction and `dataclasses.replace` were parameterized over
`TeamRuntime.simulation_time`, `next_wake_at`, `created_at`, and `updated_at`, plus every activity,
ground-truth, and projection `recorded_at`. Equivalent aware `+05:30` values were required to retain
the same instant with `tzinfo is datetime.UTC`; the existing naive rejection cases remained.

Exact command from `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_authoritative_slice.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T06/fix-round-2-red.txt
```

Expected RED: `14 failed, 238 passed in 19.78s`. All fourteen offset cases proved that the prior
result validator accepted aware instants but retained their submitted `+05:30` representation.
Naive-instant and UOW cases remained green.

### GREEN and behavior

The identical command targeting `fix-round-2-green.txt` produced `252 passed in 20.46s`.
`CommittedAuthoritativeTickSlice` now immutably rebuilds the exact nested `TeamRuntime` and ledger
records, normalizing every aware instant to `datetime.UTC` before retaining and deeply validating
the result. Original caller values stay unchanged, normal frozen/slotted mutation rejection remains,
and naive datetimes still raise `ValueError`. Successful UOW, disposed-engine reload, and continued
commit results all assert exact UTC on the detached runtime and every returned ledger row.

The direct probe covered all seven paths and reported
`normalized_paths=7 input_unchanged=true result_frozen=true`.

### Final verification

- Task 1: 62 passed, 1 baseline warning; Task 2: 197 passed; Task 3: 257 passed; Task 4:
  152 passed; Task 5: 338 passed; Task 6: 252 passed.
- All v2: 1037 passed, 1 baseline warning in 33.34s.
- Single fresh full backend after the final production change: 1555 passed, 43 skipped, exactly 15
  baseline warnings in 61.60s.
- Ruff: all checks passed. Migration parity/round trip, cold import, restart, and adapter boundary:
  49 passed in 13.66s.
- Shape: three changed Python files, no function over 30 lines or three arguments.
- Alembic: sole 015 head, empty branches, fresh upgrade/current at 015; migration diff from
  `6bac956` empty.
- `git diff --check` reported no whitespace errors. No test, warning, migration, or scope was
  weakened.

### Self-review and concerns

The verification matrix and direct probe confirmed exact-UTC normalization for all seven nested
paths, unchanged caller-owned values, and preserved frozen result behavior. The final diff was
checked for exact nested types, naive rejection, immutable reconstruction, restart behavior, no
migration, and scope isolation. No implementation concern is known. The subsequent independent
Ultra technical review reported CLEAN with no Critical or Important findings, so Task 6 and this
plan are complete. M1
stays in progress, and no next detailed slice was inferred.

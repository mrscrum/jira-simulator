# M1-T06 Evidence — atomic authoritative Scrum slices

## Scope and provenance

- Date: 2026-08-11
- Original Task 6 commit: `4cfaa65` (`feat(v2): commit scrum state atomically`)
- Review-fix round 1 commit: `6bac956` (`fix(v2): enforce authoritative after-image identity`)
- Review-fix round 2 base: `6bac956`
- Exact round-2 subject: `fix(v2): normalize authoritative result instants`
- Alembic remains at sole linear head `015`; Task 6 creates no revision `016`.
- The round-2 verification matrix and direct probe are GREEN. Independent Ultra re-review remains
  pending, so Task 6 and M1 remain open.
- No Jira/OpenAI/provider call, projection delivery, deployment, push, UAT, or live mutation ran.

Task 6 adds immutable authoritative command/result values and one atomic SQLAlchemy operation. The
transaction order is runtime CAS, sparse Scrum after-images and authorized work-owner zero-counter
seeds,
semantic-counter CAS, natural-eligibility resolution, activity/ground-truth/pending-intent appends,
final flush, and one commit. The existing `commit_tick_slice` and post-commit adapter boundary remain
compatible.

## Strict TDD evidence

The complete focused tests were written before Task 6 production code. From `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_authoritative_slice.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T06/red.txt
```

Expected RED: exit non-zero with three collection errors in 0.36s. All three were
`ModuleNotFoundError: No module named 'app.v2.domain.authoritative_slice'` from the new unit,
integration, and projection-boundary tests. This was the intended missing Task 6 interface, not an
existing Task 1–5 regression. See `red.txt`.

The identical final GREEN command, changing only the output file to `green.txt`, produced:

```text
189 passed in 13.95s
```

Review-driven TDD cycles were retained rather than rewriting the historical RED:

- `adversarial-red.txt`: 11 failed, 82 deselected in 0.93s. The failures exposed sparse existing
  after-images being treated as allocations, mixed old/new ranges, missing owner-counter
  initialization, duplicate natural scopes, older replay regression, mutable sprint plans, and a
  duck-typed public command. `adversarial-green.txt`: 11 passed, 82 deselected in 0.74s.
- `owner-counter-red.txt`: 2 failed, 1 passed, 46 deselected in 0.36s because owner-only slices did
  not persist their zero-valued child counters. `owner-counter-green.txt`: 3 passed, 46 deselected
  in 0.36s, including disposed-engine later claims, rollback, and deleted-child non-recreation.
- `team-counter-red.txt`: 2 failed, 49 deselected in 0.32s because deleted sprint/item counters were
  silently recreated. `team-counter-green.txt`: 2 passed, 49 deselected in 0.40s after removing all
  claim-time counter creation.

## Behavioral proof

- Exact command validation happens before requesting a session; forged nested claims/state,
  wrong coordinates, unsafe integers, wrong team/run, and duck-typed commands leave every row
  unchanged. The retained selection is `validation-before-session.txt` (29 passed).
- A successful slice advances runtime `0 -> 1`, applies every representative Task 5 write class,
  advances only exact claimed counters, stores eligible business-date assignments, and appends both
  records in each existing ledger with transaction positions `0, 1`.
- Sparse after-images for existing sprint/item/visit rows consume no range. A claim covers only its
  new contiguous coordinates, allowing existing and new rows in one scope. Persistence proves an
  unclaimed missing ordinal is new and raises typed `StaleSemanticCounter` before commit.
- New work-item owners receive visit and cancellation counters at zero. Blueprint members and their
  unavailable-member counters are established by Task 5/bootstrap before Task 6; Task 6 rejects a
  missing member rather than recreating its identity or resetting its counter. Seeds consume no
  occurrence, survive restart, and support a later first claim. Missing/deleted established child
  or team counters remain stale.
- Identical state, ledger, and natural eligibility replay is a no-op for immutable rows. Older
  eligibility replay after later occurrences returns the stored assignment without decrementing or
  consuming the counter again. Differing immutable content raises the typed state, natural, or
  evidence conflict and rolls back the slice.
- `atomic-failure-matrix.txt` is the final post-refactor selection: 33 passed, 18 deselected in
  2.27s. It covers runtime/state/counter/natural/ledger/final-flush/commit failures, stale writers,
  typed conflicts, deleted counters, and full rollback/no-gap behavior.
- `restart-continuation.txt` is the final post-refactor selection: 2 passed, 49 deselected in 0.45s.
  A disposed engine reloads exact state, counters, eligibility, provenance, cursors, and pending
  intents, then continues at the next occurrence.
- The exploding projection adapter is called only after commit returns. Its failure cannot mutate
  runtime, the complete Scrum snapshot, counters/evaluations, or any ledger. Static tests prove both
  UOW methods import/call no adapter or external client.

## Original Task 6 verification

All commands ran from `backend/` with `set -o pipefail`, `PYTHONDONTWRITEBYTECODE=1`,
`INTEGRATION_TESTS=false`, `python -B`, and `-p no:cacheprovider` where applicable.

| Verification | Retained result |
|---|---|
| Task 1 focused | 62 passed, 1 baseline warning in 1.58s (`task1.txt`) |
| Task 2 accepted focused, including architecture | 197 passed in 11.73s (`task2-focused.txt`) |
| Task 2 original four-file command | 176 passed in 11.63s (`task2.txt`) |
| Task 3 focused | 257 passed in 0.50s (`task3.txt`) |
| Task 4 focused | 152 passed in 0.34s (`task4.txt`) |
| Task 5 focused | 338 passed in 17.42s (`task5.txt`) |
| Task 6 focused | 189 passed in 13.95s (`green.txt`) |
| All v2 | 974 passed, 1 baseline warning in 24.42s (`all-v2.txt`) |
| Full safe backend | 1492 passed, 43 skipped, 15 baseline warnings in 52.33s (`full.txt`) |
| Ruff | `All checks passed!` (`ruff.txt`) |
| Static import/architecture boundary | 67 passed in 10.06s (`static-boundaries.txt`) |
| Function/argument shape | 8 files; maximum 30 lines and 3 arguments (`function-shape.txt`) |
| Populated 014→015→014→015 / ORM parity | 4 passed in 1.68s (`alembic-roundtrip.txt`) |
| Alembic heads | `015 (head)` (`alembic-heads.txt`) |
| Alembic branches | empty output, exit 0 (`alembic-branches.txt`) |
| Alembic history | linear 001→015 (`alembic-graph.txt`) |
| Migration diff from `b449ca0` | empty output, exit 0 (`no-migration-diff.txt`) |

The full-suite warning inventory is unchanged: one Starlette/httpx deprecation warning, thirteen
pre-existing `jira_bootstrapper` unawaited-`AsyncMock` warnings, and one pre-existing SQLAlchemy
identity warning. The 43 normal integration skips remain expected because live integration tests
were disabled. No warning was suppressed or fixed outside Task 6 scope.

## Review fix round 1

The six Ultra findings were converted into focused regressions before production changes. From
`backend/`, the consolidated RED command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_authoritative_slice.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T06/fix-round-1-red.txt
```

Expected RED: `32 failed, 199 passed in 21.04s`. The failures proved global/composite row theft,
mutable advanced replay, missing-member recreation, shallow committed-result validation,
contradictory returned counter/evaluation membership, and visible natural-owner cross-binding. A
corrected five-case scope selection was separately witnessed at `1 failed, 4 deselected`, then
`1 passed, 4 deselected` after restoring the guard. No historical RED was rewritten.

The identical consolidated command targeting `fix-round-1-green.txt` produced `231 passed in
19.61s`. The repair now:

- freezes every reviewed after-image identity/history coordinate while retaining explicitly mutable
  operational fields;
- treats any advanced allocation claim as whole-command replay, requiring every supplied state row,
  allocation claim, natural occurrence, and ledger draft to be already persisted and exact;
- rejects missing established blueprint members instead of reconstructing identity/counter history;
- deeply revalidates runtime and exact ledger result elements, and requires every returned unique
  counter/evaluation to be an exact member of the complete snapshot; and
- rejects visible cancellation-to-member and member-unavailability-to-work cross-binding before a
  session factory is called.

Final post-audit verification:

| Verification | Retained result |
|---|---|
| Task 1 focused | 62 passed, 1 baseline warning in 2.06s (`fix-round-1-task1-focused.txt`) |
| Task 2 accepted focused | 197 passed in 13.87s (`fix-round-1-task2-focused.txt`) |
| Task 3 focused | 257 passed in 0.79s (`fix-round-1-task3-focused.txt`) |
| Task 4 focused | 152 passed in 0.53s (`fix-round-1-task4-focused.txt`) |
| Task 5 focused | 338 passed in 20.48s (`fix-round-1-task5-focused.txt`) |
| Task 6 focused | 231 passed in 19.61s (`fix-round-1-green.txt`) |
| Atomic stale/conflict/rollback matrix | 48 passed, 26 deselected in 4.83s (`fix-round-1-atomic-matrix.txt`) |
| Disposed-engine restart | 1 passed, 73 deselected in 0.32s (`fix-round-1-restart.txt`) |
| All v2 | 1016 passed, 1 baseline warning in 30.34s (`fix-round-1-all-v2.txt`) |
| Single fresh full backend | 1534 passed, 43 skipped, 15 baseline warnings in 58.64s (`fix-round-1-full.txt`) |
| Ruff | `All checks passed!` (`fix-round-1-ruff.txt`) |
| Static import/architecture boundary | 67 passed in 13.41s (`fix-round-1-static-boundaries.txt`) |
| Migration parity/round trip, cold import, restart, adapter boundary | 49 passed in 14.12s (`fix-round-1-boundaries.txt`) |
| Function/argument shape | 6 Python files; no function over 30 lines or 3 arguments (`fix-round-1-code-shape.txt`) |
| Alembic | sole `015 (head)`, empty branches, fresh upgrade/current at 015 (`fix-round-1-alembic-graph.txt`) |
| Migration diff from `4cfaa65` | empty, exit 0 (`fix-round-1-no-migration-diff.txt`) |

The warning inventory remains exactly the documented baseline. The required bounded non-Ultra
post-GREEN audit reported CLEAN after rechecking identity theft, whole-slice replay, member/counter
non-resurrection, result validation/membership, and visible owner binding. No external or live call,
revision 016, deployment, push, or UAT occurred.

## Review fix round 2

The single Ultra finding was converted into direct-construction, `dataclasses.replace`, and
disposed-engine regressions before production edits. From `backend/`, the consolidated RED command
was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_authoritative_slice.py tests/v2/integration/test_authoritative_unit_of_work.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T06/fix-round-2-red.txt
```

Expected RED: `14 failed, 238 passed in 19.78s`. Each failure retained an equivalent aware
`+05:30` value in the submitted offset instead of normalizing it to exact UTC. The existing naive
instant rejection and integration cases remained green. No historical RED was changed.

The identical command targeting `fix-round-2-green.txt` produced `252 passed in 20.46s`.
`CommittedAuthoritativeTickSlice` now rebuilds its exact frozen nested `TeamRuntime`,
`ActivityEvent`, `GroundTruthRecord`, and `ProjectionIntent` values with every aware instant
normalized to `datetime.UTC` before retaining and deeply validating the committed result. The
caller-supplied frozen values are not mutated, naive values still reject, and exact nested types
remain required. Disposed-engine reload and continuation assert the same exact-UTC contract.

The direct immutable probe covered all seven paths and reported
`normalized_paths=7 input_unchanged=true result_frozen=true`.

Final retained verification:

| Verification | Retained result |
|---|---|
| Task 1 focused | 62 passed, 1 baseline warning in 2.96s (`fix-round-2-task1-focused.txt`) |
| Task 2 accepted focused | 197 passed in 17.04s (`fix-round-2-task2-focused.txt`) |
| Task 3 focused | 257 passed in 0.95s (`fix-round-2-task3-focused.txt`) |
| Task 4 focused | 152 passed in 0.61s (`fix-round-2-task4-focused.txt`) |
| Task 5 focused | 338 passed in 24.53s (`fix-round-2-task5-focused.txt`) |
| Narrow UTC normalization selection | 21 passed, 66 deselected in 0.20s (`fix-round-2-unit-green.txt`) |
| Task 6 focused | 252 passed in 20.46s (`fix-round-2-green.txt`) |
| All v2 | 1037 passed, 1 baseline warning in 33.34s (`fix-round-2-all-v2.txt`) |
| Single fresh full backend | 1555 passed, 43 skipped, 15 baseline warnings in 61.60s (`fix-round-2-full.txt`) |
| Direct immutable normalization probe | 7 paths normalized; input unchanged; result frozen (`fix-round-2-direct-probe.txt`) |
| Touched-file Ruff | `All checks passed!` (`fix-round-2-ruff-touched.txt`) |
| Ruff | `All checks passed!` (`fix-round-2-ruff.txt`) |
| Migration parity/round trip, cold import, restart, adapter boundary | 49 passed in 13.66s (`fix-round-2-boundaries.txt`) |
| Function/argument shape | 3 Python files; no function over 30 lines or 3 arguments (`fix-round-2-code-shape.txt`) |
| Alembic | sole `015 (head)`, empty branches, fresh upgrade/current at 015 (`fix-round-2-alembic-graph.txt`) |
| Migration diff from `6bac956` | empty, exit 0 (`fix-round-2-no-migration-diff.txt`) |

The full-suite warning inventory remains exactly the documented baseline. No migration, external or
live call, deployment, push, UAT, or M1 completion was added.

## Files under test

- `backend/app/v2/domain/authoritative_slice.py`
- `backend/app/v2/domain/__init__.py`
- `backend/app/v2/persistence/scrum_state_mapper.py`
- `backend/app/v2/persistence/unit_of_work.py`
- `backend/app/v2/persistence/__init__.py`
- `backend/tests/v2/authoritative_slice_support.py`
- `backend/tests/v2/unit/test_authoritative_slice.py`
- `backend/tests/v2/integration/test_authoritative_unit_of_work.py`
- `backend/tests/v2/integration/test_projection_boundary.py`
- `backend/tests/v2/unit/test_architecture_boundaries.py`

No migration, engine/scheduler, Jira/API/frontend, or provider file changed.

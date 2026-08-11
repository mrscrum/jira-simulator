# M1-T06 Evidence — atomic authoritative Scrum slices

## Scope and provenance

- Date: 2026-08-11
- Reviewed base: `b449ca0`
- Exact task commit subject: `feat(v2): commit scrum state atomically`
- Alembic remains at sole linear head `015`; Task 6 creates no revision `016`.
- The bounded non-Ultra precommit audit is clean. Independent technical review remains pending, so
  Task 6 and M1 remain open.
- No Jira/OpenAI/provider call, projection delivery, deployment, push, UAT, or live mutation ran.

Task 6 adds immutable authoritative command/result values and one atomic SQLAlchemy operation. The
transaction order is runtime CAS, sparse Scrum after-images and new-owner zero-counter seeds,
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
- New work-item owners receive visit and cancellation counters at zero; new member owners receive
  member-unavailability counters at zero. Seeds consume no occurrence, survive restart, and support a
  later first claim. Missing/deleted established child or team counters remain stale.
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

## Final verification

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

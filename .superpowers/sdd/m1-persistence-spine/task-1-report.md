# M1 Task 1 report — isolated resolved team/runtime shell

## Implemented behavior

- `ResolvedTeamBlueprint` accepts only byte-for-byte canonical resolved Scrum snapshots and rejects
  non-finite JSON, extra/missing sections, Kanban, and missing timing/risk materialization.
- Canonical JSON, SHA-256, and fixed-namespace UUIDv5 helpers derive team, blueprint, run, and
  runtime identities deterministically.
- `UTCDateTime` rejects naive values, normalizes aware values to UTC, and restores UTC tzinfo.
- Revision 013 creates `v2_teams`, `v2_team_blueprints`, `v2_runs`, and `v2_team_runtimes` in FK-safe
  order; downgrade removes them in exact reverse order.
- The create service validates before using persistence. The repository uses one session-factory
  transaction, returns detached domain values, is idempotent for same key/hash, conflicts for a
  different hash, and rolls back an injected final insert failure.

## Files

- `backend/app/v2/{domain,persistence,application}/` — domain contracts, adapter, and service.
- `backend/alembic/versions/013_add_v2_team_spine.py` — additive migration/downgrade.
- `backend/tests/v2/` — canonical, UTC, service, boundary, repository, and migration coverage.
- `evidence/v2/M1-T01/` — command output and short evidence record.

## TDD evidence

RED command (executed from `backend/` with `set -o pipefail`):

```bash
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T01/red.txt
```

Output: four collection errors, each `ModuleNotFoundError: No module named 'app.v2'`; this was the
expected missing implementation, not a fixture/setup failure.

GREEN used the identical command. Output: `19 passed in 0.38s`.

## Full verification

- Full safe backend suite: `537 passed, 43 skipped, 15 warnings in 26.61s`.
- Ruff: `All checks passed!`.
- Alembic disposable SQLite graph: sole head `013`, parent `012`; history is linear through `001`.
- Migration test proves `012 -> 013 -> 012` leaves the legacy table set unchanged and removes all
  four v2 tables.
- Repository test proves one row in each table, detached reload, idempotent replay/conflict, and
  rollback after an injected final insert failure.

## Self-review

- Confirmed the only legacy source edit is additive mapping registration in `app.models.__init__`.
- AST coverage prevents v2 imports from `app.engine`, `app.integrations`, and legacy model symbols.
- No live Jira/OpenAI call, deployment, push, UAT state, or migration 014 was performed.

## Concerns

- The full suite retains the pre-existing 15 warnings recorded in the baseline; this task did not
  broaden scope to change them.

## Fix round 1 — 2026-08-10

### Review findings resolved

- Replaced nested `dict`/`list` blueprint state with explicit frozen Pydantic models, tuples, and
  immutable mappings. Nested extras and mutation now fail.
- Added UTC-only validation for the first Scrum boundary and configured availability instants,
  plus ordered/non-overlapping interval validation.
- Added route/status/activity, staffed-responsibility, timing-grid, timing-anchor, issue-type, and
  risk materialization validation.
- Made idempotency conflict coverage assert `TeamCreationConflict` specifically.
- Replaced the nominal restart with disposal plus a new engine/session factory, and replaced the
  pre-flush monkeypatch with failure on the actual final runtime INSERT.
- Added one legacy Team and proved both `select(Team)` and `GET /teams` remain v1-only while v2
  reload remains available.
- Replaced table-name-only migration coverage with a row in every revision-012 legacy table and
  exact ordered row plus column/index/FK metadata comparison across `012 -> 013 -> 012 -> 013`.
- Split repository and migration helpers; the recorded AST check finds no touched/new function over
  30 lines.

### RED / GREEN / verification

- RED command: focused blueprint/service tests. `fix-round-1-red-blueprint.txt` records 11 failures
  for the missing deep type/freeze, nested validation, UTC, materialization, and cross-field rules.
- A separate single-test RED showed the newly required `team.purpose` was rejected as an extra
  field before it was added to the resolved contract.
- GREEN exact Task 1 command: `31 passed, 1 warning in 1.07s`.
- Full safe backend suite: `549 passed, 43 skipped, 15 warnings in 27.23s`.
- Ruff: `All checks passed!`; Alembic: sole head `013`, no branch, linear history.
- Evidence files: `fix-round-1-green.txt`, `fix-round-1-full-suite.txt`, and
  `fix-round-1-verification.txt` contain the exact outputs.

### Self-review and concerns

- Confirmed revision 013 remains additive and its reverse downgrade owns only the four v2 tables.
- Confirmed no Task 2/migration 014, live provider, deployment, push, or UAT work entered the diff.
- The full suite retains only the documented 15 baseline warnings.

## Fix round 2 — 2026-08-10

### Review findings resolved

- Replaced UTC-only blueprint validation with aware-instant validation followed by UTC
  normalization. Valid `-07:00` Scrum and member-availability instants now construct successfully;
  naive versions still fail.
- Canonicality is checked against the parsed submitted JSON before typed datetime normalization.
  The validated original canonical document is retained for byte-for-byte re-encoding, persistence,
  and SHA-256 identity, while the typed datetime values are UTC.
- Added domain and service regressions for all three offset instants, normalized typed values,
  unchanged canonical bytes, and the hash of the submitted canonical value.

### RED / GREEN

RED command, run from `backend/` with `set -o pipefail`:

```bash
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_create_team.py -q 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-red.txt
```

Exact result: `2 failed, 23 passed in 0.22s`. Both failures were expected: `_require_utc` rejected
the valid `2026-08-13T09:00:00-07:00`, `2026-08-20T09:00:00-07:00`, and
`2026-08-20T17:00:00-07:00` inputs as “instant must be aware UTC.”

GREEN exact Task 1 command:

```bash
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-green.txt
```

Exact result: `33 passed, 1 warning in 1.27s`.

### Full verification and evidence

- Full command: `PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m
  pytest -p no:cacheprovider tests -q 2>&1 | tee
  ../evidence/v2/M1-T01/fix-round-2-full-suite.txt`.
- Exact full result: `551 passed, 43 skipped, 15 warnings in 27.23s`.
- Ruff command: `../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee
  ../evidence/v2/M1-T01/fix-round-2-ruff.txt`; exact result: `All checks passed!`.
- Alembic `heads --verbose` reported `Rev: 013 (head)` with parent `012`; `branches --verbose`
  produced no branch; `history` remained linear from `001` through `013`.
- On one fresh disposable SQLite URL, `upgrade 012`, `upgrade 013`, `downgrade 012`, `upgrade 013`,
  and `current --verbose` all exited zero; the final exact current result was `Rev: 013 (head)`.
- The AST scan over Python files changed since `91fe2acf8a860e4a4cc764b9b3ac435bc6fd16d5`
  printed exactly `Functions over 30 lines: []`.
- `evidence/v2/M1-T01/README.md` now records the exact focused/full/Ruff/Alembic graph and
  round-trip/function-scan commands actually run, their exact results, and the boundary between the
  fresh CLI migration proof and the populated migration integration proof.

### Self-review and concerns

- Confirmed canonical byte/hash identity still distinguishes canonical offset spellings even when
  they represent the same UTC instant; this follows the brief's input-byte identity rule.
- Confirmed the repository suite still reloads the canonical fixture; the new offset-specific
  canonical/typed/hash behavior is covered directly in the domain and service unit tests.
- Confirmed no migration, Task 2, Jira/OpenAI, deployment, push, or UAT change entered this round.
- The full suite retains only the documented 15 baseline warnings.

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

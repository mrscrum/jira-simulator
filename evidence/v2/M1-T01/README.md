# M1-T01 — Isolated team runtime shell

- Date: 2026-08-10; environment: Python 3.12, SQLite, SQLAlchemy 2, Pydantic 2, Alembic; no live providers.
- RED: the exact mandated command failed with four `ModuleNotFoundError: No module named 'app.v2'`
  collection errors. Fixture/test setup was present; only the v2 package was missing.
- GREEN: the identical command passed `19 passed in 0.38s`.
- Full suite: `537 passed, 43 skipped, 15 warnings in 26.61s`; the 15 documented baseline warnings
  were preserved. Ruff: `All checks passed!`.
- Migration: disposable SQLite Alembic reports sole head `013`; integration coverage proves
  `012 -> 013 -> 012` table reversibility. Repository coverage proves atomic rows, replay/conflict,
  reload, and rollback after an injected final insert failure.

Exact output is retained in `red.txt`, `green.txt`, `full-suite.txt`, and `verification.txt`.

## Fix round 1

- RED: `fix-round-1-red-blueprint.txt` records 11 expected failures proving the initial nested
  snapshot was mutable/untyped and accepted nested extras, non-UTC instants, missing materialized
  grid cells, bad anchors, broken route/activity references, and overlapping availability.
- GREEN: the exact Task 1 focused command now passes `31 passed, 1 warning in 1.07s` in
  `fix-round-1-green.txt`.
- Full suite: `549 passed, 43 skipped, 15 warnings in 27.23s` in
  `fix-round-1-full-suite.txt`; the warning inventory remains the baseline 15.
- `fix-round-1-verification.txt` records Ruff clean, sole Alembic head 013 with no branch, linear
  history, and zero touched/new functions over 30 lines.
- The repository proof now disposes the first engine and reloads through a new engine/session
  factory, injects the failure on the actual `INSERT INTO v2_team_runtimes`, and exercises legacy
  `select(Team)` plus `GET /teams` invisibility. The migration proof seeds every revision-012
  legacy table and compares ordered content plus column/index/FK metadata across
  `012 -> 013 -> 012 -> 013`.

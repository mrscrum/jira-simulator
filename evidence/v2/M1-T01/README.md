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

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

## Fix round 2

Aware blueprint instants with a non-zero offset are now accepted and normalized to `datetime.UTC`
inside the typed snapshot. The submitted canonical JSON spelling, including its offset strings, is
retained for byte-for-byte re-encoding and canonical SHA-256 identity. Naive boundary and
availability instants remain invalid.

RED was run from `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_create_team.py -q 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-red.txt
```

Result: `2 failed, 23 passed in 0.22s`. Both new regressions reached `_require_utc` and failed
because the then-current implementation rejected valid `-07:00` instants.

The exact Task 1 focused command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-green.txt
```

Result: `33 passed, 1 warning in 1.27s`. The warning is the existing Starlette deprecation warning.

The full safe backend suite was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-full-suite.txt
```

Result: `551 passed, 43 skipped, 15 warnings in 27.23s`; the warning inventory remains the
documented baseline 15.

Ruff was:

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-ruff.txt
```

Result: `All checks passed!`.

The Alembic graph and disposable round-trip were run with:

```bash
set -o pipefail
migration_dir=$(mktemp -d -t m1_t01_fix2.XXXXXX)
migration_db="$migration_dir/simulator.db"
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic upgrade 012 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic upgrade 013 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic downgrade 012 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic upgrade 013 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
DATABASE_URL="sqlite:///$migration_db" ../.venv/bin/python -B -m alembic current --verbose 2>&1 | tee -a ../evidence/v2/M1-T01/fix-round-2-alembic.txt
```

Result: sole head `013`, no branch output, linear history from `001` through `013`, and successful
`012 -> 013 -> 012 -> 013` with final `current` at `013 (head)`. This CLI round-trip used a fresh
disposable database; populated revision-012 row/schema preservation is covered by the passing
focused migration integration test rather than claimed from this CLI output.

The touched/new Python function-length scan was run from `backend/`:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T01/fix-round-2-function-length.txt
import ast
import subprocess
from pathlib import Path

repository = Path("..").resolve()
changed = subprocess.check_output(
    [
        "git",
        "-C",
        str(repository),
        "diff",
        "--name-only",
        "91fe2acf8a860e4a4cc764b9b3ac435bc6fd16d5",
        "--",
        ":(glob)**/*.py",
    ],
    text=True,
).splitlines()
over_limit = []
for relative_path in changed:
    path = repository / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if length > 30:
                over_limit.append(f"{relative_path}:{node.lineno}:{node.name}:{length}")
print(f"Functions over 30 lines: {over_limit}")
PY
```

Result: `Functions over 30 lines: []`.

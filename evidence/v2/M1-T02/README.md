# M1-T02 — Atomic live-slice evidence

Date: 2026-08-10
Base: `ee48c5de9ecac3c5f8362da3422925db77df2ab5`
Scope: local backend, SQLite fakes/disposable files, no Jira/OpenAI call, deploy, push, or UAT.

Environment captured in `verification.txt`:

- Python 3.12.13
- SQLAlchemy 2.0.51
- Alembic 1.19.1
- SQLite 3.50.4

## Required RED

All four focused Task 2 files were written before production code. From `backend/`, with pipeline
failure propagation enabled, the exact command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_live_slice.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/integration/test_migration_014.py -q 2>&1 | tee ../evidence/v2/M1-T02/red.txt
```

Exact result: exit 2 with three collection errors. Each error was
`ModuleNotFoundError: No module named 'app.v2.domain.live_slice'`; pytest stopped after those three
missing-module errors, before collecting the migration file. This was the expected Task 2 absence,
not a Task 1 regression or malformed fixture. The complete output is in `red.txt`.

## Required GREEN

The identical command was rerun after implementation and final refactor, writing `green.txt`.

Exact final result: `30 passed in 2.00s`.

The focused proof covers:

- fixed UUIDv5 paths for activity, ground truth, and projection; canonical JSON/hash vectors;
  frozen records; aware-offset normalization; naive/invalid JSON/supplied identity rejection;
- runtime compare-and-swap `0 -> 1`, caller-order transaction sequences, and independent activity,
  ground-truth, and projection append sequences;
- injected failures at `UPDATE v2_team_runtimes`, `INSERT INTO v2_activity_events`, `INSERT INTO
  v2_ground_truth_records`, and `INSERT INTO v2_projection_intents`, each leaving runtime version
  zero and all ledgers empty;
- two readers of version zero where the winner commits and the loser raises `StaleRuntimeVersion`
  with no partial rows;
- identical replay returning the original records without new rows, while a conflicting key raises
  `SemanticDeduplicationConflict` and rolls back the proposed runtime advance;
- equal/late occurrence timestamps retaining append order, exclusive cursor pagination without gaps
  or duplicates, team/run filtering, and pending projection state;
- a disposed engine followed by a new engine/session factory/UOW reloading runtime version, canonical
  payload/hash, append order, pending status, and page cursors unchanged;
- a test-only exploding projection adapter called only with a returned committed intent; its failure
  leaves authoritative runtime/activity/evidence/pending intent unchanged, and AST checks prove the
  UOW imports/calls no adapter, engine, integration, Jira, OpenAI, or `deliver` boundary;
- populated `013 -> 014 -> 013 -> 014`, version-zero backfill, final non-null/no-default version,
  exact revision-013 restoration, legacy/Task-1 row preservation, empty re-created Task-2 tables,
  and a fresh-process sole-head graph check.

## Verification commands and results

Task 1 regression command:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T02/verification.txt
```

Result: `42 passed, 1 warning in 1.16s`.

Task 2 focused verification used the required GREEN command with `tee -a` to
`verification.txt`. Final result: `30 passed in 1.90s` (the standalone final `green.txt` run was
`30 passed in 2.00s`).

Final safe backend suite:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
```

Final result: `590 passed, 43 skipped, 15 warnings in 29.74s`. The 15 warnings are the preserved
baseline: one Starlette/httpx deprecation warning, 13 existing unawaited-`AsyncMock` warnings in
`test_jira_bootstrapper.py`, and one existing SQLAlchemy identity-conflict warning in
`test_models_jira.py`.

Ruff:

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
```

Final result: `All checks passed!`.

Alembic graph:

```bash
set -o pipefail
../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
```

Final result: sole `Rev: 014 (head)`, parent `013`; branch output was empty; history was linear from
`001` through `014`.

Fresh disposable SQLite round-trip:

```bash
set -e -o pipefail
task2_migration_dir="$(/usr/bin/mktemp -d /tmp/jira-simulator-m1-t02.XXXXXX)"
task2_migration_db="$task2_migration_dir/simulator.db"
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic upgrade 013 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic upgrade 014 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic current --verbose 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic downgrade 013 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic current --verbose 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic upgrade 014 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
DATABASE_URL="sqlite:///$task2_migration_db" ../.venv/bin/python -B -m alembic current --verbose 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
/bin/rm "$task2_migration_db"
/bin/rmdir "$task2_migration_dir"
```

Result: all commands exited zero; current moved `014 (head) -> 013 -> 014 (head)`. This fresh CLI
proof does not claim populated-data preservation; that stronger proof belongs to the focused
integration test.

Touched/new Python function-length scan:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee -a ../evidence/v2/M1-T02/verification.txt
import ast
import subprocess
from pathlib import Path

repository = Path("..").resolve()
base = "ee48c5de9ecac3c5f8362da3422925db77df2ab5"
tracked = subprocess.check_output(
    ["git", "-C", str(repository), "diff", "--name-only", base, "--", ":(glob)**/*.py"],
    text=True,
).splitlines()
untracked = subprocess.check_output(
    ["git", "-C", str(repository), "ls-files", "--others", "--exclude-standard", "--", "*.py"],
    text=True,
).splitlines()
over_limit = []
for relative_path in sorted(set(tracked + untracked)):
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

## Verification correction retained in the evidence

The first graph invocation after the initial full suite exposed a fresh-process circular import:
the eager `app.v2.persistence` exports loaded v2 models while `app.models` was still initializing.
That failing traceback remains in `verification.txt`. A subprocess graph regression was witnessed
failing, then persistence exports were made lazy. Staged self-review subsequently showed that cold
imports of the public UOW/model interfaces could still re-enter additive `app.models` registration;
three subprocess cases were witnessed RED and then fixed with cycle-aware lazy v2 registration.
The graph, public cold imports, migration round-trip, final focused/full suites, and final Ruff all
pass. Earlier green full runs (`586` before the graph regression and `587` before the three cold-
import cases) remain in the evidence; the final authoritative result is `590 passed` above.

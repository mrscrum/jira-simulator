# M1-T04 Evidence — dual-clock business calendar

Date: 2026-08-11

Base: `659cba835eb7ffd7e154aa55f3d1d7b371487336`

Scope: pure immutable UTC/business-time arithmetic, DST-safe IANA local-boundary resolution,
fixed local cadence, and `US_FEDERAL_V1` holiday-horizon data. This task added no migration,
mapping, repository, unit of work, scheduler, engine, Jira/OpenAI call, frontend, deployment, UAT,
or M1 completion.

## Environment

The following was run from `backend/`:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T04/versions.txt
import sys
from zoneinfo import TZPATH, ZoneInfo

print(f"Python {sys.version.split()[0]}")
print("tzdata system-zoneinfo")
print(f"zoneinfo paths {TZPATH}")
print(f"America/Los_Angeles key {ZoneInfo('America/Los_Angeles').key}")
PY
```

Result: Python `3.12.13`; system zoneinfo loaded `America/Los_Angeles` from the recorded `TZPATH`.
No host-local timezone, locale, or wall clock was consulted by production code.

## Strict RED -> GREEN -> REFACTOR

The two new unit modules and additive Task 4 architecture assertions were written before either
production module existed. Exact RED from `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/red.txt
```

Result: exit `2`, `2 errors in 0.17s`. Both were the expected collection-time
`ModuleNotFoundError` failures for absent `app.v2.domain.business_calendar` and
`app.v2.domain.us_federal_calendar`; there was no timezone-data, fixture, syntax, or assertion
failure.

After the minimum implementation, a test-only collection error identified `request` as pytest's
reserved parametrization name. Renaming that test parameter to `addition` required no production
change. A later self-review added a regression proving a half-open interval may end at midnight
immediately after the final horizon day without inspecting the next day's calendar policy. The
focused micro-RED was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py::test_elapsed_treats_midnight_after_horizon_as_an_exclusive_endpoint -q 2>&1 | tee ../evidence/v2/M1-T04/horizon-end-red.txt
```

Result: exit `1`, `1 failed in 0.12s`; `elapsed` tried to resolve `2028-01-01` beyond a
`2027-12-31` horizon. Selecting the final intersected date from the exclusive endpoint minus
`timedelta.resolution` made the micro-test pass.

Final identical focused selection:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/green.txt
```

Result: exit `0`, `117 passed in 0.21s`.

## Calendar, DST, cadence, and horizon vectors

- Aware `-07:00` and `+05:30` instants normalize to the same UTC instants; naive inputs reject.
- The resolved Los Angeles `09:00`–`17:00` interval is exact at open/inside/close, with weekends,
  the explicit `2026-12-25` holiday, overnight spans, no-business intervals, year changes,
  multi-day additions, and zero additions covered.
- A Sunday `00:30`–`03:00` interval is exactly `1.5h` on `2026-03-08` and `3.5h` on
  `2026-11-01`. Local `02:30` on the spring transition rejects as nonexistent; local `01:30` on
  the fall transition rejects as ambiguous.
- Fourteen local days preserve the `09:00` Los Angeles anchor while UTC changes from `17:00` to
  `16:00` in spring and `16:00` to `17:00` in fall. A boundary on Christmas remains on Christmas;
  workdays and holidays cannot shift it. Target cadence gaps/overlaps reject.
- The exact 2026 holiday tuple covers all 11 approved rules, including observed Independence Day.
  Saturday-Friday/Sunday-Monday observations, cross-year New Year observations, and Inauguration
  Day exclusion are explicit assertions.
- A 2026 first start produces `2025-01-01` through `2036-12-31`. `2035-01-01` is the exact no-op
  threshold; `2035-01-02` extends through `2046-12-31`, and replaying that extension returns the
  same immutable value.
- All public Task 4 values are frozen/slotted, expose no instance mapping, preserve identity across
  shallow/deep copy, and reject pickle/reduce reconstruction under the shared ordinary immutable
  value policy.

## Regression verification

All commands below were run from `backend/` with pipeline failure propagation.

Task 1 focused:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T04/task1-focused.txt
```

Result: `52 passed, 1 warning in 1.49s`.

Task 2 focused:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_live_slice.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/integration/test_migration_014.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/task2-focused.txt
```

Result: `148 passed in 3.20s`.

Task 3 focused:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/task3-focused.txt
```

Result: `247 passed in 0.43s`.

All v2:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q 2>&1 | tee ../evidence/v2/M1-T04/v2-suite.txt
```

Result: `531 passed, 1 warning in 4.10s`.

Full safe backend suite:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee ../evidence/v2/M1-T04/full-suite.txt
```

Result: `1049 passed, 43 skipped, 15 warnings in 30.82s`. The 15 warnings are the preserved
baseline categories: one Starlette/httpx deprecation, 13 Jira-bootstrapper unawaited-`AsyncMock`
warnings, and one SQLAlchemy identity-map warning. No warning was suppressed or broadened.

Ruff:

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee ../evidence/v2/M1-T04/ruff.txt
```

Result: exit `0`, `All checks passed!`.

Alembic graph:

```bash
set -o pipefail
../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee ../evidence/v2/M1-T04/alembic.txt
../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T04/alembic.txt
../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T04/alembic.txt
```

Result: sole `Rev: 014 (head)` with parent `013`; branches output was empty and history remained
linear from `001` through `014`. Task 4 added no migration or schema change.

## Shape and architecture

The exact scan used the Task 4 base, parsed every touched or untracked Python file, and inspected
both production modules for prohibited state/dependencies and host-local clock behavior:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T04/code-shape.txt
import ast
import subprocess
from pathlib import Path

repository = Path('..').resolve()
base = '659cba835eb7ffd7e154aa55f3d1d7b371487336'
tracked = subprocess.check_output(
    ['git', '-C', str(repository), 'diff', '--name-only', base, '--', ':(glob)**/*.py'],
    text=True,
).splitlines()
untracked = subprocess.check_output(
    ['git', '-C', str(repository), 'ls-files', '--others', '--exclude-standard', '--', '*.py'],
    text=True,
).splitlines()
files = sorted(set(tracked + untracked))
over_length = []
over_arguments = []
for relative_path in files:
    tree = ast.parse((repository / relative_path).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            arguments = len(node.args.posonlyargs) + len(node.args.args) + len(node.args.kwonlyargs)
            if length > 30:
                over_length.append(f'{relative_path}:{node.lineno}:{node.name}:{length}')
            if arguments > 3:
                over_arguments.append(f'{relative_path}:{node.lineno}:{node.name}:{arguments}')
print(f'Touched Python files: {files}')
print(f'Functions over 30 lines: {over_length}')
print(f'Functions over 3 arguments: {over_arguments}')

forbidden_imports = (
    'aiohttp', 'app.database', 'app.engine', 'app.integrations', 'app.models',
    'app.v2.persistence', 'httpx', 'requests', 'socket', 'sqlalchemy', 'urllib',
)
forbidden_calls = {'now', 'today', 'utcnow'}
architecture_violations = []
for relative_path in (
    'backend/app/v2/domain/business_calendar.py',
    'backend/app/v2/domain/us_federal_calendar.py',
):
    tree = ast.parse((repository / relative_path).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(forbidden_imports):
            architecture_violations.append(f'{relative_path}:import:{node.module}')
        if isinstance(node, ast.Import):
            architecture_violations.extend(
                f'{relative_path}:import:{alias.name}'
                for alias in node.names
                if alias.name.startswith(forbidden_imports)
            )
        if isinstance(node, ast.Call):
            call_name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
            if call_name in forbidden_calls:
                architecture_violations.append(f'{relative_path}:call:{call_name}')
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == 'astimezone'
                and not node.args
                and not node.keywords
            ):
                architecture_violations.append(f'{relative_path}:host-local-astimezone')
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
            architecture_violations.append(f'{relative_path}:mutable-module-state:{node.lineno}')
print(f'Architecture violations: {architecture_violations}')
if over_length or over_arguments or architecture_violations:
    raise SystemExit(1)
PY
```

Result: `Functions over 30 lines: []`, `Functions over 3 arguments: []`, and
`Architecture violations: []`.

Final tracked whitespace verification after the documentation update:

```bash
set -o pipefail
git diff --check 2>&1 | tee evidence/v2/M1-T04/diff-check.txt
```

Result: exit `0` with empty output. The explicitly staged scope was then checked with
`git diff --cached --check` before commit. No secret, live credential, external provider call,
deployment, push, or UAT occurred.

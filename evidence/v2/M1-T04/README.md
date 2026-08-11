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

## Review fix round 1 — harden calendar horizon contracts

Review-fix base: `59be24c66063b82405a8c8978b60edda3cf776e7`.

All review regressions were added before production edits. Exact focused RED from `backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-red.txt
```

Result: exit `1`, `24 failed, 112 passed in 0.37s`. Expected failures proved the old boundary
accepted `posixrules`, raised raw `OverflowError` at `date.max`, derived the starter year from the
datetime representation, required no resolved-team zone, extended a far-stale horizon only one
block per call, trusted incomplete/forged federal horizons, and lacked the shared timezone module.
Existing DST, cadence, ordinary horizon, holiday, immutable-value, and isolation cases remained
green.

The minimum implementation introduced a shared available-IANA-key resolver, team-zone year
derivation, canonical horizon authentication, ten-year-block catch-up, and stable exhaustion
errors. After an import-order-only Ruff refactor, the identical focused command produced:

```text
136 passed in 0.28s
```

The complete output is retained in `fix-round-1-green.txt`. The new cases prove:

- a canonical resolved Kiritimati `+14:00` boundary is typed as UTC but materializes from its
  Kiritimati local year; equivalent UTC and offset representations produce equal horizons;
- `America/Los_Angeles`, `Pacific/Kiritimati`, and `Etc/UTC` accept, while the separately loadable
  pseudo-zone `posixrules` rejects;
- exact independent `calendar.monthcalendar` reference dates agree for 1900–2100;
- normal threshold extension adds one block, a `2045-01-02` stale request catches the original
  horizon through `2056-12-31`, and identical replay returns the same object;
- missing, extra, non-observed, partial-start, and partial-end federal horizons reject before the
  extension/no-op decision without mutating input;
- the round-1 `Etc/UTC` next-working/addition exhaustion and final-day elapsed cases do not leak
  `OverflowError` at the horizon or `date.max`; cross-zone extreme conversion was not covered until
  review fix round 2. The actual `BusinessCalendar._configuration` field remains frozen and
  identity-stable.

### Regression and static verification

All commands used pipeline failure propagation and ran from `backend/`.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-task1-focused.txt
```

Result: `52 passed, 1 warning in 1.67s`.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_live_slice.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/integration/test_migration_014.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-task2-focused.txt
```

Result: `148 passed in 3.51s`.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-task3-focused.txt
```

Result: `247 passed in 0.54s`.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-v2-suite.txt
```

Result: `550 passed, 1 warning in 4.86s`.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-full-suite.txt
```

Result: `1068 passed, 43 skipped, 15 warnings in 30.86s`. The warning categories remain exactly
the documented baseline: one Starlette/httpx deprecation, 13 Jira-bootstrapper
unawaited-`AsyncMock` warnings, and one SQLAlchemy identity-map warning.

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-ruff.txt
```

Result: exit `0`, `All checks passed!`.

The first graph attempt used the environment-sensitive `../.venv/bin/alembic` entrypoint instead
of the repository's established module form. It exited `1` because revision 013 could not import
`app.v2`; the exact tooling error is retained in `fix-round-1-alembic.txt` and is not represented as
a migration defect. The corrected exact commands were:

```bash
set -o pipefail
../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-alembic-corrected.txt
../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T04/fix-round-1-alembic-corrected.txt
../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T04/fix-round-1-alembic-corrected.txt
```

Result: sole `Rev: 014 (head)` with parent `013`; branches output was empty and history remained
linear from `001` through `014`. No migration or schema file changed.

The touched-code scan used base `59be24c66063b82405a8c8978b60edda3cf776e7`, parsed the five
changed and one new Python file, and included `business_calendar.py`, `iana_timezone.py`, and
`us_federal_calendar.py` in the prohibited-import/call/mutable-state AST checks. Exact command:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T04/fix-round-1-code-shape.txt
import ast
import subprocess
from pathlib import Path

repository = Path('..').resolve()
base = '59be24c66063b82405a8c8978b60edda3cf776e7'
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
    'backend/app/v2/domain/iana_timezone.py',
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

Exact output in `fix-round-1-code-shape.txt` is:

```text
Functions over 30 lines: []
Functions over 3 arguments: []
Architecture violations: []
```

No migration, persistence, UOW, Task 3 algorithm/vector, v1, scheduler, engine, Jira/OpenAI,
frontend, infrastructure, deployment, push, UAT, or M1-completion boundary changed.

Final tracked whitespace check after documentation:

```bash
set -o pipefail
git diff --check 2>&1 | tee evidence/v2/M1-T04/fix-round-1-diff-check.txt
```

Result: exit `0` with empty output. The final cached diff is checked separately after explicit
staging and before the exact-subject commit.

## Review fix round 2 — normalize calendar range errors

Review-fix base: `bfc97caccd3c40bba8c9db435972b0d7c8582b05`.

The six extreme-range regressions were added before the production edit. Exact RED from
`backend/`:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-2-red.txt
```

Result: exit `1`, `6 failed, 136 passed in 0.36s`. Each failure was the expected raw
`OverflowError: date value out of range` from a real public path: maximum UTC converted to
Kiritimati, minimum UTC converted to Los Angeles, a `date.max` Los Angeles work boundary,
propagation through `next_working_instant` and `add`, and maximum-anchor Kiritimati cadence. No
fixture, syntax, timezone-data, or unrelated assertion failed.

The minimum implementation routed every calendar `astimezone` operation through one short helper
that translates only `OverflowError` to `ValueError("calendar operation exceeds the supported
datetime range")`; cadence date arithmetic uses the same stable message. Exact GREEN:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_business_calendar.py tests/v2/unit/test_us_federal_calendar.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-2-green.txt
```

Result: exit `0`, `142 passed in 0.44s`.

### Review-fix regression verification

All commands ran from `backend/` with pipeline failure propagation.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-2-v2-suite.txt
```

Result: `556 passed, 1 warning in 4.34s`.

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee ../evidence/v2/M1-T04/fix-round-2-full-suite.txt
```

Result: `1074 passed, 43 skipped, 15 warnings in 30.82s`. The warnings remain the documented
baseline categories: one Starlette/httpx deprecation, 13 Jira-bootstrapper unawaited-`AsyncMock`
warnings, and one SQLAlchemy identity-map warning.

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee ../evidence/v2/M1-T04/fix-round-2-ruff.txt
```

Result: exit `0`, `All checks passed!`.

```bash
set -o pipefail
../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee ../evidence/v2/M1-T04/fix-round-2-alembic.txt
../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T04/fix-round-2-alembic.txt
../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T04/fix-round-2-alembic.txt
```

Result: sole `Rev: 014 (head)` with parent `013`, empty branches, and linear history from `001`
through `014`. No migration or schema file changed.

The exact Task 4 AST command used the same fully recorded scan above with base changed to
`bfc97caccd3c40bba8c9db435972b0d7c8582b05`; its discovered touched files were only
`business_calendar.py` and `test_business_calendar.py`. Complete output is retained in
`fix-round-2-code-shape.txt`:

```text
Functions over 30 lines: []
Functions over 3 arguments: []
Architecture violations: []
```

Review-fix scope contains no migration, persistence, UOW, federal algorithm, Task 3 vector,
ordinary DST/cadence/horizon behavior, v1, scheduler, engine, Jira/OpenAI, frontend,
infrastructure, deployment, push, UAT, or M1-completion change.

Final tracked whitespace command from the repository root:

```bash
set -o pipefail
git diff --check 2>&1 | tee evidence/v2/M1-T04/fix-round-2-diff-check.txt
```

Result: exit `0` with empty output. The cached diff receives the same check after explicit staging.

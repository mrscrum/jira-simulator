# M1-T03 — Deterministic decision and bounded-sampling evidence

Date: 2026-08-10

Base: `3d2c6fd13d3744ee2df41af690d61eb200ff4945`

Scope: pure local v2 domain code. No persistence/migration/UOW/scheduler/engine, occurrence
allocation, Jira/OpenAI access, deployment, push, UAT, or M1 completion.

## Environment

`versions.txt` records:

- Python 3.12.13
- pytest 9.1.1
- Pydantic 2.13.4
- SQLAlchemy 2.0.51
- Alembic 1.19.1
- SQLite 3.50.4

The exact command was:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T03/versions.txt
import platform
import sqlite3
import alembic
import pydantic
import pytest
import sqlalchemy
print(f"Python {platform.python_version()}")
print(f"pytest {pytest.__version__}")
print(f"Pydantic {pydantic.__version__}")
print(f"SQLAlchemy {sqlalchemy.__version__}")
print(f"Alembic {alembic.__version__}")
print(f"SQLite {sqlite3.sqlite_version}")
PY
```

## Strict TDD evidence

The golden fixture and all focused RNG, sampling, and architecture tests were written before either
production module existed. From `backend/`, the required command was run exactly with pipeline
failure propagation:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/red.txt
```

RED result: exit 2, `2 errors in 0.16s`. Collection failed only because
`app.v2.domain.deterministic_rng` and `app.v2.domain.sampling` did not exist. There were no fixture,
syntax, or assertion errors. The complete traceback is retained in `red.txt`.

After the minimum implementation and formatting refactor, the identical command wrote `green.txt`.
GREEN result: exit 0, `143 passed in 0.29s`.

## Independent golden-vector provenance

`backend/tests/v2/fixtures/hmac_sha256_u53_v1_vectors.json` freezes literal canonical-message UTF-8
text, full lower-case HMAC digest, high-53-bit integer, and unit value. The literals were derived
before production code with a standalone Python standard-library script implementing the written
contract directly; it imported no `app.v2` function. Composed `café-seed` and decomposed
`cafe\u0301-seed` yield the same digest/U53 result, while `cafe-seed` separates. A fourth vector
covers positive occurrence/draw coordinates and a catalog-key entity.

The independent post-implementation reproduction used:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T03/golden-vector-provenance.txt
import hashlib
import hmac
import json
import unicodedata
from pathlib import Path

fixture = json.loads(
    Path('tests/v2/fixtures/hmac_sha256_u53_v1_vectors.json').read_text(encoding='utf-8')
)
print(fixture['provenance'])
for vector in fixture['vectors']:
    message = vector['canonical_message'].encode('utf-8')
    key = hashlib.sha256(unicodedata.normalize('NFC', vector['seed']).encode('utf-8')).digest()
    digest = hmac.new(key, message, hashlib.sha256).digest()
    integer = int.from_bytes(digest[:8], byteorder='big', signed=False) >> 11
    unit_value = integer / (1 << 53)
    assert digest.hex() == vector['hmac_sha256']
    assert integer == vector['u53_integer']
    assert unit_value == vector['unit_value']
    print(vector['name'], message.decode('utf-8'))
    print(digest.hex(), integer, repr(unit_value))
print('All independently fixed literal vectors reproduced exactly.')
PY
```

Result: exit 0 and `All independently fixed literal vectors reproduced exactly.` The complete
canonical bytes and numeric outputs are in `golden-vector-provenance.txt`.

## Behavior proved by the focused suite

- Every approved team/run/member/sprint/item/visit/dependency/rework path has fixed UUID literals,
  including zero and positive ordinals and all five creation kinds. The Task-1 team/initial-run IDs
  are identical to `team_rng_id`/`run_rng_id`; call and database order create no parallel identity.
- Lower-case digest, UUID, enum, root-seed, entity, occurrence, and draw-index boundaries reject raw
  strings where an enum/UUID is required, malformed/upper-case digests, booleans, negatives, and
  non-integers.
- Canonical messages have exactly seven approved fields. Frozen result replacement cannot decouple
  the message, digest, U53 integer, unit value, algorithm, or decision coordinate.
- A fresh Python subprocess reproduces the fixed positive-coordinate vector. Fresh streams plus
  reversed/interleaved calls and unrelated draws reproduce identical results.
- Dwell returns all five exact anchors, uses fixed literal log1p-interpolation values between them,
  remains monotone/bounded across 1,001 dense draws, and covers zero/equal plus very small/large
  finite profiles. Every invalid draw/value/order category is rejected, including booleans.
- Touch returns exact endpoints/equal bounds and the literal linear formula, with every invalid
  draw/value/order category rejected. Both samplers exercise every starter resolved timing cell
  without changing its canonical fixture.
- AST/import assertions reject `hash`, `random`, `uuid4`, time sources, mutable module containers,
  database/ORM/persistence, v1 engine/integration, and external adapter boundaries.

## Regression and verification commands

Task 1 focused regression:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T03/task1-focused.txt
```

Result: `48 passed, 1 warning in 1.49s`.

Task 2 focused regression:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_live_slice.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/integration/test_migration_014.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/task2-focused.txt
```

Result: `144 passed in 3.10s`.

All v2 tests:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q 2>&1 | tee ../evidence/v2/M1-T03/v2-suite.txt
```

Result: `321 passed, 1 warning in 3.94s`.

Full safe backend suite:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee ../evidence/v2/M1-T03/full-suite.txt
```

Result: `839 passed, 43 skipped, 15 warnings in 30.74s`. The warnings are the preserved baseline:
one Starlette/httpx deprecation, 13 existing unawaited `AsyncMock` warnings in
`test_jira_bootstrapper.py`, and one existing SQLAlchemy identity-conflict warning in
`test_models_jira.py`.

Ruff:

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee ../evidence/v2/M1-T03/ruff.txt
```

Result: `All checks passed!`.

Alembic graph:

```bash
set -o pipefail
../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee ../evidence/v2/M1-T03/alembic.txt
../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T03/alembic.txt
../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T03/alembic.txt
```

Result: sole `Rev: 014 (head)` with parent `013`; branch output was empty and history remained
linear from `001` through `014`. Task 3 added no migration or schema change.

The touched/new AST scan read Python paths from `git diff`/`git ls-files`, parsed every function,
counted positional/keyword-only arguments, and separately scanned the two production modules for
forbidden imports/calls and mutable module-level containers:

```bash
set -o pipefail
../.venv/bin/python -B - <<'PY' 2>&1 | tee ../evidence/v2/M1-T03/code-shape.txt
import ast
import subprocess
from pathlib import Path

repository = Path('..').resolve()
base = '3d2c6fd13d3744ee2df41af690d61eb200ff4945'
tracked = subprocess.check_output(
    ['git', '-C', str(repository), 'diff', '--name-only', base, '--', ':(glob)**/*.py'],
    text=True,
).splitlines()
untracked = subprocess.check_output(
    ['git', '-C', str(repository), 'ls-files', '--others', '--exclude-standard', '--', '*.py'],
    text=True,
).splitlines()
over_length = []
over_arguments = []
for relative_path in sorted(set(tracked + untracked)):
    path = repository / relative_path
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            arguments = len(node.args.posonlyargs) + len(node.args.args) + len(node.args.kwonlyargs)
            if length > 30:
                over_length.append(f'{relative_path}:{node.lineno}:{node.name}:{length}')
            if arguments > 3:
                over_arguments.append(f'{relative_path}:{node.lineno}:{node.name}:{arguments}')
print(f'Touched Python files: {sorted(set(tracked + untracked))}')
print(f'Functions over 30 lines: {over_length}')
print(f'Functions over 3 arguments: {over_arguments}')

forbidden_imports = (
    'app.database', 'app.engine', 'app.integrations', 'app.models',
    'app.v2.persistence', 'random', 'sqlalchemy',
)
forbidden_calls = {'hash', 'uuid4', 'now', 'utcnow', 'time'}
architecture_violations = []
for relative_path in (
    'backend/app/v2/domain/deterministic_rng.py',
    'backend/app/v2/domain/sampling.py',
):
    tree = ast.parse((repository / relative_path).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith(forbidden_imports)
        ):
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
    for node in tree.body:
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(node.value, (ast.Dict, ast.List, ast.Set))
        ):
            architecture_violations.append(
                f'{relative_path}:mutable-module-state:{node.lineno}'
            )
print(f'Architecture violations: {architecture_violations}')
PY
```

The executed script result in `code-shape.txt` was:

- `Functions over 30 lines: []`
- `Functions over 3 arguments: []`
- `Architecture violations: []`

Whitespace verification:

```bash
set -o pipefail
git diff --check 2>&1 | tee evidence/v2/M1-T03/diff-check.txt
```

Result: exit 0 with empty output. No external call or live credential was made or read.

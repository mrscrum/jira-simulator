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
covers positive cancellation occurrence/draw coordinates with the item semantic UUID. Review fix
round 1 adds a fifth independently fixed ECMAScript vector at the maximum safe integer.

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
- Canonical messages have exactly seven approved fields. The original validators coupled the
  message/digest-derived values, but the initial evidence overstated keyed authenticity: an
  arbitrary digest with self-consistent U53 values could still be constructed. Review fix round 1
  below closes that gap by sealing construction behind the keyed stream.
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

## Review fix round 1 — bind deterministic sample provenance

Date: 2026-08-11
Fix base: `4696250`

This review fix corrects the keyed-provenance overclaim above. `UniformDraw` normal direct
construction and `dataclasses.replace` now reject; only `DeterministicRandomStream.draw` creates a
validated result, without retaining the root seed. Current decision entities are semantic UUIDs,
and every semantic ordinal/index/sequence, occurrence, and draw index is a strict integer in
`0..2^53-1`. The documented fixed-zero/nonzero scope is table-tested for every decision type.
`DurationSample` direct construction and replacement now require the exact dwell/touch result for
the retained parameters and draw.

### Review-fix RED and GREEN

All four review regressions and the corrected/maximum-boundary literal vectors were added before
production edits. From `backend/`, the exact RED command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-red.txt
```

RED result: exit 1, `45 failed, 148 passed in 0.50s`. Failures were the expected missing safe upper
bound, UUID-only/scoped occurrences, sealed keyed draw construction, strict canonical integer
comparison, and exact sample-formula validation. The complete failures are retained in
`fix-round-1-red.txt`; there were no fixture, import, collection, or unrelated failures.

During refactor, a zero-argument direct-construction edge was first proved with:

```bash
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py::test_uniform_draw_normal_direct_construction_is_sealed -q
```

That micro-RED exited 1 with `1 failed in 0.13s` because an `init=False` dataclass inherited
zero-argument `object.__init__`; the explicit rejecting constructor then closed that route.

The final exact focused command was:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_deterministic_rng.py tests/v2/unit/test_sampling.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-green.txt
```

GREEN result: exit 0, `203 passed in 0.31s`.

### Independent ECMAScript vector proof

From the repository root, Node.js independently rebuilt the sorted seven-field JSON from each
fixture coordinate, NFC-normalized and hashed the seed, calculated HMAC-SHA-256, extracted U53 via
`BigInt`, and compared every literal:

```bash
set -o pipefail
node - <<'JS' 2>&1 | tee evidence/v2/M1-T03/fix-round-1-vector-provenance.txt
const crypto = require('node:crypto');
const fs = require('node:fs');
const fixture = JSON.parse(fs.readFileSync(
  'backend/tests/v2/fixtures/hmac_sha256_u53_v1_vectors.json', 'utf8'
));
for (const vector of fixture.vectors) {
  const document = {
    algorithm: 'HMAC_SHA256_U53_V1',
    team_id: vector.team_id,
    run_id: vector.run_id,
    entity_id: vector.entity_id,
    decision_type: vector.decision_type,
    occurrence: vector.occurrence,
    draw_index: vector.draw_index,
  };
  const canonical = JSON.stringify(Object.fromEntries(
    Object.keys(document).sort().map((key) => [key, document[key]])
  ));
  const key = crypto.createHash('sha256').update(vector.seed.normalize('NFC'), 'utf8').digest();
  const digest = crypto.createHmac('sha256', key).update(canonical, 'utf8').digest();
  let firstWord = 0n;
  for (const byte of digest.subarray(0, 8)) firstWord = (firstWord << 8n) | BigInt(byte);
  const integer = Number(firstWord >> 11n);
  const unitValue = integer / 2 ** 53;
  if (canonical !== vector.canonical_message) throw new Error(`${vector.name}: canonical bytes`);
  if (digest.toString('hex') !== vector.hmac_sha256) throw new Error(`${vector.name}: digest`);
  if (integer !== vector.u53_integer) throw new Error(`${vector.name}: U53 integer`);
  if (unitValue !== vector.unit_value) throw new Error(`${vector.name}: unit value`);
  console.log(`${vector.name}: ${digest.toString('hex')} ${integer} ${unitValue}`);
}
console.log('All vectors independently re-encoded and reproduced in Node.js.');
JS
```

Result: exit 0, including cancellation digest
`d3d025bfdfbbd5714ab5b66989e41279b5ce2135b364b9a6a24e3cdd7f7e66e0` and maximum-safe
digest `00f95abf1bdae7fc74ab084052900221cf26ad8d3ddd75713ec6dad8761129f5`, followed by
`All vectors independently re-encoded and reproduced in Node.js.`

### Review-fix verification

From `backend/`, the exact regression commands were:

```bash
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-task1-focused.txt
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_live_slice.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/integration/test_migration_014.py tests/v2/unit/test_architecture_boundaries.py -q 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-task2-focused.txt
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2 -q 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-v2-suite.txt
PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests -q 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-full-suite.txt
```

Results:

- Task 1, `fix-round-1-task1-focused.txt`: `48 passed, 1 warning in 1.24s`.
- Task 2, `fix-round-1-task2-focused.txt`: `144 passed in 2.94s`.
- All v2, `fix-round-1-v2-suite.txt`: `381 passed, 1 warning in 4.13s`.
- Full backend, `fix-round-1-full-suite.txt`: `899 passed, 43 skipped, 15 warnings in 30.55s`.

The full-suite warnings remain exactly the documented baseline categories: one Starlette/httpx
deprecation, 13 Jira-bootstrapper unawaited-`AsyncMock` warnings, and one SQLAlchemy identity-map
warning. No warning was suppressed or broadened.

Ruff was run exactly from `backend/`:

```bash
set -o pipefail
../.venv/bin/python -B -m ruff check --no-cache . 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-ruff.txt
```

Result: exit 0, `All checks passed!`.

Alembic graph verification from `backend/`:

```bash
set -o pipefail
../.venv/bin/python -B -m alembic heads --verbose 2>&1 | tee ../evidence/v2/M1-T03/fix-round-1-alembic.txt
../.venv/bin/python -B -m alembic branches --verbose 2>&1 | tee -a ../evidence/v2/M1-T03/fix-round-1-alembic.txt
../.venv/bin/python -B -m alembic history 2>&1 | tee -a ../evidence/v2/M1-T03/fix-round-1-alembic.txt
```

Result: sole `Rev: 014 (head)` with parent `013`, empty branch output, and a linear `001` through
`014` history. No migration or schema file changed.

The touched-function/architecture scan used fix base `4696250` and wrote
`fix-round-1-code-shape.txt`. Result:

- `Functions over 30 lines: []`
- `Functions over 3 arguments: []`
- `Architecture violations: []`

Final whitespace verification from the repository root:

```bash
set -o pipefail
git diff --check 2>&1 | tee evidence/v2/M1-T03/fix-round-1-diff-check.txt
```

Result: exit 0 with empty output.

No persistence/UOW/calendar/scheduler/engine/frontend/Jira/OpenAI interface was imported, called,
or changed. No deployment, push, UAT, or M1 completion was claimed.

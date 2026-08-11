# Task 5 Implementation Report — First Realism Behaviors and Fake-Jira Vertical

Date: 2026-08-11

## RED evidence

Exact command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/integration/test_live_scheduler.py -q
```

Exact failure:

```text
==================================== ERRORS ====================================
________________ ERROR collecting tests/v2/unit/test_risks.py _________________
ImportError while importing test module '/Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/.worktrees/v2-live-simulator/backend/tests/v2/unit/test_risks.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/v2/unit/test_risks.py:12: in <module>
    from app.v2.domain.risks import evaluate_due_risks
E   ModuleNotFoundError: No module named 'app.v2.domain.risks'
=========================== short test summary info ============================
ERROR tests/v2/unit/test_risks.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.27s
```

The required risk-policy module and vertical fake were absent, so collection failed before any
production implementation existed.

## Implementation summary

- Added the exact `RiskEvaluation` and `evaluate_due_risks` interface with versioned, due-trigger
  evaluation for sampled long stay, review rejection to a configured earlier route step,
  cancellation, deterministic external-dependency pause, and member-unavailability overlays.
- Reused accepted work/visit/overlay state, Task 6 allocation/natural claims, blueprint factors,
  deterministic draws, causal ground truth, fallback text, and pending Jira intents. No LLM call or
  separate proof/counter protocol was introduced.
- Evaluated risks before ordinary tick progress, merged sparse after-images, excluded only visits
  paused by the due risk, and preserved unrelated progress.
- Seeded the existing cancellation and member-unavailability natural-decision counters during
  bootstrap so the accepted Task 6 unit of work can validate and atomically consume them.
- Enriched sprint lifecycle and status-transition payloads with local semantic UUIDs and logical Jira
  fields. The concrete adapter resolves a local board UUID through the persisted `BOARD` mapping
  before public Jira client calls.
- Added a public-surface in-memory Jira client and a meaningful vertical acceptance using production
  scheduler, coherent live store, Task 6 unit of work, outbox store, worker, and concrete adapter.
  It provisions project/board/issues, crosses two sprint ends, restarts without catch-up, retains an
  outage retry, drains after recovery, and proves provider-success/local-receipt replay does not
  duplicate resources.

## GREEN and regression evidence

Required GREEN command after refactor:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/integration/test_live_scheduler.py -q
..............                                                           [100%]
14 passed in 4.87s
```

Affected regression command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_tick.py tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/unit/test_v2_sprint_lifecycle.py tests/v2/unit/test_jira_delivery_worker.py tests/v2/integration/test_jira_delivery_store.py tests/v2/integration/test_team_tick.py tests/v2/integration/test_live_scheduler.py -q
......................................................                   [100%]
54 passed in 5.82s
```

Final all-v2 command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2 -q
........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 19%]
........................................................................ [ 26%]
........................................................................ [ 32%]
........................................................................ [ 39%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 65%]
........................................................................ [ 71%]
........................................................................ [ 78%]
........................................................................ [ 84%]
........................................................................ [ 91%]
........................................................................ [ 97%]
.........................                                                [100%]
=============================== warnings summary ===============================
../.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/.worktrees/v2-live-simulator/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1105 passed, 1 warning in 39.46s
```

The required scheduler file includes the existing two-team isolation scenario; it passed in the
focused and full-v2 runs. No five-team matrix was added.

## Ruff, Alembic, and no-migration evidence

```text
cd backend && ../.venv/bin/python -m ruff check app/v2 tests/v2
All checks passed!

cd backend && ../.venv/bin/python -m ruff check app/integrations/v2_jira_intent_adapter.py
All checks passed!

cd backend && ../.venv/bin/python -m alembic heads
016 (head)

cd backend && git diff --name-only bd7430a -- alembic/versions
[no output]

cd backend && git diff --check
[no output]
```

Revision 016 remains the sole migration head and Task 5 adds no migration.

## Documentation and backlog

- Appended task outcomes and assumptions to `changelog.md` and `assumptions.md`.
- Updated `README.md` and `agent_instruction.md` to the current live-loop state, next slice, and
  remaining limitations.
- Updated `backlog/v2/README.md`, `stage-1-live-runtime-and-scrum.md`, and
  `stage-4-risks-content-transcripts.md`; the exact Task 5 outcome moved from in progress to complete.

## Self-review

- The five behaviors each have one representative outcome test; the acceptance remains one
  meaningful vertical rather than an exhaustive fault matrix.
- Domain payloads contain local semantic UUIDs and logical fields only. Jira provider IDs are
  resolved exclusively by the concrete adapter from persisted mappings.
- Jira calls occur only after the authoritative commit, through the existing outbox worker.
- The fake uses public Jira client methods and no production-only fake hook. Retry and idempotency
  assertions observe persisted pending work and provider resource counts.
- No schema, live Jira access, deployment, push, UAT, hostile scalar/subclass/pickle/HMAC/canonical-
  hash machinery, or exact-microsecond proof protocol was added.
- The superseded Task 7 stash remains present and untouched.

## Commits

- Implementation commit: `75b0f425acf3533add6b4dc2679c3d4fcf70df9b`
  (`feat: prove v2 live scrum loop`)

## Concerns

- The acceptance deliberately seeds production-shaped provisioning intents through the real Task 6
  unit of work because production team creation still owns only aggregate/Scrum bootstrap. Wiring
  provisioning into a future application service remains a later slice, not a production fake hook.
- Live Jira behavior, credentials, deployment, and UAT were explicitly out of scope and remain
  unverified. The single Starlette/httpx deprecation warning is pre-existing baseline noise.

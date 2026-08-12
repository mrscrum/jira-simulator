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

## Fix Round 1 — Important Review Findings

### Finding verification

- Production `SqlAlchemyLiveTeamStore.ensure_bootstrapped` created Scrum state but no projection
  intents; the acceptance alone built project/board/issue commands.
- False review, cancellation, dependency, and member-unavailability outcomes returned no ground
  truth. Dependency also drew again whenever `entered_at < runtime cursor` and emitted another start.
- Long-stay crossing subtracted pause from raw wall duration rather than using
  `BusinessCalendar.elapsed(...).business`.
- Every handler received the original state, and later right-biased write-set merging could replace
  a cancelled closed visit with the dependency handler's open visit.
- The accepted no-migration natural-evaluation schema supports only cancellation/member-
  unavailability owner shapes. Approved visit-triggered dependency uses visit UUID occurrence zero,
  so exactly-once dependency persistence uses ground truth plus the persisted entry cursor; accepted
  continuation is identified by visit pause state and consumes no new draw.

### RED

Exact command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/integration/test_live_team_store.py tests/v2/acceptance/test_live_scrum_fake_jira.py -q
```

Exact pytest summary output:

```text
.....FFFFFFF...FF                                                        [100%]
=================================== FAILURES ===================================
_____ test_due_false_review_rejection_persists_evaluation_without_activity _____
E       IndexError: tuple index out of range
_______ test_due_false_cancellation_persists_evaluation_without_activity _______
E       IndexError: tuple index out of range
___________ test_due_false_dependency_is_recorded_once_for_the_entry ___________
E           AssertionError: dependency outcome was redrawn
______ test_due_false_unavailability_persists_evaluation_without_activity ______
E       IndexError: tuple index out of range
______ test_dependency_continuation_does_not_redraw_or_emit_another_start ______
E           AssertionError: dependency outcome was redrawn
________ test_long_stay_does_not_cross_during_non_business_weekend_time ________
E       AssertionError: assert (ActivityEven...te_version=1)) == ()
_____ test_cancellation_has_terminal_precedence_over_same_tick_dependency ______
E               ValueError: open visit status must match current work status
______ test_store_bootstrap_enqueues_dependency_ordered_jira_provisioning ______
E       AssertionError: assert [] == ['CREATE_PROJ...CREATE_BOARD']
_______ test_live_scrum_converges_after_restart_outage_and_receipt_retry _______
E       assert 0 == 1
=========================== short test summary info ============================
FAILED tests/v2/unit/test_risks.py::test_due_false_review_rejection_persists_evaluation_without_activity
FAILED tests/v2/unit/test_risks.py::test_due_false_cancellation_persists_evaluation_without_activity
FAILED tests/v2/unit/test_risks.py::test_due_false_dependency_is_recorded_once_for_the_entry
FAILED tests/v2/unit/test_risks.py::test_due_false_unavailability_persists_evaluation_without_activity
FAILED tests/v2/unit/test_risks.py::test_dependency_continuation_does_not_redraw_or_emit_another_start
FAILED tests/v2/unit/test_risks.py::test_long_stay_does_not_cross_during_non_business_weekend_time
FAILED tests/v2/unit/test_risks.py::test_cancellation_has_terminal_precedence_over_same_tick_dependency
FAILED tests/v2/integration/test_live_team_store.py::test_store_bootstrap_enqueues_dependency_ordered_jira_provisioning
FAILED tests/v2/acceptance/test_live_scrum_fake_jira.py::test_live_scrum_converges_after_restart_outage_and_receipt_retry
9 failed, 8 passed in 1.78s
```

The failures directly demonstrated the five reviewed defects before any production edit.

### Implementation

- Added `compose_jira_provisioning`, a small production application composer for logical local-ID
  project, board, and initial-issue intents. Live bootstrap appends its projection-only slice through
  existing UOW persistence in the same transaction and idempotently replays it.
- Removed the acceptance-only provisioning command path; the vertical now enters provisioning only
  through supported production bootstrap.
- Recorded false due decisions as `RISK_EVALUATED` ground truth while retaining no activity,
  projection, or mechanical after-image. Cancellation/unavailability still consume their accepted
  Task 6 natural claims atomically.
- Made dependency outcome due only at `visit.entered_at == runtime.simulation_time`; false/true entry
  records once, and an accepted pause continues from persisted visit pause without another draw or
  start record.
- Switched long-stay crossing to business-service elapsed time and evaluated handlers sequentially
  against accumulated state, preserving terminal cancellation precedence.
- Refactored all newly changed handlers and provisioning helpers to at most three arguments and 30
  lines. No migration or new framework was added.

### GREEN and regression

Focused GREEN after refactor:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/integration/test_live_team_store.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/unit/test_scrum_tick.py -q
.................................                                        [100%]
33 passed in 4.43s
```

Expanded affected regression:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/integration/test_live_scheduler.py tests/v2/integration/test_team_tick.py tests/v2/unit/test_scrum_tick.py tests/v2/unit/test_v2_sprint_lifecycle.py tests/v2/unit/test_jira_delivery_worker.py tests/v2/integration/test_jira_delivery_store.py tests/v2/integration/test_live_team_store.py tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py -q
.................................................................        [100%]
65 passed in 8.82s
```

All-v2 regression:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2 -q
........................................................................ [  6%]
........................................................................ [ 12%]
........................................................................ [ 19%]
........................................................................ [ 25%]
........................................................................ [ 32%]
........................................................................ [ 38%]
........................................................................ [ 45%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 64%]
........................................................................ [ 71%]
........................................................................ [ 77%]
........................................................................ [ 84%]
........................................................................ [ 90%]
........................................................................ [ 97%]
.................................                                        [100%]
=============================== warnings summary ===============================
../.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/.worktrees/v2-live-simulator/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1113 passed, 1 warning in 40.75s
```

### Ruff, Alembic, and no-migration evidence

```text
cd backend && ../.venv/bin/python -m ruff check app/v2 tests/v2
All checks passed!

cd backend && ../.venv/bin/python -m ruff check app/integrations/v2_jira_intent_adapter.py
All checks passed!

cd backend && ../.venv/bin/python -m alembic heads
016 (head)

cd backend && git diff --name-only 11ded36 -- alembic/versions
[no output]

cd backend && git diff --check
[no output]
```

### Self-review and concerns

- The acceptance uses no test-only production hook and exercises the production bootstrap/UOW,
  scheduler, durable store, worker, concrete adapter, and public Jira client surface.
- Provider IDs remain adapter-only; composer payloads contain logical fields and local semantic UUIDs.
- False decisions are auditable without creating user-visible activity or state mutation.
- External dependency's fixed visit occurrence intentionally does not expand Task 6's two supported
  counter-backed workday natural-owner shapes; this preserves revision 016 as sole head.
- Live Jira, deployment, push, and UAT remain intentionally unperformed. The sole warning is the
  pre-existing Starlette/httpx deprecation warning.

### Fix-round commit

- Implementation and living docs: `e736bb91e54e03dacd203c1451d48183b416c2e2`
  (`fix: close v2 live loop review gaps`)

## Fix Round 2 — Dependency Continuation Evidence

### Finding verification

`_dependency_continuation` advanced both `queue_microseconds` and `pause_microseconds` for every
continuation delta but returned an empty evidence tuple. The existing continuation unit test
explicitly asserted that omission. Therefore, after two scheduler slices, authoritative state held
one hour of pause while causal ground truth described only the initial 30-minute delta.

### RED

Exact command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py::test_dependency_continuation_records_wait_without_redraw_or_another_start -q
```

Exact output:

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_dependency_continuation_records_wait_without_redraw_or_another_start ___

        assert continued.pause_microseconds == ONE_HOUR_MICROSECONDS
        assert second.activity == ()
        assert second.projection_intents == ()
>       assert len(second.ground_truth) == 1
E       assert 0 == 1
E        +  where 0 = len(())
E        +    where () = RiskEvaluation(state=ScrumStateWriteSet(member_identities=(), member_availability_overlays=(), member_business_date_co...on_evaluations=()), activity=(), ground_truth=(), projection_intents=(), counter_claims=(), natural_decision_claims=()).ground_truth

tests/v2/unit/test_risks.py:259: AssertionError
=========================== short test summary info ============================
FAILED tests/v2/unit/test_risks.py::test_dependency_continuation_records_wait_without_redraw_or_another_start
1 failed in 0.35s
```

The assertion failed for the reviewed reason: the second 30-minute mechanical wait delta had no
atomic causal ground-truth record.

### Implementation

- Kept continuation deterministic from persisted visit pause state and did not invoke the draw
  source.
- Added one `RISK_EVALUATION` ground-truth record for each non-zero committed continuation delta.
  The record is keyed to the same visit plus the continuation cursor and records the wait delta,
  zero progress delta, deterministic continuation outcome, and no Jira intent.
- Used the existing evidence envelope and persistence protocol; no schema, counter, claim, activity,
  projection, or duplicate `EXTERNAL_DEPENDENCY_STARTED` event was added.

### GREEN and regression

Focused GREEN:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py::test_dependency_continuation_records_wait_without_redraw_or_another_start -q
.                                                                        [100%]
1 passed in 0.63s
```

Risk unit regression:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py -q
............                                                             [100%]
12 passed in 1.50s
```

Focused Task 5 command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/integration/test_live_scheduler.py -q
.....................                                                    [100%]
21 passed in 5.31s
```

Affected regression:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/integration/test_live_scheduler.py tests/v2/integration/test_team_tick.py tests/v2/unit/test_scrum_tick.py tests/v2/unit/test_v2_sprint_lifecycle.py tests/v2/unit/test_jira_delivery_worker.py tests/v2/integration/test_jira_delivery_store.py tests/v2/integration/test_live_team_store.py tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py -q
.................................................................        [100%]
65 passed in 7.08s
```

All-v2 regression:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2 -q
........................................................................ [  6%]
........................................................................ [ 12%]
........................................................................ [ 19%]
........................................................................ [ 25%]
........................................................................ [ 32%]
........................................................................ [ 38%]
........................................................................ [ 45%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 64%]
........................................................................ [ 71%]
........................................................................ [ 77%]
........................................................................ [ 84%]
........................................................................ [ 90%]
........................................................................ [ 97%]
.................................                                        [100%]
=============================== warnings summary ===============================
../.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/.worktrees/v2-live-simulator/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1113 passed, 1 warning in 38.60s
```

### Ruff, Alembic, and no-migration evidence

```text
cd backend && ../.venv/bin/python -m ruff check app/v2 tests/v2
All checks passed!

cd backend && ../.venv/bin/python -m ruff check app/integrations/v2_jira_intent_adapter.py
All checks passed!

cd backend && ../.venv/bin/python -m alembic heads
016 (head)

git diff --name-only 0092aae0a1693997241a6d85d558cd0fbf836ea5 -- backend/alembic/versions
[no output]

git diff --check
[no output]
```

### Documentation, self-review, and concerns

- Updated current-state README/agent guidance, changelog, assumptions, milestone summary, and both
  live/risk backlog outcomes to describe atomic continuation evidence.
- The regression's rejecting draw source proves continuation still performs no redraw. Assertions
  also prove no activity or projection, one visit-keyed truth record, and the exact second delta.
- Sequential terminal precedence and entry no-repeat behavior are unchanged; the existing focused
  and full-v2 regressions passed.
- Revision 016 remains the sole head. Live Jira, deployment, push, and UAT remain intentionally
  unperformed. The sole warning is the pre-existing Starlette/httpx deprecation warning.

### Fix-round commit

- Implementation and living docs: `dbeec099e98bc88849c9c782d7144b55c127a2a7`
  (`fix: record dependency continuation evidence`)

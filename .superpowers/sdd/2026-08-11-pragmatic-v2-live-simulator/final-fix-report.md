# Pragmatic v2 final integration correction report

Date: 2026-08-11

Status: COMPLETE

Implementation commit: `5ca529bf3fba78b113642d0181bf038b877991ee`

## Consolidated RED

Tests were written before production edits. Fixture-construction mistakes were corrected before
accepting the RED. The genuine consolidated command was:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_tick.py tests/v2/integration/test_team_tick.py tests/v2/acceptance/test_live_scrum_fake_jira.py -q
```

Exact captured progress and terminal summary:

```text
...............FFF..F.....F                                              [100%]
5 failed, 22 passed in 3.95s
```

The five exact failing tests and assertion deltas captured from their tracebacks were:

```text
tests/v2/unit/test_scrum_tick.py::test_tick_recomputes_dependency_pause_at_the_early_completion_boundary
assert 7200000000 == 1800000000

tests/v2/unit/test_scrum_tick.py::test_tick_stops_at_the_next_due_workday_boundary
assert datetime.datetime(2026, 8, 13, 16, 0, tzinfo=datetime.timezone.utc) == datetime.datetime(2026, 8, 11, 16, 0, tzinfo=datetime.timezone.utc)

tests/v2/unit/test_scrum_tick.py::test_tick_never_evaluates_dependency_for_an_intrinsically_paused_status
the first tick contained external-dependency risk ground truth instead of ()

tests/v2/integration/test_team_tick.py::test_late_bootstrap_uses_the_containing_dst_cadence_and_ticks_forward_after_reload
assert 0 == 1

tests/v2/acceptance/test_live_scrum_fake_jira.py::test_active_bootstrap_maps_its_sprint_before_later_completion
assert None is not None
```

The review-status chronology seam received its own focused RED after the consolidated five:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py::test_review_rejection_is_timestamped_at_its_due_status_boundary -q
F                                                                        [100%]
```

The returned visit was stamped `2026-08-13 19:00:00+00:00` instead of the due closed-visit boundary
`2026-08-13 18:00:00+00:00`; the exact terminal summary was `1 failed in 0.32s`.

## Implementation mapping

1. **Committed-cursor chronology.** `scrum_tick.py` now performs a provisional risk-aware advance;
   if visit calculation shortens the interval, it discards that provisional result and evaluates
   risks again from the original state at the shorter end. A configured `WORKDAY_STARTED` rule
   bounds the candidate at the first working-interval start strictly after the cursor. Effective
   end is never earlier than the persisted cursor. `risks.py` timestamps review rejection and its
   returned visit at the due closed-visit boundary.
2. **Late-start cadence.** `scrum_bootstrap.py` locates the half-open fixed-cadence window containing
   `started_at` through the existing `cadence_boundary`/`BusinessCalendar` semantics, including
   local DST preservation. Sprint ID, ordinal, and next-sprint counter use that window.
3. **Initial active-sprint Jira mapping.** `jira_provisioning.py` adds a bootstrap-only composer that
   appends local-ID `CREATE_SPRINT -> SCOPE_SPRINT -> START_SPRINT` intents after project, board, and
   all initial issues. `live_team_store.py` selects it only for the original `CREATED -> RUNNING`
   transaction; existing runtimes retain base provisioning and planned bootstrap defers lifecycle
   intents. The real store/worker/concrete-adapter fake acceptance proves mapping, active delivery,
   and later completion without FIFO blockage.
4. **Intrinsic-pause exclusion.** `risks.py` returns no dependency entry or continuation records for
   a workflow status whose own service clock is paused. The two-tick regression proves intrinsic
   pause grows only its normal pause clock and cannot manufacture dependency evidence or queue time.

No provider Jira ID was added to a domain payload, no schema or pause-provenance protocol was added,
and the implementation retains the single generic per-team path.

## GREEN and affected regression

Final focused correction command:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_tick.py tests/v2/integration/test_team_tick.py tests/v2/acceptance/test_live_scrum_fake_jira.py -q
...........................                                              [100%]
27 passed in 4.27s
```

Focused review-status regression:

```text
cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py::test_review_rejection_is_timestamped_at_its_due_status_boundary -q
.                                                                        [100%]
1 passed in 0.24s
```

Expanded focused set:

```text
57 passed in 5.86s
```

Affected lifecycle, tick, risk, scheduler, delivery-store/worker, live-store, integration, and fake
Jira regression set:

```text
78 passed in 9.11s
```

The final all-v2 run after refactor was:

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
........................................................................ [ 57%]
........................................................................ [ 64%]
........................................................................ [ 70%]
........................................................................ [ 77%]
........................................................................ [ 83%]
........................................................................ [ 90%]
........................................................................ [ 96%]
.......................................                                  [100%]
=============================== warnings summary ===============================
../.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/pavel.ozolin/Documents/Codex/2026-08-10/https-github-com-mrscrum-jira-simulator/.worktrees/v2-live-simulator/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1119 passed, 1 warning in 38.01s
```

## Ruff, Alembic, migration, shape, and diff

```text
cd backend && ../.venv/bin/python -m ruff check app/v2 tests/v2
All checks passed!

cd backend && ../.venv/bin/python -m alembic heads
016 (head)

git diff --name-only 6a27c068cce6e907bebcdc5d6228c255e83c9dc1 -- backend/alembic
[no output]

git diff --check
[no output]
```

- Revision 016 remains the sole Alembic head and there is no migration diff.
- The AST scan covered all 44 changed/new Python functions, including tests: zero exceeds 30 source
  lines or three explicit arguments (excluding `self`/`cls`).
- Named-path staging and staged whitespace checks were clean.
- Self-review found no provider identity leakage, extra team path, schema expansion, or candidate-end
  state/evidence commit.
- Independent read-only final review found no Critical or Important issue and confirmed all four
  required outcomes. Its stale pre-refactor production shape note was resolved; two long tests were
  also extracted behind short setup helpers before the final verification.
- `stash@{0}` remained exactly `superseded-v2-task7-before-pragmatic-live-loop`.

## Documentation and backlog

- Updated `README.md`, `agent_instruction.md`, and `backlog/v2/README.md` to the current chronology,
  cadence, initial-sprint delivery, next-slice, and limitation boundaries.
- Appended the correction to `changelog.md` and its one dependency-edge assumption to
  `assumptions.md`.
- Marked the exact Stage 1, Stage 2, and Stage 4 outcomes IN PROGRESS before production edits and
  restored them COMPLETE after GREEN, with final correction notes retained.
- Updated this SDD progress ledger and created this durable report.

## Concerns and excluded work

- The all-v2 suite retains one pre-existing FastAPI/Starlette `httpx` deprecation warning.
- Independent review noted a Minor precision gap: the complete active-bootstrap payload graph and
  repeat-active-bootstrap idempotency are not duplicated in a separate store-only test. The required
  public real-store/worker/concrete-adapter fake acceptance proves sprint mapping, activation, and
  later completion, while the existing store provisioning test proves planned deferral.
- Per instruction, no live Jira, deployment, push, UAT, exhaustive fault matrix, hostile type/HMAC
  work, or exact-microsecond machinery was performed.

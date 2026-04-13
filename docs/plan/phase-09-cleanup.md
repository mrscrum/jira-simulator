# Phase 9: Delete Obsolete Code

## Context

Remove old simulation engine components that have been replaced. Keep model files for DB table compatibility but stop importing them in the engine.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Files to DELETE:

### Engine state machine (replaced by workflow_engine.py):
- `backend/app/engine/issue_state_machine.py`

### All event handlers (replaced by distribution-based workflow):
- `backend/app/engine/events/__init__.py`
- `backend/app/engine/events/base.py`
- `backend/app/engine/events/registry.py`
- `backend/app/engine/events/carry_over.py`
- `backend/app/engine/events/move_left.py`
- `backend/app/engine/events/descope.py`
- `backend/app/engine/events/split_story.py`
- `backend/app/engine/events/external_block.py`
- `backend/app/engine/events/unplanned_absence.py`
- `backend/app/engine/events/priority_change.py`
- `backend/app/engine/events/scope_commitment_miss.py`
- `backend/app/engine/events/uneven_load.py`
- `backend/app/engine/events/review_bottleneck.py`
- `backend/app/engine/events/sprint_goal_risk.py`
- `backend/app/engine/events/velocity_drift.py`
- `backend/app/engine/events/stale_issue.py`
- `backend/app/engine/events/onboarding_tax.py`
- `backend/app/engine/events/late_planning.py`
- `backend/app/engine/events/skipped_retro.py`

### Dysfunction API:
- `backend/app/api/routers/dysfunctions.py`

---

## Files to KEEP (DB table compatibility) but stop using:
- `backend/app/models/dysfunction_config.py` — table exists in DB
- `backend/app/models/simulation_event_config.py` — table exists
- `backend/app/models/simulation_event_log.py` — historical data

---

## Imports to clean up:

### `backend/app/engine/__init__.py`
- Remove event imports if present

### `backend/app/main.py`
- Remove `dysfunctions` router include
- Remove any event-related imports

### `backend/app/api/routers/simulation.py`
- Remove imports of IssueState, event registry, dysfunction config
- Remove imports from engine/events/*

---

## Old test files to DELETE or gut:
- `backend/tests/unit/test_issue_state_machine.py`
- `backend/tests/unit/test_events.py` (if exists)
- `backend/tests/unit/test_events_remaining.py` (if exists)
- `backend/tests/unit/test_dysfunction_details.py` (if exists)
- Any test files referencing old event handlers

---

## Dependencies:
- Phase 6 must be working first (new engine doesn't import old code)

## Verification:
- `pytest backend/tests/` passes with no import errors
- `python -c "from app.engine.simulation import SimulationEngine"` works
- No references to deleted files remain in active code (grep for old imports)

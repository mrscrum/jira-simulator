# Phase 10: Tests

## Context

Create comprehensive tests for all new modules and update existing tests. Tests should be written alongside each phase but this document consolidates the full test plan.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## New test files:

### `backend/tests/unit/test_distributions.py` (Phase 1)
- `fit_lognormal` returns correct mu/sigma for known inputs
- `fit_lognormal` with edge cases (very small p25, very large p99)
- `sample_full_time` produces values in reasonable range
- `sample_full_time` returns >= minimum threshold
- `sample_work_time` returns values within [min, max]
- `sample_work_time(0, 0)` returns 0.0
- `sample_sprint_capacity` returns int within [min, max]
- Reproducibility: same seed produces same results

### `backend/tests/unit/test_new_capacity.py` (Phase 3)
- `build_member_states` creates correct initial states
- `find_available_member` returns None when all busy
- `find_available_member` respects role filter with single role
- `find_available_member` respects role filter with multiple roles
- `find_available_member` random selection (statistical test with seed)
- `mark_busy` returns updated immutable dict
- Sticky assignment: assigned member available only to their issue
- Unassigned member available to any issue

### `backend/tests/unit/test_new_sprint_lifecycle.py` (Phase 4)
- `plan_sprint` selects items up to capacity target
- `plan_sprint` respects min capacity (doesn't stop below min)
- `plan_sprint` stops when next item exceeds target and total >= min
- `plan_sprint` with priority randomization produces different orderings
- `plan_sprint` with empty backlog
- `plan_sprint` with single large item exceeding capacity
- `check_sprint_end` True when working days elapsed
- `check_sprint_end` False during sprint
- `handle_carryover` multiplies remaining work by 1.25
- `handle_carryover` preserves completed status work
- `handle_carryover` marks carried_over flag
- `create_next_sprint` correct dates and numbering

### `backend/tests/unit/test_workflow_engine.py` (Phase 5)
- `enter_status` samples times correctly
- `enter_status` emits TRANSITION_ISSUE with correct jira_status
- `enter_status` resets all tracking fields
- `process_item_tick` assigns available worker
- `process_item_tick` no worker available — full_time advances, work does not
- `process_item_tick` work completes and transitions forward
- `process_item_tick` move-left resamples and transitions back
- `process_item_tick` work_time=0 status — no capacity needed
- `process_item_tick` final status → marks Done
- `check_transition_ready` both conditions required
- `check_transition_ready` work_time=0 only needs full_time
- `roll_direction` with 0% move-left always forward
- `roll_direction` with 100% move-left always left
- `roll_direction` respects per-item-type config
- `roll_direction` with no matching config defaults to forward
- Sticky assignment persists across ticks
- Multiple items competing for same role — random assignment

---

## Existing tests to update:

### `backend/tests/unit/test_simulation.py`
- Update to new tick flow (no events, no TickContext)
- Test sprint phase transitions (PLANNING → ACTIVE → COMPLETED)
- Test continuous sprint cycling

### `backend/tests/unit/test_jira_write_queue.py`
- Remove/update tests referencing JIRA_STATUS_MAP
- Add test: raw status name passed through to _resolve_and_transition

---

## Tests to delete:
- Any test files for old events (carry_over, move_left, descope, etc.)
- Tests for IssueState enum transitions
- Tests for DysfunctionConfig

---

## Verification after all phases:
1. `pytest backend/tests/unit/ -v` — all pass
2. `pytest backend/tests/unit/test_distributions.py -v` — distribution math correct
3. `pytest backend/tests/unit/test_workflow_engine.py -v` — core tick logic correct
4. Manual: `POST /simulation/tick` on running instance with configured team
5. Speed-up mode: full sprint cycle completes and Jira updates appear

# Phase 4: New Sprint Lifecycle

## Context

Simplify sprint lifecycle from 5 phases (BACKLOG_PREP → PLANNING → ACTIVE → REVIEW → RETRO) to 3 phases (PLANNING → ACTIVE → COMPLETED). Planning now includes capacity-based item selection. Carryover handling multiplies remaining work by 1.25.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Rewrite: `backend/app/engine/sprint_lifecycle.py`

### Phase enum:

```python
class SprintPhase(StrEnum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
```

### Functions:

```python
def plan_sprint(
    backlog_issues: list[Issue],
    capacity_min: int,
    capacity_max: int,
    priority_randomization: bool,
    rng: random.Random,
) -> tuple[list[Issue], int]:
    """Select items for sprint from prioritized backlog.

    1. If priority_randomization: shuffle backlog order
    2. Draw capacity_target from uniform[min, max]
    3. Pull items in order until next item would exceed target AND total >= min
    4. Returns (selected_issues, capacity_target)
    """

def check_sprint_end(
    sprint: Sprint,
    sim_now: datetime,
    team_timezone: str,
    working_hours_start: int,
    working_hours_end: int,
    holidays: list[str],
) -> bool:
    """Check if sprint calendar time has been reached.
    Uses calendar.working_days_in_range to count elapsed working days."""

def handle_carryover(incomplete_issues: list[Issue]) -> list[Issue]:
    """Process carryover for incomplete items.

    For each item:
    - Current status: remaining work_time *= 1.25, full_time extended proportionally
    - Completed statuses: no change
    - Future statuses: no change
    - Mark carried_over = True
    Returns the modified issues (they go to top of next sprint backlog)."""

def create_next_sprint(
    team: Team,
    prev_sprint: Sprint,
    sprint_number: int,
) -> Sprint:
    """Create the next sprint. Start date = prev sprint end date.
    End date calculated from sprint_length_days working days."""
```

### Sprint planning capacity logic (from requirements):
- Draw capacity_target uniformly from [min, max]
- Pull items from top of backlog in priority order
- Stop when: adding the next item would exceed capacity_target AND total already >= capacity_min
- If total < capacity_min after exhausting backlog, proceed with what's available

### Carryover logic:
- `remaining_work = sampled_work_time - elapsed_work_time`
- `new_remaining_work = remaining_work * 1.25`
- `issue.sampled_work_time = issue.elapsed_work_time + new_remaining_work`
- Proportionally extend full_time similarly
- Reset `work_started = False`, clear `current_worker_id`

---

## Test file: `backend/tests/unit/test_new_sprint_lifecycle.py`

Test cases:
- `plan_sprint` respects min/max capacity bounds
- `plan_sprint` stops when next item would exceed target
- `plan_sprint` with priority randomization shuffles order
- `plan_sprint` with empty backlog returns empty list
- `check_sprint_end` returns True when working days elapsed
- `handle_carryover` multiplies remaining work by 1.25
- `handle_carryover` doesn't change completed/future statuses
- `create_next_sprint` starts where previous ended

---

## Existing files to reference:
- `backend/app/engine/sprint_lifecycle.py` — current 5-phase implementation
- `backend/app/engine/calendar.py` — `working_days_in_range`, `is_working_time` (PRESERVE, reuse)
- `backend/app/models/sprint.py` — Sprint model

## Dependencies:
- Phase 2 (Sprint model with capacity_target, Team model with capacity range)

## What comes next:
- Phase 6 (Simulation Engine) calls these sprint lifecycle functions

# Phase 2: Model Updates

## Context

Update SQLAlchemy models to match the new columns added in the Phase 1 migration. This makes the ORM layer aware of the new fields so subsequent phases can use them.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Files to modify:

### `backend/app/models/team.py`
Add columns:
- `sprint_capacity_min: Mapped[int]` (Integer, default=20)
- `sprint_capacity_max: Mapped[int]` (Integer, default=40)
- `priority_randomization: Mapped[bool]` (Boolean, default=False)
- `first_sprint_start_date: Mapped[datetime | None]` (DateTime, nullable)
- `tick_duration_hours: Mapped[float]` (Float, default=1.0)

### `backend/app/models/issue.py`
Add columns:
- `sampled_full_time: Mapped[float]` (Float, default=0.0)
- `sampled_work_time: Mapped[float]` (Float, default=0.0)
- `elapsed_full_time: Mapped[float]` (Float, default=0.0)
- `elapsed_work_time: Mapped[float]` (Float, default=0.0)
- `work_started: Mapped[bool]` (Boolean, default=False)

Keep all existing columns for backward compatibility.

### `backend/app/models/sprint.py`
Add column:
- `capacity_target: Mapped[int | None]` (Integer, nullable)

### `backend/app/models/workflow_step.py`
Add column:
- `roles_json: Mapped[str | None]` (String, nullable)

Add property:
```python
@property
def roles(self) -> list[str]:
    """Return list of roles. Parses roles_json if set, otherwise falls back to [role_required]."""
    if self.roles_json:
        import json
        return json.loads(self.roles_json)
    return [self.role_required]
```

### `backend/app/models/touch_time_config.py`
Add columns:
- `full_time_p25: Mapped[float | None]` (Float, nullable)
- `full_time_p50: Mapped[float | None]` (Float, nullable)
- `full_time_p99: Mapped[float | None]` (Float, nullable)

### `backend/app/models/move_left_config.py`
Add column to `MoveLeftConfig`:
- `issue_type: Mapped[str | None]` (String, nullable)

### `backend/app/models/member.py`
Change default:
- `max_concurrent_wip` default from 3 to 1

---

## Dependencies:
- Phase 1 migration must be applied first

## What comes next:
- Phase 3 (Capacity) and Phase 4 (Sprint Lifecycle) depend on these model updates

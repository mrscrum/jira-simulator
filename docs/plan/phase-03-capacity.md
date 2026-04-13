# Phase 3: New Capacity Module

## Context

Replace the existing capacity module with a simpler model: each team member works on at most 1 item per tick. No WIP limit tracking beyond a boolean "busy this tick." Members stay assigned to an item until work on the current status is complete (sticky assignment).

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## Rewrite: `backend/app/engine/capacity.py`

### New data structure:

```python
@dataclass(frozen=True)
class MemberTickState:
    member_id: int
    role: str
    busy_this_tick: bool  # already assigned work this tick
    assigned_issue_id: int | None  # sticky: stays until current-status work done
```

### Functions:

```python
def build_member_states(members: list) -> dict[int, MemberTickState]:
    """Create fresh tick states for all active members.
    Each member starts with busy_this_tick=False.
    Preserves assigned_issue_id from member's current assignment (from DB)."""

def find_available_member(
    states: dict[int, MemberTickState],
    roles: list[str],
    rng: random.Random,
) -> MemberTickState | None:
    """Find a random available member matching any of the given roles.
    Available = not busy_this_tick AND (not assigned OR assigned to requesting issue).
    Returns None if no one available."""

def mark_busy(
    states: dict[int, MemberTickState],
    member_id: int,
    issue_id: int,
) -> dict[int, MemberTickState]:
    """Return updated states with member marked busy and assigned to issue.
    Uses dataclass replace() for immutability."""
```

### Key behaviors:
- A member already assigned to an issue (sticky) is "available" only to that same issue
- If multiple items need the same role, assignment is **random** among available members
- `DailyCapacityLog` persistence pattern from old module should be preserved for analytics

---

## Test file: `backend/tests/unit/test_new_capacity.py`

Test cases:
- `build_member_states` creates correct initial states
- `find_available_member` returns None when all busy
- `find_available_member` respects role filter
- `find_available_member` random selection among multiple available
- `mark_busy` returns immutable updated dict
- Sticky assignment: member assigned to issue A is not available for issue B

---

## Existing file to reference:
- `backend/app/engine/capacity.py` — current implementation (DailyCapacityState, frozen dataclass pattern)

## Dependencies:
- Phase 2 (Member model update)

## What comes next:
- Phase 5 (Workflow Engine) uses this capacity module

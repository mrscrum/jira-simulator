"""Per-member capacity tracking for the simulation engine.

New model: each member works on at most 1 item per tick.
Members stay assigned to an item until work on the current status is complete
(sticky assignment).

All functions are pure — no DB dependency.
"""

import random
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class MemberTickState:
    """Immutable per-tick state for a single team member."""

    member_id: int
    role: str
    busy_this_tick: bool  # already assigned work this tick
    assigned_issue_id: int | None  # sticky: stays until current-status work done


def build_member_states(
    members: list[dict],
) -> dict[int, MemberTickState]:
    """Create fresh tick states for all active members.

    Args:
        members: list of dicts with keys: id, role, assigned_issue_id (or None)

    Returns:
        Dict mapping member_id to MemberTickState with busy_this_tick=False.
    """
    states: dict[int, MemberTickState] = {}
    for m in members:
        states[m["id"]] = MemberTickState(
            member_id=m["id"],
            role=m["role"],
            busy_this_tick=False,
            assigned_issue_id=m.get("assigned_issue_id"),
        )
    return states


def find_available_member(
    states: dict[int, MemberTickState],
    roles: list[str],
    issue_id: int,
    rng: random.Random,
) -> MemberTickState | None:
    """Find an available member matching any of the given roles.

    A member is available if:
    - Not busy this tick, AND
    - Either unassigned (assigned_issue_id is None) or assigned to the
      requesting issue (sticky assignment).

    If multiple members are available, one is chosen randomly.

    Args:
        states: current member tick states
        roles: list of acceptable role names
        issue_id: the issue requesting capacity
        rng: Random instance for reproducibility

    Returns:
        The chosen MemberTickState, or None if no one is available.
    """
    role_set = set(roles)
    candidates = [
        s for s in states.values()
        if not s.busy_this_tick
        and s.role in role_set
        and (s.assigned_issue_id is None or s.assigned_issue_id == issue_id)
    ]

    if not candidates:
        return None

    return rng.choice(candidates)


def mark_busy(
    states: dict[int, MemberTickState],
    member_id: int,
    issue_id: int,
) -> dict[int, MemberTickState]:
    """Return updated states with member marked busy and assigned to issue.

    Uses dataclass replace() for immutability.
    """
    current = states[member_id]
    updated = replace(current, busy_this_tick=True, assigned_issue_id=issue_id)
    return {**states, member_id: updated}


def release_assignment(
    states: dict[int, MemberTickState],
    member_id: int,
) -> dict[int, MemberTickState]:
    """Release a member's sticky assignment (e.g., when work on a status completes)."""
    current = states[member_id]
    updated = replace(current, assigned_issue_id=None)
    return {**states, member_id: updated}

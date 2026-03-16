"""Sprint lifecycle — phase management and transitions.

Manages: BACKLOG_PREP → PLANNING → ACTIVE → REVIEW → RETRO → next sprint.
All functions are pure — no DB dependency.
"""

from enum import StrEnum

BACKLOG_DEPTH_MULTIPLIER = 1.5
DONE_STATUSES = {"DONE", "Done", "done"}


class SprintPhase(StrEnum):
    BACKLOG_PREP = "BACKLOG_PREP"
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    RETRO = "RETRO"


def check_phase_advance(
    phase: SprintPhase,
    backlog_depth: int,
    sprint_capacity: int,
    planning_hours_elapsed: float,
    planning_duration_hours: float,
    sprint_days_elapsed: int,
    sprint_length_days: int,
    pause_before_planning: bool,
) -> SprintPhase | None:
    """Check if conditions are met to advance to the next phase.

    Returns the next phase, or None if no advance should happen.
    """
    if phase == SprintPhase.BACKLOG_PREP:
        return _check_backlog_prep(
            backlog_depth, sprint_capacity, pause_before_planning
        )
    if phase == SprintPhase.PLANNING:
        return _check_planning(
            planning_hours_elapsed, planning_duration_hours
        )
    if phase == SprintPhase.ACTIVE:
        return _check_active(sprint_days_elapsed, sprint_length_days)
    if phase == SprintPhase.REVIEW:
        return SprintPhase.RETRO
    if phase == SprintPhase.RETRO:
        return SprintPhase.BACKLOG_PREP
    return None


def _check_backlog_prep(
    backlog_depth: int,
    sprint_capacity: int,
    pause_before_planning: bool,
) -> SprintPhase | None:
    if pause_before_planning:
        return None
    threshold = sprint_capacity * BACKLOG_DEPTH_MULTIPLIER
    if backlog_depth >= threshold:
        return SprintPhase.PLANNING
    return None


def _check_planning(
    hours_elapsed: float,
    duration_hours: float,
) -> SprintPhase | None:
    if hours_elapsed >= duration_hours:
        return SprintPhase.ACTIVE
    return None


def _check_active(
    days_elapsed: int,
    length_days: int,
) -> SprintPhase | None:
    if days_elapsed >= length_days:
        return SprintPhase.REVIEW
    return None


def select_sprint_issues(
    backlog: list[dict],
    strategy: str,
    capacity_points: int,
) -> list[dict]:
    """Select issues from backlog for the sprint.

    Strategies:
    - capacity_fitted: fill up to capacity in priority order
    - point_target: same as capacity_fitted (alias)
    - priority_ordered: all issues in priority order, ignore capacity
    """
    sorted_backlog = sorted(
        backlog,
        key=lambda i: (i.get("backlog_priority") or 999, i["id"]),
    )

    if strategy == "priority_ordered":
        return sorted_backlog

    # capacity_fitted (default)
    selected = []
    total = 0
    for issue in sorted_backlog:
        points = issue.get("story_points") or 0
        if total + points <= capacity_points:
            selected.append(issue)
            total += points
    return selected


def detect_carry_over_issues(sprint_issues: list[dict]) -> list[dict]:
    """Find issues not in DONE at sprint end."""
    return [
        issue for issue in sprint_issues
        if issue.get("status") not in DONE_STATUSES
    ]


def calculate_velocity(completed: int, committed: int) -> float:
    """Calculate velocity ratio: completed / committed."""
    if committed == 0:
        return 0.0
    return completed / committed

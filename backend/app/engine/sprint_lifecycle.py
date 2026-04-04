"""Sprint lifecycle — simplified 3-phase management.

Manages: PLANNING → ACTIVE → COMPLETED → next sprint.
All functions are pure — no DB dependency.
"""

import random
from datetime import datetime, timedelta
from enum import StrEnum


class SprintPhase(StrEnum):
    PLANNING = "PLANNING"
    SIMULATED = "SIMULATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


def plan_sprint(
    backlog_issues: list[dict],
    capacity_min: int,
    capacity_max: int,
    priority_randomization: bool,
    rng: random.Random,
) -> tuple[list[dict], int]:
    """Select items for a sprint from the prioritized backlog.

    1. If priority_randomization is True, shuffle the backlog order.
    2. Draw a capacity_target uniformly from [capacity_min, capacity_max].
    3. Pull items in order until the next item would exceed the target
       AND total already >= capacity_min.
    4. If total < capacity_min after exhausting the backlog, proceed with
       what's available.

    Args:
        backlog_issues: list of issue dicts with keys: id, story_points,
            backlog_priority. Must be pre-sorted by priority (lowest number first)
            unless priority_randomization is True.
        capacity_min: minimum story points for the sprint.
        capacity_max: maximum story points for the sprint.
        rng: Random instance for reproducibility.

    Returns:
        (selected_issues, capacity_target)
    """
    if not backlog_issues:
        target = (
            rng.randint(capacity_min, capacity_max)
            if capacity_min <= capacity_max
            else capacity_min
        )
        return [], target

    ordered = list(backlog_issues)
    if priority_randomization:
        rng.shuffle(ordered)
    else:
        ordered.sort(key=lambda i: (i.get("backlog_priority") or 999, i["id"]))

    target = rng.randint(capacity_min, capacity_max)

    selected: list[dict] = []
    total = 0
    for issue in ordered:
        points = issue.get("story_points") or 0
        if total + points > target and total >= capacity_min:
            break
        selected.append(issue)
        total += points

    return selected, target


def check_sprint_end(
    sprint_start: datetime,
    sprint_length_days: int,
    sim_now: datetime,
) -> bool:
    """Check if the sprint's calendar time has been reached.

    Uses simple day counting (working days are enforced by the tick loop
    only ticking during working hours).

    Args:
        sprint_start: when the sprint started (ACTIVE phase began).
        sprint_length_days: configured sprint length in working days.
        sim_now: current simulation time.

    Returns:
        True if the sprint should end.
    """
    elapsed = sim_now - sprint_start
    elapsed_days = elapsed.total_seconds() / (3600 * 24)
    # Working days: approximate by counting calendar days and multiplying by 5/7
    # More precise counting happens at the tick level (only ticks on working days)
    # Here we use calendar days as an upper bound since ticks only fire on work days
    return elapsed_days >= sprint_length_days


def handle_carryover(issues: list[dict]) -> list[dict]:
    """Process carryover for incomplete items at sprint end.

    For each item's current status:
    - Remaining work_time is multiplied by 1.25 (25% penalty).
    - Full time is extended proportionally.
    - work_started is reset to False, current_worker_id cleared.
    - carried_over flag is set.

    Args:
        issues: list of issue dicts with keys: sampled_work_time,
            elapsed_work_time, sampled_full_time, elapsed_full_time,
            work_started, current_worker_id, carried_over.

    Returns:
        The same list of dicts, mutated in place for convenience.
    """
    for issue in issues:
        remaining_work = issue["sampled_work_time"] - issue["elapsed_work_time"]
        if remaining_work > 0:
            new_remaining_work = remaining_work * 1.25
            issue["sampled_work_time"] = issue["elapsed_work_time"] + new_remaining_work

        remaining_full = issue["sampled_full_time"] - issue["elapsed_full_time"]
        if remaining_full > 0:
            new_remaining_full = remaining_full * 1.25
            issue["sampled_full_time"] = issue["elapsed_full_time"] + new_remaining_full

        issue["work_started"] = False
        issue["current_worker_id"] = None
        issue["carried_over"] = True

    return issues


def create_next_sprint_dates(
    prev_end_date: datetime,
    sprint_length_days: int,
) -> tuple[datetime, datetime]:
    """Calculate start and end dates for the next sprint.

    Next sprint starts where the previous one ended.
    End date is sprint_length_days calendar days later (working days
    are enforced by the tick loop).

    Returns:
        (start_date, end_date)
    """
    start = prev_end_date
    end = start + timedelta(days=sprint_length_days)
    return start, end


def calculate_velocity(completed: int, committed: int) -> float:
    """Calculate velocity ratio: completed / committed."""
    if committed == 0:
        return 0.0
    return completed / committed

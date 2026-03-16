"""Per-person capacity tracking, WIP enforcement, touch-time advancement.

All functions are pure — no DB dependency. Accept data as arguments.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime

from app.engine.calendar import is_working_time

DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]


@dataclass(frozen=True)
class DailyCapacityState:
    member_id: int
    date: date
    total_hours: float
    consumed_hours: float
    available_hours: float
    active_wip_count: int
    is_working: bool


def calculate_daily_capacity(
    member_id: int,
    daily_capacity_hours: float,
    timezone_name: str,
    working_hours_start: int,
    working_hours_end: int,
    holidays: list[date],
    working_days: list[int],
    at: datetime,
) -> DailyCapacityState:
    """Build a fresh capacity state for a member at the given time."""
    working = is_working_time(
        timezone_name, working_hours_start, working_hours_end,
        holidays, working_days, at,
    )
    if not working:
        return DailyCapacityState(
            member_id=member_id,
            date=at.date(),
            total_hours=0.0,
            consumed_hours=0.0,
            available_hours=0.0,
            active_wip_count=0,
            is_working=False,
        )
    return DailyCapacityState(
        member_id=member_id,
        date=at.date(),
        total_hours=daily_capacity_hours,
        consumed_hours=0.0,
        available_hours=daily_capacity_hours,
        active_wip_count=0,
        is_working=True,
    )


def can_accept_work(
    capacity: DailyCapacityState,
    max_wip: int,
    wip_contribution: float = 1.0,
) -> bool:
    """Check if a member can accept new work."""
    if not capacity.is_working:
        return False
    if capacity.available_hours <= 0:
        return False
    return capacity.active_wip_count + wip_contribution <= max_wip


def consume_capacity(
    capacity: DailyCapacityState,
    hours: float,
    wip_contribution: float = 1.0,
) -> DailyCapacityState:
    """Consume hours and WIP from a capacity state."""
    actual_hours = min(hours, capacity.available_hours)
    new_consumed = capacity.consumed_hours + actual_hours
    new_available = capacity.total_hours - new_consumed
    new_wip = capacity.active_wip_count + int(wip_contribution)
    return replace(
        capacity,
        consumed_hours=new_consumed,
        available_hours=max(0.0, new_available),
        active_wip_count=new_wip,
    )


def advance_touch_time(
    touch_time_remaining: float,
    capacity: DailyCapacityState,
    tick_hours: float,
) -> tuple[float, DailyCapacityState]:
    """Burn down touch time, constrained by available capacity.

    Returns (new_touch_time_remaining, updated_capacity).
    """
    if touch_time_remaining <= 0:
        return 0.0, capacity

    hours_to_advance = min(
        touch_time_remaining,
        tick_hours,
        capacity.available_hours,
    )
    new_remaining = touch_time_remaining - hours_to_advance
    new_consumed = capacity.consumed_hours + hours_to_advance
    new_available = capacity.total_hours - new_consumed
    updated = replace(
        capacity,
        consumed_hours=new_consumed,
        available_hours=max(0.0, new_available),
    )
    return new_remaining, updated


def get_available_workers(
    members: list[dict],
    role: str,
    max_wip: int,
    wip_contribution: float = 1.0,
) -> list[dict]:
    """Filter members by role and availability."""
    result = []
    for member in members:
        if member["role"] != role:
            continue
        cap = member["capacity"]
        if can_accept_work(cap, max_wip, wip_contribution):
            result.append(member)
    return result

"""Business day, working hours, timezone, and holiday calculations.

All functions are pure — no DB dependency. Accept configuration as arguments.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]  # Monday–Friday
MAX_LOOKAHEAD_DAYS = 30


def is_working_time(
    tz_name: str,
    start_hour: int,
    end_hour: int,
    holidays: list[date],
    working_days: list[int],
    at: datetime,
) -> bool:
    """Check if the given UTC datetime falls within working hours."""
    local_dt = _to_local(at, tz_name)
    if local_dt.weekday() not in working_days:
        return False
    if local_dt.date() in holidays:
        return False
    return start_hour <= local_dt.hour < end_hour


def next_working_moment(
    tz_name: str,
    start_hour: int,
    end_hour: int,
    holidays: list[date],
    working_days: list[int],
    after: datetime,
) -> datetime:
    """Find the next datetime that falls within working hours."""
    local_dt = _to_local(after, tz_name)
    tz = ZoneInfo(tz_name)

    if _is_working_local(local_dt, start_hour, end_hour, holidays, working_days):
        return after

    # If before start on a working day, jump to start
    if (
        local_dt.weekday() in working_days
        and local_dt.date() not in holidays
        and local_dt.hour < start_hour
    ):
        candidate = local_dt.replace(
            hour=start_hour, minute=0, second=0, microsecond=0
        )
        return candidate.astimezone(UTC)

    # Move to next day's start and scan forward
    current_date = local_dt.date() + timedelta(days=1)
    for _ in range(MAX_LOOKAHEAD_DAYS):
        if (
            current_date.weekday() in working_days
            and current_date not in holidays
        ):
            candidate = datetime(
                current_date.year,
                current_date.month,
                current_date.day,
                start_hour,
                0,
                0,
                tzinfo=tz,
            )
            return candidate.astimezone(UTC)
        current_date += timedelta(days=1)

    # Fallback — should not happen with reasonable config
    return after


def working_hours_remaining_today(
    tz_name: str,
    start_hour: int,
    end_hour: int,
    at: datetime,
) -> float:
    """Return hours remaining in the working day from the given time."""
    local_dt = _to_local(at, tz_name)
    if local_dt.hour >= end_hour:
        return 0.0
    if local_dt.hour < start_hour:
        return float(end_hour - start_hour)
    remaining_seconds = (
        (end_hour * 3600)
        - (local_dt.hour * 3600 + local_dt.minute * 60 + local_dt.second)
    )
    return max(0.0, remaining_seconds / 3600.0)


def working_days_in_range(
    tz_name: str,
    start_hour: int,
    end_hour: int,
    holidays: list[date],
    working_days: list[int],
    start: date,
    end: date,
) -> int:
    """Count business days in an inclusive date range."""
    count = 0
    current = start
    while current <= end:
        if current.weekday() in working_days and current not in holidays:
            count += 1
        current += timedelta(days=1)
    return count


def handoff_lag_hours(
    sender_tz: str,
    sender_end_hour: int,
    receiver_tz: str,
    receiver_start_hour: int,
    receiver_holidays: list[date],
    receiver_working_days: list[int],
    at: datetime,
) -> float:
    """Calculate hours until the receiver's next working moment."""
    next_moment = next_working_moment(
        receiver_tz,
        receiver_start_hour,
        receiver_start_hour + 8,  # assume 8-hour day
        receiver_holidays,
        receiver_working_days,
        at,
    )
    delta = next_moment - at
    lag = delta.total_seconds() / 3600.0
    return max(0.0, lag)


def _to_local(dt: datetime, tz_name: str) -> datetime:
    """Convert a datetime to the given timezone."""
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz)


def _is_working_local(
    local_dt: datetime,
    start_hour: int,
    end_hour: int,
    holidays: list[date],
    working_days: list[int],
) -> bool:
    """Check if a local datetime is within working hours."""
    if local_dt.weekday() not in working_days:
        return False
    if local_dt.date() in holidays:
        return False
    return start_hour <= local_dt.hour < end_hour

"""Sprint overlap detection and next-start-date suggestion.

Pure utility functions for sprint date management.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.engine.calendar import DEFAULT_WORKING_DAYS, next_working_moment
from app.engine.precompute import _compute_sprint_end, _parse_holidays


def check_sprint_overlap(
    session: Session,
    team_id: int,
    start: datetime,
    end: datetime,
    exclude_id: int | None = None,
) -> dict | None:
    """Return the first overlapping sprint, or None.

    Two sprints overlap when: existing.start < new.end AND existing.end > new.start
    """
    from app.models.sprint import Sprint

    query = (
        session.query(Sprint)
        .filter_by(team_id=team_id)
        .filter(Sprint.start_date < end, Sprint.end_date > start)
    )
    if exclude_id is not None:
        query = query.filter(Sprint.id != exclude_id)

    overlap = query.first()
    if overlap is None:
        return None
    return {
        "id": overlap.id,
        "name": overlap.name,
        "start_date": overlap.start_date.isoformat(),
        "end_date": overlap.end_date.isoformat(),
    }


def suggest_next_start(
    session: Session,
    team_id: int,
    team,
) -> dict:
    """Suggest start and end dates for the next sprint.

    Looks at the latest sprint's end_date and returns the next business day.
    Falls back to team.first_sprint_start_date or next business day from now.

    Returns dict with suggested_start, suggested_end, and sprint_number.
    """
    from app.models.sprint import Sprint

    holidays = _parse_holidays(team.holidays)
    working_days = DEFAULT_WORKING_DAYS

    # Find latest sprint by end_date
    last_sprint = (
        session.query(Sprint)
        .filter_by(team_id=team_id)
        .order_by(Sprint.end_date.desc())
        .first()
    )

    next_number = 1
    if last_sprint:
        next_number = (last_sprint.sprint_number or 0) + 1
        # Start on the next business day after the last sprint ends
        after = last_sprint.end_date
        if after.tzinfo is None:
            after = after.replace(tzinfo=UTC)
        suggested_start = next_working_moment(
            team.timezone,
            team.working_hours_start,
            team.working_hours_end,
            holidays,
            working_days,
            after,
        )
    elif team.first_sprint_start_date:
        suggested_start = team.first_sprint_start_date
        if suggested_start.tzinfo is None:
            suggested_start = suggested_start.replace(tzinfo=UTC)
    else:
        now = datetime.now(UTC)
        suggested_start = next_working_moment(
            team.timezone,
            team.working_hours_start,
            team.working_hours_end,
            holidays,
            working_days,
            now,
        )

    suggested_end = _compute_sprint_end(
        suggested_start,
        team.sprint_length_days,
        team.timezone,
        team.working_hours_start,
        team.working_hours_end,
        holidays,
        working_days,
    )

    return {
        "suggested_start": suggested_start.isoformat(),
        "suggested_end": suggested_end.isoformat(),
        "sprint_number": next_number,
        "sprint_length_days": team.sprint_length_days,
    }

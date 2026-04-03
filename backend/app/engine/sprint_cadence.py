"""Sprint cadence — automatic sprint scheduling based on recurrence rules.

Teams configure a cadence (e.g., "every second Wednesday, 9 AM") using
RRULE strings.  A periodic job checks if a new sprint should start and
triggers pre-computation automatically.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Minimum gap between sprint end and next auto-trigger
MIN_GAP_HOURS = 1


def get_next_sprint_start(
    cadence_rule: str,
    cadence_time: str,
    timezone: str,
    after: datetime,
) -> datetime | None:
    """Compute the next sprint start datetime from the RRULE.

    Args:
        cadence_rule: RRULE string (e.g., "FREQ=WEEKLY;INTERVAL=2;BYDAY=WE")
        cadence_time: time string (e.g., "09:00")
        timezone: team timezone (e.g., "America/New_York")
        after: find next occurrence after this datetime

    Returns:
        Next sprint start as UTC datetime, or None if can't compute.
    """
    try:
        from dateutil.rrule import rrulestr
    except ImportError:
        logger.error("python-dateutil is required for sprint cadence")
        return None

    try:
        tz = ZoneInfo(timezone)
    except (KeyError, ValueError):
        logger.error("Invalid timezone: %s", timezone)
        return None

    try:
        hour, minute = (int(p) for p in cadence_time.split(":"))
    except (ValueError, AttributeError):
        logger.error("Invalid cadence time: %s", cadence_time)
        return None

    try:
        rule = rrulestr(cadence_rule, dtstart=after.astimezone(tz))
    except (ValueError, TypeError) as exc:
        logger.error("Invalid RRULE: %s — %s", cadence_rule, exc)
        return None

    # Find next occurrence after `after`
    local_after = after.astimezone(tz)
    next_occurrence = rule.after(local_after, inc=False)
    if next_occurrence is None:
        return None

    # Set the time component
    candidate = next_occurrence.replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    )
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=tz)

    # If the candidate is before `after`, get the one after that
    if candidate.astimezone(UTC) <= after:
        candidate = rule.after(candidate, inc=False)
        if candidate is None:
            return None
        candidate = candidate.replace(
            hour=hour, minute=minute, second=0, microsecond=0,
        )
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=tz)

    return candidate.astimezone(UTC)


class SprintCadenceChecker:
    """Checks if teams need a new sprint triggered based on their cadence."""

    def __init__(self, session_factory: Any, simulation_engine: Any):
        self._session_factory = session_factory
        self._engine = simulation_engine

    async def check_and_trigger(self) -> list[int]:
        """Check all active teams and trigger pre-computation where due.

        Returns:
            List of team_ids that were triggered.
        """
        from app.models.team import Team

        session: Session = self._session_factory()
        triggered: list[int] = []
        now = datetime.now(UTC)

        try:
            teams = (
                session.query(Team)
                .filter(
                    Team.is_active.is_(True),
                    Team.sprint_auto_schedule.is_(True),
                    Team.sprint_cadence_rule.isnot(None),
                    Team.sprint_cadence_time.isnot(None),
                )
                .all()
            )

            for team in teams:
                if self._should_trigger(session, team, now):
                    try:
                        await self._engine.compute_and_schedule_sprint(team.id)
                        triggered.append(team.id)
                        logger.info(
                            "Auto-triggered sprint precomputation for team %d (%s)",
                            team.id, team.name,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to auto-trigger sprint for team %d",
                            team.id,
                        )

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Sprint cadence check failed")
        finally:
            session.close()

        return triggered

    def _should_trigger(self, session: Session, team, now: datetime) -> bool:
        """Determine if a team needs a new sprint triggered.

        True if:
        1. Team has cadence configured
        2. No active or planning sprint exists
        3. Current time >= next scheduled sprint start
        """
        from app.engine.sprint_lifecycle import SprintPhase
        from app.models.sprint import Sprint

        # Check for existing active/planning sprint
        active_sprint = (
            session.query(Sprint)
            .filter(
                Sprint.team_id == team.id,
                Sprint.phase.in_([
                    SprintPhase.PLANNING.value,
                    SprintPhase.ACTIVE.value,
                ]),
            )
            .first()
        )
        if active_sprint is not None:
            return False

        # Find last completed sprint
        last_sprint = (
            session.query(Sprint)
            .filter_by(team_id=team.id)
            .order_by(Sprint.end_date.desc())
            .first()
        )

        reference_time = last_sprint.end_date if last_sprint else now - timedelta(days=1)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)

        next_start = get_next_sprint_start(
            team.sprint_cadence_rule,
            team.sprint_cadence_time,
            team.timezone,
            reference_time,
        )
        if next_start is None:
            return False

        return now >= next_start

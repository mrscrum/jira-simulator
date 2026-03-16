"""Master tick orchestrator — drives the simulation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.engine.issue_state_machine import JiraWriteAction

logger = logging.getLogger(__name__)


class SimulationState(StrEnum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


@dataclass
class TeamTickResult:
    team_id: int
    jira_actions_count: int
    events_fired: list[str]
    error: str | None


class SimulationEngine:
    """Tick-based simulation engine coordinating all modules."""

    def __init__(
        self,
        session_factory,
        write_queue,
    ):
        self._session_factory = session_factory
        self._write_queue = write_queue
        self._state = SimulationState.STOPPED
        self._paused_teams: set[int] = set()
        self._last_successful_tick: datetime | None = None
        self._tick_count: int = 0
        self.tick_interval_minutes: int = 5

    @property
    def state(self) -> SimulationState:
        return self._state

    @property
    def paused_teams(self) -> set[int]:
        return self._paused_teams.copy()

    @property
    def last_successful_tick(self) -> datetime | None:
        return self._last_successful_tick

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def start(self) -> None:
        self._state = SimulationState.RUNNING
        logger.info("Simulation engine started")

    def pause(self) -> None:
        self._state = SimulationState.PAUSED
        logger.info("Simulation engine paused")

    def resume(self) -> None:
        self._state = SimulationState.RUNNING
        logger.info("Simulation engine resumed")

    def stop(self) -> None:
        self._state = SimulationState.STOPPED
        logger.info("Simulation engine stopped")

    def pause_team(self, team_id: int) -> None:
        self._paused_teams.add(team_id)
        logger.info("Team %d paused", team_id)

    def resume_team(self, team_id: int) -> None:
        self._paused_teams.discard(team_id)
        logger.info("Team %d resumed", team_id)

    def should_tick(self) -> bool:
        return self._state == SimulationState.RUNNING

    def enqueue_actions(
        self, team_id: int, actions: list[JiraWriteAction],
    ) -> None:
        """Hand off JiraWriteActions to the write queue."""
        for action in actions:
            self._write_queue.enqueue(
                team_id=team_id,
                operation_type=action.operation_type,
                payload=action.payload,
                issue_id=action.issue_id,
            )

    def record_tick_success(self, at: datetime) -> None:
        self._last_successful_tick = at
        self._tick_count += 1

    async def tick(self) -> list[TeamTickResult]:
        """Execute one simulation tick across all active teams.

        Tick sequence:
        1. Calendar check per team
        2. Per-team loop: capacity reset, sprint phase, issue advancement,
           event rolls, detections
        3. Backlog maintenance
        4. Populate write queue
        5. Persist state snapshot
        6. Record last_successful_tick
        """
        if not self.should_tick():
            return []

        results: list[TeamTickResult] = []
        session = self._session_factory()

        try:
            from app.models.team import Team
            teams = session.query(Team).all()

            for team in teams:
                if team.id in self._paused_teams:
                    continue
                result = await self._tick_team(session, team)
                results.append(result)

            session.commit()
            self.record_tick_success(datetime.now())
        except Exception as e:
            session.rollback()
            logger.exception("Tick failed: %s", e)
            raise
        finally:
            session.close()

        return results

    async def _tick_team(self, session, team) -> TeamTickResult:
        """Process a single team within a tick."""
        jira_actions: list[JiraWriteAction] = []
        events_fired: list[str] = []

        try:
            # Placeholder for full tick sequence per team.
            # Steps: capacity reset, sprint phase check,
            # issue advancement, event rolls, detections.
            self.enqueue_actions(team.id, jira_actions)

            return TeamTickResult(
                team_id=team.id,
                jira_actions_count=len(jira_actions),
                events_fired=events_fired,
                error=None,
            )
        except Exception as e:
            logger.exception("Team %d tick failed: %s", team.id, e)
            return TeamTickResult(
                team_id=team.id,
                jira_actions_count=0,
                events_fired=events_fired,
                error=str(e),
            )

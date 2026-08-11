"""Sequential persisted scheduling and restart orchestration for v2 teams."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.authoritative_slice import AuthoritativeTickSliceCommit
from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    GroundTruthDetails,
    GroundTruthRecordDraft,
    RuntimeAdvance,
    TickSliceCommit,
)
from app.v2.domain.scrum_state import ScrumStateWriteSet, SprintLifecycle
from app.v2.domain.scrum_tick import TickRequest
from app.v2.persistence.due_team_store import DueTeamStore
from app.v2.persistence.live_team_store import LiveTeamStore
from app.v2.persistence.unit_of_work import V2UnitOfWork

logger = logging.getLogger(__name__)


class TeamTickAdvancer(Protocol):
    def advance(self, request: TickRequest) -> object: ...


class ReconcileBeforeResume(Protocol):
    def reconcile(self, team_id: UUID, as_of: datetime) -> None: ...


@dataclass(frozen=True)
class SchedulerDependencies:
    due_teams: DueTeamStore
    tick_service: TeamTickAdvancer
    live_teams: LiveTeamStore
    unit_of_work: V2UnitOfWork
    reconciler: ReconcileBeforeResume


@dataclass(frozen=True)
class SchedulerRunResult:
    attempted: tuple[UUID, ...]
    succeeded: tuple[UUID, ...]
    failed: tuple[UUID, ...]


@dataclass(frozen=True)
class _DowntimeWindow:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class _DowntimeDraft:
    advances_to: datetime
    recorded_at: datetime
    activity: tuple[ActivityEventDraft, ...]
    ground_truth: tuple[GroundTruthRecordDraft, ...]


class LiveScheduler:
    """Uses one sequential team path and isolates failures by team."""

    def __init__(self, dependencies: SchedulerDependencies) -> None:
        self._dependencies = dependencies

    def run_due(self, as_of: datetime) -> SchedulerRunResult:
        instant = _utc(as_of)
        team_ids = tuple(sorted(self._dependencies.due_teams.due_team_ids(instant), key=str))
        return self._run(team_ids, lambda team_id: self._advance(team_id, instant))

    def resume_after_restart(self, as_of: datetime) -> SchedulerRunResult:
        instant = _utc(as_of)
        team_ids = tuple(sorted(self._dependencies.due_teams.running_team_ids(), key=str))
        return self._run(team_ids, lambda team_id: self._resume(team_id, instant))

    def _run(
        self, team_ids: tuple[UUID, ...], operation: Callable[[UUID], None]
    ) -> SchedulerRunResult:
        succeeded: list[UUID] = []
        failed: list[UUID] = []
        for team_id in team_ids:
            try:
                operation(team_id)
                succeeded.append(team_id)
            except Exception:
                logger.exception("v2 team scheduling failed", extra={"team_id": str(team_id)})
                failed.append(team_id)
        return SchedulerRunResult(team_ids, tuple(succeeded), tuple(failed))

    def _advance(self, team_id: UUID, as_of: datetime) -> None:
        while True:
            before = self._dependencies.live_teams.load(team_id)
            self._dependencies.tick_service.advance(TickRequest(team_id, as_of, as_of))
            after = self._dependencies.live_teams.load(team_id)
            if after.aggregate.runtime.version <= before.aggregate.runtime.version:
                raise RuntimeError("team tick did not advance the persisted runtime version")
            if _caught_up(after, as_of):
                return

    def _resume(self, team_id: UUID, as_of: datetime) -> None:
        dependencies = self._dependencies
        dependencies.reconciler.reconcile(team_id, as_of)
        initial = dependencies.live_teams.load(team_id)
        downtime_start = initial.aggregate.runtime.simulation_time
        if downtime_start >= as_of:
            return
        downtime = _DowntimeWindow(downtime_start, as_of)
        record_downtime = True
        while True:
            state = dependencies.live_teams.load(team_id)
            boundary = _next_boundary(state, as_of)
            if boundary is None:
                if record_downtime:
                    self._skip_recorded_downtime(state, as_of, downtime)
                else:
                    self._skip_silent_downtime(state, as_of, as_of)
                return
            cursor = state.aggregate.runtime.simulation_time
            if cursor < boundary:
                if record_downtime:
                    self._skip_recorded_downtime(state, boundary, downtime)
                else:
                    self._skip_silent_downtime(state, boundary, as_of)
                record_downtime = False
            self._advance(team_id, boundary)

    def _skip_recorded_downtime(
        self,
        state: LiveTeamState,
        ends_at: datetime,
        downtime: _DowntimeWindow,
    ) -> None:
        key = _downtime_key(state, ends_at)
        activity, truth = _downtime_records(state, key, downtime)
        draft = _DowntimeDraft(ends_at, downtime.ends_at, activity, truth)
        command = _downtime_command(state, draft)
        self._dependencies.unit_of_work.commit_authoritative_slice(command)

    def _skip_silent_downtime(
        self, state: LiveTeamState, ends_at: datetime, recorded_at: datetime
    ) -> None:
        command = _downtime_command(state, _DowntimeDraft(ends_at, recorded_at, (), ()))
        self._dependencies.unit_of_work.commit_authoritative_slice(command)


def _next_boundary(state: LiveTeamState, as_of: datetime) -> datetime | None:
    cursor = state.aggregate.runtime.simulation_time
    boundaries = tuple(
        instant
        for sprint in state.scrum.sprints
        for instant in (_boundary_for(sprint),)
        if instant is not None and cursor <= instant <= as_of
    )
    return min(boundaries) if boundaries else None


def _caught_up(state: LiveTeamState, as_of: datetime) -> bool:
    runtime = state.aggregate.runtime
    return runtime.simulation_time >= as_of and _next_boundary(state, as_of) is None


def _boundary_for(sprint) -> datetime | None:
    if sprint.lifecycle is SprintLifecycle.PLANNED:
        return sprint.planned_start_at
    if sprint.lifecycle is SprintLifecycle.ACTIVE:
        return sprint.planned_end_at
    return None


def _downtime_command(state: LiveTeamState, draft: _DowntimeDraft) -> AuthoritativeTickSliceCommit:
    runtime = state.aggregate.runtime
    key = _downtime_key(state, draft.advances_to)
    live_slice = TickSliceCommit(
        semantic_uuid(f"commit/{key}"),
        runtime.team_id,
        runtime.run_id,
        runtime.version,
        RuntimeAdvance(runtime.state, draft.advances_to, draft.advances_to),
        draft.activity,
        draft.ground_truth,
        (),
        draft.recorded_at,
    )
    return AuthoritativeTickSliceCommit(live_slice, ScrumStateWriteSet(), (), ())


def _downtime_records(
    state: LiveTeamState, key: str, downtime: _DowntimeWindow
) -> tuple[tuple[ActivityEventDraft, ...], tuple[GroundTruthRecordDraft, ...]]:
    payload = {
        "starts_at": downtime.starts_at.isoformat(),
        "ends_at": downtime.ends_at.isoformat(),
    }
    envelope = DraftEnvelope(f"{key}/downtime", "1.0", downtime.ends_at, payload)
    runtime = state.aggregate.runtime
    activity = ActivityEventDraft.create(
        envelope,
        ActivityDetails("DOWNTIME_SKIPPED", "RUNTIME", runtime.id, runtime.version + 1),
    )
    truth = GroundTruthRecordDraft.create(
        envelope,
        GroundTruthDetails("DOWNTIME_SKIPPED", "SIMULATOR_V2"),
    )
    return (activity,), (truth,)


def _downtime_key(state: LiveTeamState, ends_at: datetime) -> str:
    runtime = state.aggregate.runtime
    return f"restart/{runtime.team_id}/{runtime.run_id}/{runtime.version}/{ends_at.isoformat()}"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be aware")
    return value.astimezone(UTC)

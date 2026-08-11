"""APScheduler hosting for the persisted v2 live-team scheduler."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session, sessionmaker

from app.v2.application.live_scheduler import (
    LiveScheduler,
    SchedulerDependencies,
    SchedulerRunResult,
)
from app.v2.application.team_tick import TeamTickService
from app.v2.persistence.due_team_store import SqlAlchemyDueTeamStore
from app.v2.persistence.live_team_store import SqlAlchemyLiveTeamStore
from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork

V2_POLL_INTERVAL_SECONDS = 30


class DueRunner(Protocol):
    def run_due(self, as_of: datetime) -> SchedulerRunResult | object: ...


class NoopObservationReconciler:
    """Local supported-observation seam until Jira reconciliation is connected."""

    def reconcile(self, team_id: UUID, as_of: datetime) -> None:
        del team_id, as_of


def build_v2_scheduler(session_factory: sessionmaker[Session]) -> LiveScheduler:
    """Compose the one persisted execution path used for every v2 team."""
    store = SqlAlchemyLiveTeamStore(session_factory)
    unit_of_work = SqlAlchemyV2UnitOfWork(session_factory)
    dependencies = SchedulerDependencies(
        SqlAlchemyDueTeamStore(session_factory),
        TeamTickService(store, unit_of_work),
        store,
        unit_of_work,
        NoopObservationReconciler(),
    )
    return LiveScheduler(dependencies)


def register_v2_job(
    scheduler: AsyncIOScheduler,
    live_scheduler: DueRunner,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Register APScheduler only as a poller over persisted wake authority."""

    def poll_due_teams() -> None:
        live_scheduler.run_due(now())

    scheduler.add_job(
        poll_due_teams,
        trigger=IntervalTrigger(seconds=V2_POLL_INTERVAL_SECONDS),
        id="v2_live_scheduler",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def resume_and_register_v2(
    scheduler: AsyncIOScheduler,
    session_factory: sessionmaker[Session],
    as_of: datetime,
) -> LiveScheduler:
    """Reconcile persisted running teams before enabling future due polling."""
    live_scheduler = build_v2_scheduler(session_factory)
    live_scheduler.resume_after_restart(as_of)
    register_v2_job(scheduler, live_scheduler)
    return live_scheduler

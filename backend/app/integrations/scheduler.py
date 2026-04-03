import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL_SECONDS = 60
DAILY_DIGEST_HOUR = 8
DAILY_DIGEST_MINUTE = 0

TICK_INTERVAL_SECONDS = 60
QUEUE_INTERVAL_SECONDS = 10
DISPATCH_INTERVAL_SECONDS = 30
AUDIT_INTERVAL_SECONDS = 300
CADENCE_CHECK_INTERVAL_SECONDS = 60


def create_scheduler(
    health_monitor: Any,
    alerting_service: Any,
    write_queue: Any,
    simulation_engine: Any | None = None,
    event_dispatcher: Any | None = None,
    event_auditor: Any | None = None,
    cadence_checker: Any | None = None,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def health_check_job():
        try:
            await health_monitor.check()
        except Exception:
            logger.exception("Health check failed")

    async def daily_digest_job():
        try:
            await alerting_service.send_daily_digest({})
        except Exception:
            logger.exception("Daily digest failed")

    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(seconds=HEALTH_CHECK_INTERVAL_SECONDS),
        id="jira_health_check",
        replace_existing=True,
    )

    scheduler.add_job(
        daily_digest_job,
        trigger=CronTrigger(
            hour=DAILY_DIGEST_HOUR,
            minute=DAILY_DIGEST_MINUTE,
            timezone="UTC",
        ),
        id="daily_digest",
        replace_existing=True,
    )

    # -- Simulation tick + Jira queue processing (start paused) --
    if simulation_engine is not None:
        async def simulation_tick_job():
            try:
                if simulation_engine.should_tick():
                    await simulation_engine.tick()
            except Exception:
                logger.exception("Simulation tick failed")

        async def queue_process_job():
            try:
                await write_queue.process_batch(
                    tick_interval_seconds=QUEUE_INTERVAL_SECONDS * 2,
                )
            except Exception:
                logger.exception("Queue processing failed")

        scheduler.add_job(
            simulation_tick_job,
            trigger=IntervalTrigger(seconds=TICK_INTERVAL_SECONDS),
            id="simulation_tick",
            replace_existing=True,
            next_run_time=None,  # starts paused
        )

        scheduler.add_job(
            queue_process_job,
            trigger=IntervalTrigger(seconds=QUEUE_INTERVAL_SECONDS),
            id="queue_process",
            replace_existing=True,
            next_run_time=None,  # starts paused
        )

    # -- Event dispatch (schedule-based simulation) --
    if event_dispatcher is not None:
        def event_dispatch_job():
            try:
                event_dispatcher.dispatch_due_events()
            except Exception:
                logger.exception("Event dispatch failed")

        scheduler.add_job(
            event_dispatch_job,
            trigger=IntervalTrigger(seconds=DISPATCH_INTERVAL_SECONDS),
            id="event_dispatch",
            replace_existing=True,
            next_run_time=None,  # starts paused
        )

    # -- Event audit (verification of dispatched events) --
    if event_auditor is not None:
        async def event_audit_job():
            try:
                await event_auditor.run_audit()
            except Exception:
                logger.exception("Event audit failed")

        scheduler.add_job(
            event_audit_job,
            trigger=IntervalTrigger(seconds=AUDIT_INTERVAL_SECONDS),
            id="event_audit",
            replace_existing=True,
        )

    # -- Sprint cadence check (auto-trigger precomputation) --
    if cadence_checker is not None:
        async def cadence_check_job():
            try:
                await cadence_checker.check_and_trigger()
            except Exception:
                logger.exception("Sprint cadence check failed")

        scheduler.add_job(
            cadence_check_job,
            trigger=IntervalTrigger(seconds=CADENCE_CHECK_INTERVAL_SECONDS),
            id="sprint_cadence_check",
            replace_existing=True,
        )

    return scheduler

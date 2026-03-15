import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL_SECONDS = 60
DAILY_DIGEST_HOUR = 8
DAILY_DIGEST_MINUTE = 0


def create_scheduler(
    health_monitor: Any,
    alerting_service: Any,
    write_queue: Any,
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

    return scheduler

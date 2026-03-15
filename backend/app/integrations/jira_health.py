import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

FAILURES_THRESHOLD = 2

StatusChangeCallback = Callable[[str, str], Coroutine[Any, Any, None]]


class JiraHealthMonitor:
    def __init__(
        self,
        jira_client: Any,
        on_status_change: StatusChangeCallback | None = None,
    ):
        self._jira_client = jira_client
        self._on_status_change = on_status_change
        self.status: str = "ONLINE"
        self.last_checked: datetime | None = None
        self.last_online: datetime | None = None
        self.consecutive_failures: int = 0
        self.outage_start: datetime | None = None

    async def check(self) -> None:
        is_reachable = await self._jira_client.ping()
        self.last_checked = datetime.now(UTC)

        if is_reachable:
            await self._handle_success()
        else:
            await self._handle_failure()

    async def _handle_success(self) -> None:
        self.consecutive_failures = 0
        self.last_online = datetime.now(UTC)

        if self.status == "OFFLINE":
            await self._transition_to("RECOVERING")
        elif self.status == "ONLINE":
            pass

    async def _handle_failure(self) -> None:
        self.consecutive_failures += 1

        if self.status == "ONLINE":
            if self.consecutive_failures >= FAILURES_THRESHOLD:
                self.outage_start = datetime.now(UTC)
                await self._transition_to("OFFLINE")

    def mark_recovery_complete(self) -> None:
        if self.status == "RECOVERING":
            self.status = "ONLINE"
            self.outage_start = None
            logger.info("Jira recovery complete, status: ONLINE")

    async def _transition_to(self, new_status: str) -> None:
        old_status = self.status
        self.status = new_status
        logger.info("Jira health: %s -> %s", old_status, new_status)

        if self._on_status_change:
            await self._on_status_change(old_status, new_status)

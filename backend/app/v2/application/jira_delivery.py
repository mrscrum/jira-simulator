"""Transport-neutral orchestration for committed Jira intents."""

from datetime import datetime, timedelta
from typing import Protocol

from app.v2.domain.jira_delivery import (
    DeliveryBatchResult,
    JiraDeliveryFailure,
    JiraDeliverySuccess,
    PendingJiraIntent,
)

BASE_RETRY_SECONDS = 10
MAX_RETRY_SECONDS = 300


class JiraDeliveryStore(Protocol):
    def pending(self, as_of: datetime, limit: int = 50) -> tuple[PendingJiraIntent, ...]: ...

    def record_success(self, result: JiraDeliverySuccess) -> None: ...

    def record_failure(self, result: JiraDeliveryFailure) -> None: ...


class JiraIntentAdapter(Protocol):
    async def deliver(self, intent: PendingJiraIntent) -> JiraDeliverySuccess: ...


class JiraDeliveryError(RuntimeError):
    """A visible provider failure that remains retryable."""


class JiraDeliveryProviderError(JiraDeliveryError):
    """A non-rate-limit provider or transport failure."""


class JiraDeliveryRateLimitError(JiraDeliveryError):
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__(f"Jira rate limited delivery for {self.retry_after_seconds} seconds")


class JiraDeliveryWorker:
    """Sequentially deliver committed intents without retaining a database session."""

    def __init__(self, store: JiraDeliveryStore, adapter: JiraIntentAdapter) -> None:
        self._store = store
        self._adapter = adapter

    async def drain_once(self, as_of: datetime, limit: int = 50) -> DeliveryBatchResult:
        attempted = delivered = failed = 0
        processed = set()
        while attempted < limit:
            pending = tuple(
                item
                for item in self._store.pending(as_of, limit - attempted)
                if item.intent.id not in processed
            )
            if not pending:
                break
            for item in pending:
                processed.add(item.intent.id)
                attempted += 1
                if await self._deliver_one(item, as_of):
                    delivered += 1
                else:
                    failed += 1
        return DeliveryBatchResult(attempted, delivered, 0, failed)

    async def _deliver_one(self, item: PendingJiraIntent, as_of: datetime) -> bool:
        try:
            success = await self._adapter.deliver(item)
            if success.intent_id != item.intent.id:
                raise JiraDeliveryProviderError("adapter returned the wrong intent identifier")
            self._store.record_success(success)
            return True
        except JiraDeliveryRateLimitError as error:
            retry_at = as_of + timedelta(seconds=error.retry_after_seconds)
            self._record_failure(item, retry_at, error, as_of)
        except JiraDeliveryProviderError as error:
            retry_at = as_of + timedelta(seconds=_retry_delay(item.attempts))
            self._record_failure(item, retry_at, error, as_of)
        return False

    def _record_failure(
        self,
        item: PendingJiraIntent,
        retry_at: datetime,
        error: JiraDeliveryError,
        failed_at: datetime,
    ) -> None:
        failure = JiraDeliveryFailure(item.intent.id, retry_at, str(error), failed_at)
        self._store.record_failure(failure)


def _retry_delay(attempts: int) -> int:
    return min(BASE_RETRY_SECONDS * (2**attempts), MAX_RETRY_SECONDS)

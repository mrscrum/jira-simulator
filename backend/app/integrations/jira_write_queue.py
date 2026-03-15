import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.exceptions import JiraRateLimitError
from app.models.jira_write_queue_entry import JiraWriteQueueEntry

logger = logging.getLogger(__name__)

OPERATION_PRIORITY = {
    "CREATE_ISSUE": 1,
    "ADD_TO_SPRINT": 2,
    "TRANSITION_ISSUE": 3,
    "ADD_COMMENT": 4,
    "CREATE_LINK": 5,
    "UPDATE_ISSUE": 6,
    "UPDATE_SPRINT": 7,
    "COMPLETE_SPRINT": 7,
}

MIN_DELAY_SECONDS = 0.2


class JiraWriteQueue:
    def __init__(
        self,
        session_factory: Any,
        jira_client: Any,
        health_monitor: Any,
    ):
        self._session_factory = session_factory
        self._jira_client = jira_client
        self._health_monitor = health_monitor

    def _get_session(self) -> Session:
        return self._session_factory()

    def enqueue(
        self,
        team_id: int,
        operation_type: str,
        payload: dict,
        issue_id: int | None = None,
    ) -> None:
        session = self._get_session()
        priority = OPERATION_PRIORITY.get(operation_type, 5)
        entry = JiraWriteQueueEntry(
            team_id=team_id,
            issue_id=issue_id,
            operation_type=operation_type,
            payload=payload,
            priority=priority,
        )
        session.add(entry)
        session.commit()

    def get_pending_batch(self) -> list[JiraWriteQueueEntry]:
        session = self._get_session()
        return (
            session.query(JiraWriteQueueEntry)
            .filter(JiraWriteQueueEntry.status == "PENDING")
            .order_by(
                JiraWriteQueueEntry.priority,
                JiraWriteQueueEntry.created_at,
            )
            .all()
        )

    async def process_one(
        self, entry: JiraWriteQueueEntry
    ) -> float | None:
        entry.status = "IN_FLIGHT"
        session = self._get_session()
        session.commit()

        try:
            await self._dispatch(entry)
            entry.status = "DONE"
            entry.processed_at = datetime.now(UTC)
            session.commit()
            return None
        except JiraRateLimitError as exc:
            entry.status = "PENDING"
            session.commit()
            return exc.retry_after
        except Exception as exc:
            entry.status = "FAILED"
            entry.attempts += 1
            entry.last_error = str(exc)[:500]
            session.commit()
            logger.error("Queue entry %s failed: %s", entry.id, exc)
            return None

    async def _dispatch(self, entry: JiraWriteQueueEntry) -> None:
        op = entry.operation_type
        payload = entry.payload

        if op == "CREATE_ISSUE":
            await self._jira_client.create_issue(**payload)
        elif op == "UPDATE_ISSUE":
            await self._jira_client.update_issue(**payload)
        elif op == "TRANSITION_ISSUE":
            await self._jira_client.transition_issue(**payload)
        elif op == "ADD_COMMENT":
            await self._jira_client.add_comment(**payload)
        elif op == "CREATE_LINK":
            await self._jira_client.create_issue_link(**payload)
        elif op == "ADD_TO_SPRINT":
            await self._jira_client.add_issues_to_sprint(**payload)
        elif op == "UPDATE_SPRINT":
            await self._jira_client.start_sprint(**payload)
        elif op == "COMPLETE_SPRINT":
            await self._jira_client.complete_sprint(**payload)
        else:
            raise ValueError(f"Unknown operation: {op}")

    async def process_batch(self, tick_interval_seconds: float) -> None:
        if self._health_monitor.status == "OFFLINE":
            logger.info("Jira offline, skipping queue processing")
            return

        batch = self.get_pending_batch()
        if not batch:
            return

        available_time = tick_interval_seconds * 0.8
        delay = max(available_time / len(batch), MIN_DELAY_SECONDS)

        for entry in batch:
            retry_after = await self.process_one(entry)
            if retry_after:
                logger.info("Rate limited, pausing %ss", retry_after)
                await asyncio.sleep(retry_after)
                break
            await asyncio.sleep(delay)

    async def run_recovery(self) -> None:
        session = self._get_session()
        pending = (
            session.query(JiraWriteQueueEntry)
            .filter(JiraWriteQueueEntry.status == "PENDING")
            .order_by(JiraWriteQueueEntry.created_at)
            .all()
        )
        if not pending:
            return

        issues_with_pending = self._group_by_issue(pending)
        for issue_id, entries in issues_with_pending.items():
            await self._collapse_and_write(entries, issue_id)

    def _group_by_issue(
        self, entries: list[JiraWriteQueueEntry]
    ) -> dict[int | None, list[JiraWriteQueueEntry]]:
        groups: dict[int | None, list[JiraWriteQueueEntry]] = {}
        for entry in entries:
            groups.setdefault(entry.issue_id, []).append(entry)
        return groups

    async def _collapse_and_write(
        self,
        entries: list[JiraWriteQueueEntry],
        issue_id: int | None,
    ) -> None:
        if not entries:
            return

        session = self._get_session()
        for entry in entries:
            entry.status = "SKIPPED"
        session.commit()

        last_entry = entries[-1]
        last_entry.status = "PENDING"
        session.commit()

        if issue_id is not None:
            comment_payload = self._build_catchup_comment(entries)
            if comment_payload:
                self.enqueue(
                    team_id=last_entry.team_id,
                    operation_type="ADD_COMMENT",
                    payload=comment_payload,
                    issue_id=issue_id,
                )

    def _build_catchup_comment(
        self, entries: list[JiraWriteQueueEntry]
    ) -> dict | None:
        if not entries:
            return None
        first = entries[0]
        last = entries[-1]
        issue_key = first.payload.get("issue_key")
        if not issue_key:
            return None
        body = (
            f"[Simulator] Sync resumed after outage. "
            f"State fast-forwarded from {first.created_at} to {last.created_at} "
            f"({len(entries)} ticks). Internal simulation continued uninterrupted."
        )
        return {"issue_key": issue_key, "body": body}

    def retry_failed(self) -> int:
        session = self._get_session()
        failed = (
            session.query(JiraWriteQueueEntry)
            .filter(JiraWriteQueueEntry.status == "FAILED")
            .all()
        )
        for entry in failed:
            entry.status = "PENDING"
            entry.attempts = 0
        session.commit()
        return len(failed)

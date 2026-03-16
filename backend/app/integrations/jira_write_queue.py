import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.exceptions import JiraRateLimitError
from app.models.jira_write_queue_entry import JiraWriteQueueEntry

logger = logging.getLogger(__name__)

# Map simulator states to Jira simplified board statuses (To Do / In Progress / Done).
JIRA_STATUS_MAP: dict[str, str] = {
    "SPRINT_COMMITTED": "To Do",
    "QUEUED_FOR_ROLE": "To Do",
    "IN_PROGRESS": "In Progress",
    "PENDING_HANDOFF": "In Progress",
    "EXTERNALLY_BLOCKED": "In Progress",
    "MOVED_LEFT": "In Progress",
    "DONE": "Done",
    "DESCOPED": "Done",
}

OPERATION_PRIORITY = {
    "CREATE_SPRINT": 0,
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
        session: Session | None = None,
    ) -> None:
        own_session = session is None
        if own_session:
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
        if own_session:
            session.commit()

    def get_pending_batch(self, session: Session | None = None) -> list[JiraWriteQueueEntry]:
        if session is None:
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
        self, entry: JiraWriteQueueEntry, session: Session | None = None,
    ) -> float | None:
        if session is None:
            session = self._get_session()
        entry.status = "IN_FLIGHT"
        session.commit()

        try:
            result = await self._dispatch(entry, session=session)
            entry.status = "DONE"
            entry.processed_at = datetime.now(UTC)

            # Map Jira issue key back to local Issue after creation.
            if (
                entry.operation_type == "CREATE_ISSUE"
                and entry.issue_id is not None
                and result
            ):
                self._map_issue_key(session, entry.issue_id, result)

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

    def _map_issue_key(
        self, session: Session, issue_id: int, jira_response: dict,
    ) -> None:
        """Populate jira_issue_key/id on the local Issue after Jira creation."""
        from app.models.issue import Issue

        issue = session.get(Issue, issue_id)
        if issue is None:
            logger.warning("Issue %d not found for key mapping", issue_id)
            return
        issue.jira_issue_key = jira_response.get("key")
        issue.jira_issue_id = str(jira_response.get("id", ""))
        logger.info(
            "Mapped issue %d -> %s", issue_id, issue.jira_issue_key,
        )

    def _map_sprint_id(
        self, session: Session, sprint_db_id: int, jira_response: dict,
    ) -> None:
        """Populate jira_sprint_id on the local Sprint after Jira creation."""
        from app.models.sprint import Sprint

        sprint = session.get(Sprint, sprint_db_id)
        if sprint is None:
            logger.warning("Sprint %d not found for ID mapping", sprint_db_id)
            return
        sprint.jira_sprint_id = jira_response.get("id")
        logger.info(
            "Mapped sprint %d -> jira_sprint_id %s",
            sprint_db_id, sprint.jira_sprint_id,
        )

    async def _dispatch(
        self, entry: JiraWriteQueueEntry, session: Session | None = None,
    ) -> dict | None:
        op = entry.operation_type
        payload = dict(entry.payload)  # copy to avoid mutating stored payload

        if op == "CREATE_SPRINT":
            sprint_db_id = payload.pop("_sprint_db_id", None)
            from datetime import datetime as _dt
            result = await self._jira_client.create_sprint(
                board_id=payload["board_id"],
                name=payload["name"],
                start_date=_dt.fromisoformat(payload["start_date"]),
                end_date=_dt.fromisoformat(payload["end_date"]),
            )
            if sprint_db_id and result and session:
                self._map_sprint_id(session, sprint_db_id, result)
            return result
        elif op == "CREATE_ISSUE":
            # Extract custom fields — Jira Cloud simplified projects reject
            # custom fields on the create/edit screen.  We remove them from
            # the payload and set story points via the Agile estimation API.
            post_create_fields = self._extract_post_create_fields(payload)
            # Pop metadata before sending to Jira.
            sp_field_id = payload.pop("_sp_field_id", None)
            board_id = payload.pop("_board_id", None)
            result = await self._jira_client.create_issue(**payload)
            if result:
                issue_key = result.get("key")
                if issue_key:
                    await self._set_estimation_and_fields(
                        issue_key, post_create_fields,
                        sp_field_id, board_id,
                    )
            return result
        elif op == "UPDATE_ISSUE":
            await self._jira_client.update_issue(**payload)
        elif op == "TRANSITION_ISSUE":
            await self._resolve_and_transition(payload)
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
        return None

    @staticmethod
    def _extract_post_create_fields(payload: dict) -> dict:
        """Move custom fields out of the CREATE_ISSUE payload.

        Jira Cloud simplified projects often reject custom fields on the
        create screen.  We remove them from ``payload['fields']`` and
        return them for a follow-up call.
        """
        fields = payload.get("fields")
        if not fields or not isinstance(fields, dict):
            return {}
        post: dict = {}
        for key in list(fields):
            if key.startswith("customfield_"):
                post[key] = fields.pop(key)
        return post

    async def _set_estimation_and_fields(
        self,
        issue_key: str,
        custom_fields: dict,
        sp_field_id: str | None,
        board_id: int | None,
    ) -> None:
        """Set story points and custom fields after issue creation.

        Uses the Agile estimation API for story points (bypasses screen
        restrictions) and falls back to update_issue for other fields.
        """
        # Set story points via the Agile estimation API.
        sp_value = custom_fields.pop(sp_field_id, None) if sp_field_id else None
        if sp_value is not None and board_id:
            try:
                await self._jira_client.set_estimation(
                    issue_key, int(board_id), float(sp_value),
                )
                logger.info(
                    "Set estimation on %s: %s points (board %s)",
                    issue_key, sp_value, board_id,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to set estimation on %s: %s", issue_key, exc,
                )
        elif sp_value is not None:
            logger.warning(
                "No board_id available to set estimation on %s", issue_key,
            )

        # Set remaining custom fields via standard update.
        if custom_fields:
            try:
                await self._jira_client.update_issue(issue_key, custom_fields)
                logger.info(
                    "Set post-create fields on %s: %s",
                    issue_key, list(custom_fields),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to set post-create fields on %s: %s",
                    issue_key, exc,
                )

    async def _resolve_and_transition(self, payload: dict) -> None:
        """Resolve a target_status name to a Jira transition ID, then transition."""
        issue_key = payload["issue_key"]
        target_status = payload.get("target_status", "")

        # Map simulator state name to Jira status if needed.
        jira_status = JIRA_STATUS_MAP.get(target_status, target_status)

        transitions = await self._jira_client.get_issue_transitions(issue_key)
        transition_id = None
        for t in transitions:
            to_name = t.get("to", {}).get("name", "")
            if to_name == jira_status or t.get("name") == jira_status:
                transition_id = t["id"]
                break

        if transition_id is None:
            available = [t.get("to", {}).get("name", t.get("name")) for t in transitions]
            raise ValueError(
                f"No transition to '{jira_status}' for {issue_key}. "
                f"Available: {available}"
            )

        await self._jira_client.transition_issue(issue_key, transition_id)

    async def process_batch(self, tick_interval_seconds: float) -> None:
        if self._health_monitor.status == "OFFLINE":
            logger.info("Jira offline, skipping queue processing")
            return

        session = self._get_session()
        batch = self.get_pending_batch(session=session)
        if not batch:
            session.close()
            return

        available_time = tick_interval_seconds * 0.8
        delay = max(available_time / len(batch), MIN_DELAY_SECONDS)

        try:
            for entry in batch:
                retry_after = await self.process_one(entry, session=session)
                if retry_after:
                    logger.info("Rate limited, pausing %ss", retry_after)
                    await asyncio.sleep(retry_after)
                    break
                await asyncio.sleep(delay)
        finally:
            session.close()

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

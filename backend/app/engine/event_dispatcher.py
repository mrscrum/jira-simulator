"""Event dispatcher — dispatches scheduled events to the Jira write queue.

Replaces the real-time tick engine with a schedule-based dispatch model.
Runs periodically (every 30s via APScheduler) and enqueues events whose
scheduled_at time has passed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.event_audit_log import EventAuditLog
from app.models.scheduled_event import ScheduledEvent

logger = logging.getLogger(__name__)

DISPATCH_BATCH_SIZE = 50


class EventDispatcher:
    """Dispatches due scheduled events to the Jira write queue."""

    def __init__(self, session_factory: Any, write_queue: Any):
        self._session_factory = session_factory
        self._write_queue = write_queue

    def dispatch_due_events(self) -> int:
        """Find and dispatch all PENDING events whose time has come.

        Returns:
            Number of events dispatched.
        """
        session: Session = self._session_factory()
        dispatched_count = 0
        now = datetime.now(UTC)

        try:
            due_events = (
                session.query(ScheduledEvent)
                .filter(
                    ScheduledEvent.status.in_(["PENDING", "MODIFIED"]),
                    ScheduledEvent.scheduled_at <= now,
                )
                .order_by(
                    ScheduledEvent.scheduled_at,
                    ScheduledEvent.sequence_order,
                )
                .limit(DISPATCH_BATCH_SIZE)
                .all()
            )

            for event in due_events:
                queue_entry_id = self._enqueue_event(session, event)
                event.status = "DISPATCHED"
                event.dispatched_at = now

                audit = EventAuditLog(
                    scheduled_event_id=event.id,
                    jira_queue_entry_id=queue_entry_id,
                    expected_at=event.scheduled_at,
                    dispatched_at=now,
                    verification_status="PENDING",
                )
                session.add(audit)
                dispatched_count += 1

            session.commit()

            if dispatched_count > 0:
                logger.info("Dispatched %d scheduled events", dispatched_count)

        except Exception:
            session.rollback()
            logger.exception("Event dispatch failed")
            raise
        finally:
            session.close()

        return dispatched_count

    def _enqueue_event(
        self, session: Session, event: ScheduledEvent,
    ) -> str | None:
        """Enqueue a single event to the Jira write queue.

        Returns the queue entry ID for audit linkage.
        """
        self._write_queue.enqueue(
            team_id=event.team_id,
            operation_type=event.event_type,
            payload=event.payload,
            issue_id=event.issue_id,
            session=session,
            scheduled_event_id=event.id,
        )
        # The write queue entry was just added to session; find it
        # by scheduled_event_id to get its ID
        from app.models.jira_write_queue_entry import JiraWriteQueueEntry
        entry = (
            session.query(JiraWriteQueueEntry)
            .filter_by(scheduled_event_id=event.id)
            .order_by(JiraWriteQueueEntry.created_at.desc())
            .first()
        )
        return entry.id if entry else None

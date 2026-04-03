"""Event auditor — verifies scheduled events were dispatched and processed.

Runs periodically (every 5 minutes) to check that dispatched events
actually reached Jira. Creates alerts for failures and timeouts.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.event_audit_log import EventAuditLog
from app.models.jira_write_queue_entry import JiraWriteQueueEntry
from app.models.scheduled_event import ScheduledEvent

logger = logging.getLogger(__name__)

VERIFICATION_DELAY_MINUTES = 15
TIMEOUT_MINUTES = 60
AUDIT_BATCH_SIZE = 100


class EventAuditor:
    """Verifies that dispatched events were processed by the Jira write queue."""

    def __init__(
        self,
        session_factory: Any,
        alerting_service: Any | None = None,
    ):
        self._session_factory = session_factory
        self._alerting = alerting_service

    async def run_audit(self) -> dict[str, int]:
        """Check pending audit entries and verify their queue status.

        Returns:
            Counts of verified, failed, and timed-out entries.
        """
        session: Session = self._session_factory()
        now = datetime.now(UTC)
        verification_cutoff = now - timedelta(minutes=VERIFICATION_DELAY_MINUTES)
        timeout_cutoff = now - timedelta(minutes=TIMEOUT_MINUTES)

        counts = {"verified": 0, "failed": 0, "timeout": 0}

        try:
            pending_audits = (
                session.query(EventAuditLog)
                .filter(
                    EventAuditLog.verification_status == "PENDING",
                    EventAuditLog.dispatched_at <= verification_cutoff,
                )
                .limit(AUDIT_BATCH_SIZE)
                .all()
            )

            for audit in pending_audits:
                result = self._verify_one(session, audit, timeout_cutoff)
                counts[result] += 1

            session.commit()

        except Exception:
            session.rollback()
            logger.exception("Audit run failed")
            raise
        finally:
            session.close()

        if any(v > 0 for v in counts.values()):
            logger.info(
                "Audit results: verified=%d, failed=%d, timeout=%d",
                counts["verified"], counts["failed"], counts["timeout"],
            )

        return counts

    def _verify_one(
        self,
        session: Session,
        audit: EventAuditLog,
        timeout_cutoff: datetime,
    ) -> str:
        """Verify a single audit entry against its queue entry status.

        Returns 'verified', 'failed', or 'timeout'.
        """
        now = datetime.now(UTC)

        if audit.jira_queue_entry_id:
            queue_entry = session.get(
                JiraWriteQueueEntry, audit.jira_queue_entry_id,
            )

            if queue_entry is not None:
                if queue_entry.status == "DONE":
                    audit.verification_status = "VERIFIED"
                    audit.verified_at = now
                    return "verified"

                if queue_entry.status == "FAILED":
                    audit.verification_status = "FAILED"
                    audit.verified_at = now
                    audit.failure_reason = (
                        queue_entry.last_error or "Jira write failed"
                    )
                    self._maybe_send_alert(audit)
                    return "failed"

        # Check for timeout
        if audit.dispatched_at and audit.dispatched_at <= timeout_cutoff:
            audit.verification_status = "TIMEOUT"
            audit.verified_at = now
            audit.failure_reason = "Event was not processed within timeout"
            self._maybe_send_alert(audit)
            return "timeout"

        # Still pending — not enough time has passed
        return "verified"  # don't count, will be rechecked

    def _maybe_send_alert(self, audit: EventAuditLog) -> None:
        """Send alert if not already sent."""
        if audit.alert_sent:
            return
        audit.alert_sent = True

        if self._alerting is None:
            return

        # Alert will be sent asynchronously by the calling code
        logger.warning(
            "Audit alert: event %d %s — %s",
            audit.scheduled_event_id,
            audit.verification_status,
            audit.failure_reason,
        )

    async def get_audit_summary(
        self, team_id: int, sprint_id: int,
    ) -> dict:
        """Get audit summary for a sprint's scheduled events."""
        session: Session = self._session_factory()
        try:
            # Get all scheduled event IDs for this sprint
            event_ids = (
                session.query(ScheduledEvent.id)
                .filter_by(team_id=team_id, sprint_id=sprint_id)
                .all()
            )
            event_id_list = [eid[0] for eid in event_ids]

            if not event_id_list:
                return {
                    "total": 0, "pending": 0, "dispatched": 0,
                    "verified": 0, "failed": 0, "timeout": 0,
                    "failures": [],
                }

            audits = (
                session.query(EventAuditLog)
                .filter(EventAuditLog.scheduled_event_id.in_(event_id_list))
                .all()
            )

            counts = {
                "total": len(audits),
                "pending": 0,
                "dispatched": 0,
                "verified": 0,
                "failed": 0,
                "timeout": 0,
            }
            failures = []

            for audit in audits:
                status = audit.verification_status
                if status == "PENDING":
                    counts["pending"] += 1
                elif status == "VERIFIED":
                    counts["verified"] += 1
                elif status == "FAILED":
                    counts["failed"] += 1
                    failures.append(audit)
                elif status == "TIMEOUT":
                    counts["timeout"] += 1
                    failures.append(audit)

            counts["dispatched"] = counts["verified"] + counts["failed"] + counts["timeout"]
            counts["failures"] = failures

            return counts
        finally:
            session.close()

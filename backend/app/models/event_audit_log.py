from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EventAuditLog(TimestampMixin, Base):
    __tablename__ = "event_audit_log"

    scheduled_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scheduled_events.id"), nullable=False
    )
    jira_queue_entry_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("jira_write_queue.id"), nullable=True
    )
    expected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(
        String, nullable=False, default="PENDING"
    )
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    alert_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

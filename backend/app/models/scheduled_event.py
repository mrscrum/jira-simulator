from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin


class ScheduledEvent(TimestampMixin, Base):
    __tablename__ = "scheduled_events"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    sprint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sprints.id"), nullable=False
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sim_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="PENDING"
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    original_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    original_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    batch_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)

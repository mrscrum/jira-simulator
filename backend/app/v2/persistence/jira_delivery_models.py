"""SQLAlchemy mappings for v2 Jira delivery receipts and resource identities."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.v2.persistence.utc_datetime import UTCDateTime


class V2JiraDeliveryReceiptModel(Base):
    __tablename__ = "v2_jira_delivery_receipts"
    __table_args__ = (
        CheckConstraint(
            "state IN ('RETRYABLE','DELIVERED')", name="ck_v2_jira_receipts_state"
        ),
        CheckConstraint("attempts >= 1", name="ck_v2_jira_receipts_attempts"),
        CheckConstraint(
            "(state = 'RETRYABLE' AND next_attempt_at IS NOT NULL "
            "AND delivered_at IS NULL AND last_error IS NOT NULL) OR "
            "(state = 'DELIVERED' AND next_attempt_at IS NULL "
            "AND delivered_at IS NOT NULL AND last_error IS NULL)",
            name="ck_v2_jira_receipts_shape",
        ),
        Index("ix_v2_jira_receipts_due", "state", "next_attempt_at"),
    )

    intent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("v2_projection_intents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class V2JiraResourceMappingModel(Base):
    __tablename__ = "v2_jira_resource_mappings"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "internal_kind",
            "jira_id",
            name="uq_v2_jira_mappings_provider_id",
        ),
        UniqueConstraint(
            "team_id",
            "internal_kind",
            "jira_key",
            name="uq_v2_jira_mappings_provider_key",
        ),
        Index("ix_v2_jira_mappings_provider_id", "internal_kind", "jira_id"),
    )

    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("v2_teams.id", ondelete="CASCADE"), primary_key=True
    )
    internal_kind: Mapped[str] = mapped_column(String(30), primary_key=True)
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    jira_id: Mapped[str] = mapped_column(String(100), nullable=False)
    jira_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

"""SQLAlchemy mappings for append-oriented v2 live-slice ledgers."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.v2.persistence.utc_datetime import UTCDateTime


class _LiveEnvelopeMixin:
    append_sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), nullable=False)
    semantic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("v2_teams.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("v2_runs.id", ondelete="CASCADE"), nullable=False
    )
    commit_id: Mapped[str] = mapped_column(String(36), nullable=False)
    transaction_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    canonical_payload: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class V2ActivityEventModel(_LiveEnvelopeMixin, Base):
    __tablename__ = "v2_activity_events"
    __table_args__ = (
        UniqueConstraint("id", name="uq_v2_activity_events_id"),
        UniqueConstraint("semantic_key", name="uq_v2_activity_events_semantic_key"),
        CheckConstraint(
            "transaction_sequence >= 0", name="ck_v2_activity_events_transaction_sequence"
        ),
        CheckConstraint("aggregate_version >= 0", name="ck_v2_activity_aggregate_version"),
        Index("ix_v2_activity_team_append", "team_id", "append_sequence"),
        Index("ix_v2_activity_team_run_append", "team_id", "run_id", "append_sequence"),
        {"sqlite_autoincrement": True},
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)


class V2GroundTruthRecordModel(_LiveEnvelopeMixin, Base):
    __tablename__ = "v2_ground_truth_records"
    __table_args__ = (
        UniqueConstraint("id", name="uq_v2_ground_truth_records_id"),
        UniqueConstraint("semantic_key", name="uq_v2_ground_truth_records_semantic_key"),
        CheckConstraint(
            "transaction_sequence >= 0",
            name="ck_v2_ground_truth_records_transaction_sequence",
        ),
        Index("ix_v2_ground_truth_team_append", "team_id", "append_sequence"),
        Index("ix_v2_ground_truth_team_run_append", "team_id", "run_id", "append_sequence"),
        {"sqlite_autoincrement": True},
    )

    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provenance_type: Mapped[str] = mapped_column(String(50), nullable=False)


class V2ProjectionIntentModel(_LiveEnvelopeMixin, Base):
    __tablename__ = "v2_projection_intents"
    __table_args__ = (
        UniqueConstraint("id", name="uq_v2_projection_intents_id"),
        UniqueConstraint("semantic_key", name="uq_v2_projection_intents_semantic_key"),
        CheckConstraint(
            "transaction_sequence >= 0", name="ck_v2_projection_intents_transaction_sequence"
        ),
        CheckConstraint("aggregate_version >= 0", name="ck_v2_projection_aggregate_version"),
        CheckConstraint("status = 'PENDING'", name="ck_v2_projection_pending"),
        Index("ix_v2_projection_team_append", "team_id", "append_sequence"),
        Index("ix_v2_projection_team_run_append", "team_id", "run_id", "append_sequence"),
        Index("ix_v2_projection_pending", "team_id", "status", "append_sequence"),
        {"sqlite_autoincrement": True},
    )

    target_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

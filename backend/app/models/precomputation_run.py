from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PrecomputationRun(TimestampMixin, Base):
    __tablename__ = "precomputation_runs"

    batch_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    sprint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sprints.id"), nullable=False
    )
    rng_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ticks: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    superseded_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("precomputation_runs.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="ACTIVE"
    )

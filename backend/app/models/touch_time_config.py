from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.workflow_step import WorkflowStep


class TouchTimeConfig(TimestampMixin, Base):
    __tablename__ = "touch_time_configs"
    __table_args__ = (
        UniqueConstraint(
            "workflow_step_id", "issue_type", "story_points",
            name="uq_step_type_points",
        ),
    )

    workflow_step_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_steps.id"), nullable=False
    )
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    story_points: Mapped[int] = mapped_column(Integer, nullable=False)
    min_hours: Mapped[float] = mapped_column(Float, nullable=False)
    max_hours: Mapped[float] = mapped_column(Float, nullable=False)
    full_time_p25: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_time_p50: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_time_p99: Mapped[float | None] = mapped_column(Float, nullable=True)

    workflow_step: Mapped["WorkflowStep"] = relationship(back_populates="touch_time_configs")
